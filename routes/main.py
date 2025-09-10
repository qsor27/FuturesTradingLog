from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_from_directory
from scripts.TradingLog_db import FuturesDB
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService
from tasks.position_building import auto_rebuild_positions_async
import os
import time
import shutil
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page now shows positions instead of individual trades"""
    # Redirect to positions dashboard for better organization
    return redirect(url_for('positions.positions_dashboard'))

@main_bp.route('/trades')
def trades_legacy():
    """Legacy trades view - individual trade executions (for debugging/admin)"""
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
        cursor_id = request.args.get('cursor_id')
        cursor_time = request.args.get('cursor_time')
        cursor_id = int(cursor_id) if cursor_id else None
    except (ValueError, TypeError):
        page = 1
        page_size = 50
        cursor_id = None
        cursor_time = None
    
    # Validate page_size
    allowed_page_sizes = [10, 25, 50, 100]
    if page_size not in allowed_page_sizes:
        page_size = 50
    
    with FuturesDB() as db:
        accounts = db.get_unique_accounts()
        trades, total_count, total_pages, next_cursor_id, next_cursor_time = db.get_recent_trades(
            page_size=page_size,
            page=page,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filters,
            trade_result=trade_result,
            side=side_filter,
            cursor_id=cursor_id,
            cursor_time=cursor_time
        )
    
    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        page = total_pages
        return redirect(url_for('main.trades_legacy', 
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
        total_count=total_count,
        next_cursor_id=next_cursor_id,
        next_cursor_time=next_cursor_time
    )

@main_bp.route('/delete-trades', methods=['POST'])
def delete_trades():
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])
        
        if not trade_ids:
            return jsonify({'success': False, 'message': 'No trades selected'})
        
        # Get auto_update_positions parameter (default: true)
        auto_update_positions = data.get('auto_update_positions', True)
        
        # Get affected positions before deletion
        affected_positions = set()
        if auto_update_positions:
            with FuturesDB() as db:
                for trade_id in trade_ids:
                    trade = db.get_trade_by_id(trade_id)
                    if trade:
                        account = trade.get('account')
                        instrument = trade.get('instrument')
                        if account and instrument:
                            affected_positions.add((account, instrument))
        
        with FuturesDB() as db:
            success = db.delete_trades(trade_ids)
        
        response_data = {
            'success': success,
            'auto_update_positions': auto_update_positions
        }
        
        # Trigger automatic position updates if enabled and deletion was successful
        if success and auto_update_positions and affected_positions:
            try:
                from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
                position_updates = {}
                
                with EnhancedPositionServiceV2() as position_service:
                    for account, instrument in affected_positions:
                        result = position_service.rebuild_positions_for_account_instrument(account, instrument)
                        position_updates[f"{account}/{instrument}"] = result
                        
                        logger.info(f"Triggered position update after deletion: {account}/{instrument}")
                
                response_data['position_updates'] = position_updates
                
            except Exception as pos_error:
                logger.error(f"Error triggering position updates after deletion: {pos_error}")
                response_data['position_update_warning'] = f"Position updates failed: {str(pos_error)}"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in delete_trades: {e}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    # Get auto_build_positions parameter (default: true)
    auto_build_positions = request.form.get('auto_build_positions', 'true').lower() == 'true'
    
    if file and file.filename.endswith('.csv'):
        temp_path = 'temp_trades.csv'
        file.save(temp_path)
        
        try:
            with FuturesDB() as db:
                success = db.import_csv(temp_path)
            
            os.remove(temp_path)
            
            if success:
                response_data = {
                    'success': True,
                    'message': 'File successfully imported',
                    'auto_build_positions': auto_build_positions
                }
                
                # Trigger automatic position building if enabled
                if auto_build_positions:
                    try:
                        # Get distinct accounts from the database to determine which accounts need rebuilding
                        with FuturesDB() as db:
                            # Get recently imported accounts (trades from last hour as a proxy)
                            accounts_query = """
                                SELECT DISTINCT account FROM trades 
                                WHERE created_at >= datetime('now', '-1 hour')
                                ORDER BY account
                            """
                            accounts_result = db.execute_query(accounts_query)
                            if accounts_result:
                                accounts = [row['account'] for row in accounts_result]
                                
                                # Get distinct instruments for these accounts
                                if accounts:
                                    placeholders = ','.join('?' for _ in accounts)
                                    instruments_query = f"""
                                        SELECT DISTINCT instrument FROM trades 
                                        WHERE account IN ({placeholders})
                                        AND created_at >= datetime('now', '-1 hour')
                                        ORDER BY instrument
                                    """
                                    instruments_result = db.execute_query(instruments_query, accounts)
                                    if instruments_result:
                                        instruments = [row['instrument'] for row in instruments_result]
                                        
                                        # Trigger async position building for each account
                                        task_ids = []
                                        for account in accounts:
                                            task = auto_rebuild_positions_async.delay(account, instruments)
                                            task_ids.append({
                                                'account': account,
                                                'task_id': task.id,
                                                'instruments': instruments
                                            })
                                        
                                        response_data['position_build_tasks'] = task_ids
                                        response_data['message'] += f' - Position building started for {len(accounts)} accounts'
                                        
                                        logger.info(f"Triggered automatic position building for accounts: {accounts}")
                        
                    except Exception as pos_error:
                        logger.error(f"Error triggering automatic position building: {pos_error}")
                        response_data['position_build_warning'] = f"Position building failed to start: {str(pos_error)}"
                
                return jsonify(response_data), 200
            else:
                return jsonify({'success': False, 'message': 'Error importing file'}), 500
                
        except Exception as e:
            logger.error(f"Error in upload_file: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': False, 'message': f'Import failed: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Invalid file type'}), 400

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
    
    # Get auto_build_positions parameter (default: true)
    auto_build_positions = request.form.get('auto_build_positions', 'true').lower() == 'true'
    
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
            
            # Copy the TradeLog.csv to data directory if successful
            if success:
                temp_tradelog = os.path.join(temp_dir, 'TradeLog.csv')
                if os.path.exists(temp_tradelog):
                    from config import config
                    tradelog_path = os.path.join(str(config.data_dir), 'trade_log.csv')
                    os.makedirs(os.path.dirname(tradelog_path), exist_ok=True)
                    shutil.copy2(temp_tradelog, tradelog_path)
                    print(f"Copied trade log to {tradelog_path}")
                
                # Move archives to data/archive directory
                from config import config
                archive_dir = os.path.join(str(config.data_dir), 'archive')
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
                response_data = {
                    'success': True,
                    'message': 'NT Executions processed successfully',
                    'auto_build_positions': auto_build_positions
                }
                
                # Trigger automatic position building if enabled
                if auto_build_positions:
                    try:
                        # Get distinct accounts from the database to determine which accounts need rebuilding
                        with FuturesDB() as db:
                            # Get recently imported accounts (trades from last hour as a proxy)
                            accounts_query = """
                                SELECT DISTINCT account FROM trades 
                                WHERE created_at >= datetime('now', '-1 hour')
                                ORDER BY account
                            """
                            accounts_result = db.execute_query(accounts_query)
                            if accounts_result:
                                accounts = [row['account'] for row in accounts_result]
                                
                                # Get distinct instruments for these accounts
                                if accounts:
                                    placeholders = ','.join('?' for _ in accounts)
                                    instruments_query = f"""
                                        SELECT DISTINCT instrument FROM trades 
                                        WHERE account IN ({placeholders})
                                        AND created_at >= datetime('now', '-1 hour')
                                        ORDER BY instrument
                                    """
                                    instruments_result = db.execute_query(instruments_query, accounts)
                                    if instruments_result:
                                        instruments = [row['instrument'] for row in instruments_result]
                                        
                                        # Trigger async position building for each account
                                        task_ids = []
                                        for account in accounts:
                                            task = auto_rebuild_positions_async.delay(account, instruments)
                                            task_ids.append({
                                                'account': account,
                                                'task_id': task.id,
                                                'instruments': instruments
                                            })
                                        
                                        response_data['position_build_tasks'] = task_ids
                                        response_data['message'] += f' - Position building started for {len(accounts)} accounts'
                                        
                                        logger.info(f"Triggered automatic position building for accounts: {accounts}")
                        
                    except Exception as pos_error:
                        logger.error(f"Error triggering automatic position building: {pos_error}")
                        response_data['position_build_warning'] = f"Position building failed to start: {str(pos_error)}"
                
                return jsonify(response_data)
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

@main_bp.route('/csv-manager')
def csv_manager():
    """CSV Management interface for batch import operations"""
    from config import config
    
    # Get list of CSV files in data directory and archive subdirectory
    data_dir = str(config.data_dir)
    csv_files = []
    
    try:
        # Check root data directory
        for filename in os.listdir(data_dir):
            if filename.endswith('.csv'):
                file_path = os.path.join(data_dir, filename)
                file_stats = os.stat(file_path)
                csv_files.append({
                    'filename': filename,
                    'path': file_path,
                    'size': file_stats.st_size,
                    'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime)),
                    'location': 'data'
                })
        
        # Check archive subdirectory
        archive_dir = os.path.join(data_dir, 'archive')
        if os.path.exists(archive_dir):
            for filename in os.listdir(archive_dir):
                if filename.endswith('.csv'):
                    file_path = os.path.join(archive_dir, filename)
                    file_stats = os.stat(file_path)
                    csv_files.append({
                        'filename': filename,
                        'path': file_path,
                        'size': file_stats.st_size,
                        'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime)),
                        'location': 'archive'
                    })
        
        # Sort by modification date (newest first)
        csv_files.sort(key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        print(f"Error listing CSV files: {e}")
        csv_files = []
    
    return render_template('csv_manager.html', csv_files=csv_files, data_dir=data_dir)

def detect_csv_format(file_path):
    """Detect if CSV is NinjaTrader format or processed TradeLog format"""
    try:
        import pandas as pd
        df = pd.read_csv(file_path, nrows=1)  # Read just the header
        columns = set(df.columns)
        
        # Check for NinjaTrader execution format
        nt_columns = {'Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'Account'}
        if nt_columns <= columns:
            return 'ninjatrade'
        
        # Check for processed TradeLog format  
        tradelog_columns = {'Instrument', 'Side of Market', 'Entry Price', 'Entry Time', 'Exit Time'}
        if tradelog_columns <= columns:
            return 'tradelog'
            
        return 'unknown'
    except Exception:
        return 'unknown'

def process_ninjatrade_file(file_path):
    """Process a NinjaTrader CSV file using ExecutionProcessing"""
    import tempfile
    import shutil
    import sys
    from config import config
    
    # Create a unique temporary filename in the data directory
    timestamp = int(time.time())
    temp_ninja_name = f"NinjaTrader_temp_{timestamp}.csv"
    temp_ninja_path = os.path.join(str(config.data_dir), temp_ninja_name)
    
    try:
        # Copy the file to data directory with NinjaTrader prefix
        shutil.copy2(file_path, temp_ninja_path)
        
        # Add scripts directory to path
        scripts_dir = os.path.join(os.getcwd(), 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        # Import and run ExecutionProcessing
        import ExecutionProcessing
        
        # The ExecutionProcessing script will process the file and create trade_log.csv
        success = ExecutionProcessing.main()
        
        if success:
            # Return path to the generated trade_log.csv 
            trade_log_path = os.path.join(str(config.data_dir), 'trade_log.csv')
            if os.path.exists(trade_log_path):
                return trade_log_path
        
        return None
            
    except Exception as e:
        print(f"Error processing NinjaTrader file: {e}")
        return None
    finally:
        # Clean up temporary file if it still exists
        if os.path.exists(temp_ninja_path):
            try:
                os.remove(temp_ninja_path)
            except:
                pass

@main_bp.route('/batch-import-csv', methods=['POST'])
def batch_import_csv():
    """Import multiple CSV files in batch"""
    try:
        data = request.get_json()
        selected_files = data.get('selected_files', [])
        auto_process = data.get('auto_process', True)  # Auto-process NinjaTrader files
        
        if not selected_files:
            return jsonify({'success': False, 'message': 'No files selected for import'})
        
        from config import config
        data_dir = str(config.data_dir)
        
        results = []
        successful_imports = 0
        failed_imports = 0
        
        with FuturesDB() as db:
            for filename in selected_files:
                file_path = os.path.join(data_dir, filename)
                
                # Verify file exists and is safe to import
                if not os.path.exists(file_path) or not filename.endswith('.csv'):
                    results.append({
                        'filename': filename,
                        'success': False,
                        'message': 'File not found or invalid type'
                    })
                    failed_imports += 1
                    continue
                
                try:
                    # Detect file format
                    file_format = detect_csv_format(file_path)
                    processed_file = None
                    
                    if file_format == 'ninjatrade' and auto_process:
                        # Process NinjaTrader file first
                        processed_file = process_ninjatrade_file(file_path)
                        if processed_file:
                            import_path = processed_file
                            message_suffix = " (processed from NinjaTrader format)"
                        else:
                            results.append({
                                'filename': filename,
                                'success': False,
                                'message': 'Failed to process NinjaTrader format'
                            })
                            failed_imports += 1
                            continue
                    elif file_format == 'tradelog':
                        import_path = file_path
                        message_suffix = ""
                    else:
                        results.append({
                            'filename': filename,
                            'success': False,
                            'message': f'Unsupported file format: {file_format}'
                        })
                        failed_imports += 1
                        continue
                    
                    # Import the CSV file
                    success = db.import_csv(import_path)
                    
                    # Clean up temporary processed file
                    if processed_file and os.path.exists(processed_file):
                        import shutil
                        temp_dir = os.path.dirname(processed_file)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    
                    if success:
                        results.append({
                            'filename': filename,
                            'success': True,
                            'message': f'Successfully imported{message_suffix}'
                        })
                        successful_imports += 1
                    else:
                        results.append({
                            'filename': filename,
                            'success': False,
                            'message': f'Import failed - check file format{message_suffix}'
                        })
                        failed_imports += 1
                        
                except Exception as e:
                    results.append({
                        'filename': filename,
                        'success': False,
                        'message': f'Import error: {str(e)}'
                    })
                    failed_imports += 1
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_files': len(selected_files),
                'successful': successful_imports,
                'failed': failed_imports
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Batch import error: {str(e)}'
        })

@main_bp.route('/test_date_range.html')
def test_date_range():
    """Serve the date range test page"""
    return send_from_directory('.', 'test_date_range.html')

@main_bp.route('/test_chart_simple')
def test_chart_simple():
    """Serve the simple chart test page"""
    return render_template('test_chart_simple.html')

@main_bp.route('/charts')
def charts():
    """Charts page with dropdown to select different contracts"""
    try:
        with FuturesDB() as db:
            # Get instruments with OHLC data and comprehensive metadata
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(DISTINCT timeframe) as timeframe_count,
                    GROUP_CONCAT(DISTINCT timeframe ORDER BY 
                        CASE timeframe
                            WHEN '1m' THEN 1
                            WHEN '5m' THEN 2
                            WHEN '15m' THEN 3
                            WHEN '1h' THEN 4
                            WHEN '4h' THEN 5
                            WHEN '1d' THEN 6
                            ELSE 7
                        END
                    ) as timeframes,
                    MIN(timestamp) as earliest_data,
                    MAX(timestamp) as latest_data,
                    COUNT(*) as total_records
                FROM ohlc_data 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                HAVING COUNT(*) >= 50  -- Filter out instruments with insufficient data
                ORDER BY instrument
            """)
            
            ohlc_instruments = []
            import time
            current_time = time.time()
            
            for row in db.cursor.fetchall():
                instrument, timeframe_count, timeframes, earliest, latest, total_records = row
                
                # Calculate data freshness (days since last update)
                days_since_update = (current_time - latest) / (24 * 3600) if latest else float('inf')
                
                ohlc_instruments.append({
                    'instrument': instrument,
                    'timeframe_count': timeframe_count,
                    'timeframes': timeframes.split(',') if timeframes else [],
                    'earliest_data': earliest,
                    'latest_data': latest,
                    'total_records': total_records,
                    'days_since_update': int(days_since_update),
                    'is_recent': days_since_update <= 7  # Data within last week
                })
            
            # Get trade instruments for additional context
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(*) as trade_count
                FROM trades 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            trade_instruments = [
                {'instrument': row[0], 'trade_count': row[1]} 
                for row in db.cursor.fetchall()
            ]
        
        return render_template('charts.html',
                             ohlc_instruments=ohlc_instruments,
                             trade_instruments=trade_instruments,
                             page_title='Price Charts')
        
    except Exception as e:
        import traceback
        print(f"Error in charts route: {e}")
        traceback.print_exc()
        # Return template with error message instead of crashing
        return render_template('charts.html', 
                             ohlc_instruments=[], 
                             trade_instruments=[],
                             error_message=f"Failed to load instruments: {str(e)}")

