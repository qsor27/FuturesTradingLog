from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from futures_db import FuturesDB
import os
import time
import shutil

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Get all query parameters with defaults
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_order = request.args.get('sort_order', 'DESC')
    account_filters = request.args.getlist('accounts')
    trade_result = request.args.get('trade_result')
    side_filter = request.args.get('side')
    
    # Get pagination parameters with proper error handling
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = int(request.args.get('page_size', 50))
    except (ValueError, TypeError):
        page = 1
        page_size = 50
    
    # Validate page_size
    allowed_page_sizes = [10, 25, 50, 100]
    if page_size not in allowed_page_sizes:
        page_size = 50
    
    with FuturesDB() as db:
        accounts = db.get_unique_accounts()
        trades, total_count, total_pages = db.get_recent_trades(
            page_size=page_size,
            page=page,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filters,
            trade_result=trade_result,
            side=side_filter
        )
    
    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        page = total_pages
        return redirect(url_for('main.index', 
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filters,
            trade_result=trade_result,
            side=side_filter
        ))
    
    return render_template(
        'main.html', 
        trades=trades,
        sort_by=sort_by,
        sort_order=sort_order,
        accounts=accounts,
        selected_accounts=account_filters,
        selected_result=trade_result,
        selected_side=side_filter,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_count=total_count
    )

@main_bp.route('/delete-trades', methods=['POST'])
def delete_trades():
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])
        
        if not trade_ids:
            return jsonify({'success': False, 'message': 'No trades selected'})
        
        with FuturesDB() as db:
            success = db.delete_trades(trade_ids)
        
        return jsonify({'success': success})
    except Exception as e:
        print(f"Error in delete_trades: {e}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file uploaded', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    
    if file and file.filename.endswith('.csv'):
        temp_path = 'temp_trades.csv'
        file.save(temp_path)
        
        with FuturesDB() as db:
            success = db.import_csv(temp_path)
        
        os.remove(temp_path)
        
        if success:
            return 'File successfully imported', 200
        else:
            return 'Error importing file', 500
    
    return 'Invalid file type', 400

def safe_move_file(src, dst, max_attempts=5, delay=1):
    """Move a file with retry mechanism"""
    for i in range(max_attempts):
        try:
            # Release any potential file handles
            import gc
            gc.collect()
            time.sleep(delay)
            
            # Force Python to close any open file handles
            if os.path.exists(src):
                with open(src, 'r') as _:
                    pass
            
            shutil.move(src, dst)
            return True
        except Exception as e:
            if i == max_attempts - 1:
                print(f"Failed to move {src} to {dst} after {max_attempts} attempts: {str(e)}")
                return False
            time.sleep(delay)
    return False

@main_bp.route('/process-nt-executions', methods=['POST'])
def process_nt_executions():
    """Process NinjaTrader execution exports"""
    temp_dir = "temp_processing"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not file.filename.endswith('.csv'):
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a CSV file.'})
        
        # Save to temporary directory
        temp_file_path = os.path.join(temp_dir, 'upload.csv')
        try:
            file.save(temp_file_path)
            file.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error saving file: {str(e)}'})
        
        # Give system time to release file handle
        time.sleep(1)
        
        try:
            # Change working directory to temp_dir
            original_dir = os.getcwd()
            os.chdir(temp_dir)
            
            # Copy required files for processing
            shutil.copy2('upload.csv', 'NinjaTrader.csv')
            shutil.copy2(os.path.join(original_dir, 'instrument_multipliers.json'), 'instrument_multipliers.json')
            
            # Import and run the ExecutionProcessing script from scripts directory
            import sys
            scripts_dir = os.path.join(original_dir, 'scripts')
            sys.path.insert(0, scripts_dir)
            
            try:
                import ExecutionProcessing
                success = ExecutionProcessing.main()
                if not success:
                    print('ExecutionProcessing.main() returned False')
            except Exception as exec_error:
                print(f'Error executing ExecutionProcessing: {str(exec_error)}')
                raise
            
            # Change back to original directory
            os.chdir(original_dir)
            
            # Copy the TradeLog.csv back if successful
            if success:
                temp_tradelog = os.path.join(temp_dir, 'TradeLog.csv')
                if os.path.exists(temp_tradelog):
                    shutil.copy2(temp_tradelog, 'TradeLog.csv')
                
                # Create Archive directory if it doesn't exist
                archive_dir = os.path.join(original_dir, 'Archive')
                os.makedirs(archive_dir, exist_ok=True)
                
                # Move the original uploaded file to Archive
                timestamp = time.strftime('%Y-%m-%d %H-%M %p')
                archive_filename = f'NinjaTrader Grid {timestamp}.csv'
                archive_path = os.path.join(archive_dir, archive_filename)
                original_file = os.path.join(temp_dir, 'upload.csv')
                shutil.copy2(original_file, archive_path)
            
            time.sleep(1)  # Give time for file operations to complete
            
            # Clean up
            try:
                import gc
                gc.collect()
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as cleanup_error:
                print(f"Cleanup warning: {cleanup_error}")
                
            if success:
                return jsonify({'success': True, 'message': 'NT Executions processed successfully'})
            else:
                return jsonify({'success': False, 'message': 'Error processing NT executions'})
            
        except Exception as e:
            # Change back to original directory on error
            if original_dir != os.getcwd():
                os.chdir(original_dir)
            return jsonify({'success': False, 'message': f'Processing error: {str(e)}'})
            
    except Exception as e:
        # Clean up on error
        try:
            import gc
            gc.collect()
            time.sleep(1)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
