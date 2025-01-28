from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from futures_db import FuturesDB
import os

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