@main_bp.route('/symbols')
def symbols():
    """Symbols/Instruments page to view all available symbols with chart data"""
    try:
        with FuturesDB() as db:
            # Get instruments from both trades and OHLC data with stats
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(DISTINCT timeframe) as timeframe_count,
                    MIN(timestamp) as first_data,
                    MAX(timestamp) as last_data,
                    COUNT(*) as total_records
                FROM ohlc_data 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            ohlc_instruments = []
            for row in db.cursor.fetchall():
                instrument, timeframe_count, first_data, last_data, total_records = row
                ohlc_instruments.append({
                    'instrument': instrument,
                    'timeframe_count': timeframe_count,
                    'first_data': first_data,
                    'last_data': last_data,
                    'total_records': total_records
                })
            
            # Get instruments from trades
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(*) as trade_count,
                    MIN(entry_time) as first_trade,
                    MAX(entry_time) as last_trade
                FROM trades 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            trade_instruments = {}
            for row in db.cursor.fetchall():
                instrument, trade_count, first_trade, last_trade = row
                trade_instruments[instrument] = {
                    'trade_count': trade_count,
                    'first_trade': first_trade,
                    'last_trade': last_trade
                }
        
        return render_template('symbols.html', 
                             ohlc_instruments=ohlc_instruments,
                             trade_instruments=trade_instruments)
        
    except Exception as e:
        print(f"Error in symbols route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500
