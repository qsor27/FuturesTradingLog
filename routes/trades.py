from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from futures_db import FuturesDB

trades_bp = Blueprint('trades', __name__, url_prefix='')

@trades_bp.route('/')
def index():
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_order = request.args.get('sort_order', 'DESC')
    account_filter = request.args.get('account')
    trade_result = request.args.get('trade_result')
    side_filter = request.args.get('side')
    
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = int(request.args.get('page_size', 50))
    except (ValueError, TypeError):
        page = 1
        page_size = 50
    
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
            account=account_filter,
            trade_result=trade_result,
            side=side_filter
        )
    
    if page > total_pages and total_pages > 0:
        page = total_pages
        return redirect(url_for('trades.index', 
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filter,
            trade_result=trade_result,
            side=side_filter
        ))
    
    return render_template('index.html', 
        trades=trades,
        sort_by=sort_by,
        sort_order=sort_order,
        accounts=accounts,
        selected_account=account_filter,
        selected_result=trade_result,
        selected_side=side_filter,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_count=total_count
    )

@trades_bp.route('/trade/<int:trade_id>')
def trade_detail(trade_id):
    with FuturesDB() as db:
        trade = db.get_trade_by_id(trade_id)
    
    if trade is None:
        return 'Trade not found', 404
        
    return render_template('trade_detail.html', trade=trade)

@trades_bp.route('/delete-trades', methods=['POST'])
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

@trades_bp.route('/update-trade/<int:trade_id>', methods=['POST'])
def update_trade(trade_id):
    try:
        data = request.get_json()
        chart_url = data.get('chart_url')
        notes = data.get('notes')
        
        with FuturesDB() as db:
            success = db.update_trade_details(trade_id, chart_url, notes)
        
        return jsonify({'success': success})
    except Exception as e:
        print(f"Error updating trade: {e}")
        return jsonify({'success': False, 'message': str(e)})