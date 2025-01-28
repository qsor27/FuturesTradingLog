from flask import Blueprint, render_template, request, jsonify
from futures_db import FuturesDB

trade_details_bp = Blueprint('trade_details', __name__)

@trade_details_bp.route('/trade/<int:trade_id>')
def trade_detail(trade_id):
    with FuturesDB() as db:
        # Get the main trade
        trade = db.get_trade_by_id(trade_id)
        
        # Get linked trades if this trade is part of a group
        linked_trades = None
        group_total_pnl = 0
        group_total_commission = 0
        
        if trade and trade['link_group_id']:
            group_data = db.get_linked_trades(trade['link_group_id'])
            if group_data:
                linked_trades = group_data['trades']
                group_total_pnl = group_data['total_pnl']
                group_total_commission = group_data['total_commission']
    
    return render_template(
        'trade_detail.html',
        trade=trade,
        linked_trades=linked_trades,
        group_total_pnl=group_total_pnl,
        group_total_commission=group_total_commission
    )

@trade_details_bp.route('/trade/<int:trade_id>/update', methods=['POST'])
def update_trade(trade_id):
    data = request.get_json()
    notes = data.get('notes')
    chart_url = data.get('chart_url')
    
    with FuturesDB() as db:
        success = db.update_trade_details(trade_id, chart_url=chart_url, notes=notes)
    
    return jsonify({'success': success})