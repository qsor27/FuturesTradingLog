from flask import Blueprint, render_template, request, jsonify
from futures_db import FuturesDB

trade_details_bp = Blueprint('trade_details', __name__)

@trade_details_bp.route('/trade/<int:trade_id>')
def trade_detail(trade_id):
    with FuturesDB() as db:
        # Get comprehensive position data including execution breakdown
        position_data = db.get_position_executions(trade_id)
        
        if not position_data:
            return render_template('error.html', message='Trade not found'), 404
        
        trade = position_data['primary_trade']
        
        # Get linked trades if this trade is part of a group
        linked_trades = None
        group_total_pnl = 0
        group_total_commission = 0
        
        if trade and trade['link_group_id']:
            # Get linked trades and group statistics separately
            linked_trades = db.get_linked_trades(trade['link_group_id'])
            group_stats = db.get_group_statistics(trade['link_group_id'])
            if linked_trades:
                group_total_pnl = group_stats['total_pnl']
                group_total_commission = group_stats['total_commission']
    
    return render_template(
        'trade_detail.html',
        trade=trade,
        position_data=position_data,
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