from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB

trade_details_bp = Blueprint('trade_details', __name__)

@trade_details_bp.route('/trade/<int:trade_id>')
def trade_detail(trade_id):
    try:
        with FuturesDB() as db:
            # First try to get the basic trade data
            trade = db.get_trade_by_id(trade_id)
            if not trade:
                return render_template('error.html', 
                                     error="Trade not found", 
                                     message=f"Trade ID {trade_id} does not exist"), 404
            
            # Try to get comprehensive position data including execution breakdown
            position_data = db.get_position_executions(trade_id)
            
            # If position_data fails, create fallback data
            if not position_data:
                position_data = {
                    'primary_trade': trade,
                    'related_executions': [trade],
                    'execution_analysis': {
                        'executions': [],
                        'total_fills': 2,
                        'entry_fills': 1,
                        'exit_fills': 1,
                        'position_lifecycle': 'closed'
                    },
                    'position_summary': {
                        'total_pnl': trade['dollars_gain_loss'],
                        'total_commission': trade['commission'],
                        'total_points': trade['points_gain_loss'],
                        'total_quantity': trade['quantity'],
                        'average_entry_price': trade['entry_price'],
                        'average_exit_price': trade['exit_price'],
                        'net_pnl': trade['dollars_gain_loss'] - trade['commission'],
                        'first_entry': trade['entry_time'],
                        'last_exit': trade['exit_time'],
                        'number_of_fills': 2
                    }
                }
            
            # Get linked trades if this trade is part of a group
            linked_trades = None
            group_total_pnl = 0
            group_total_commission = 0
            
            if trade and trade.get('link_group_id'):
                try:
                    # Get linked trades and group statistics separately
                    linked_trades = db.get_linked_trades(trade['link_group_id'])
                    group_stats = db.get_group_statistics(trade['link_group_id'])
                    if linked_trades and group_stats:
                        group_total_pnl = group_stats.get('total_pnl', 0)
                        group_total_commission = group_stats.get('total_commission', 0)
                except Exception as e:
                    print(f"Error getting linked trades: {e}")
                    # Continue without linked trades data
        
        return render_template(
            'trade_detail.html',
            trade=trade,
            position_data=position_data,
            linked_trades=linked_trades,
            group_total_pnl=group_total_pnl,
            group_total_commission=group_total_commission
        )
        
    except Exception as e:
        print(f"Error in trade_detail route: {e}")
        return render_template('error.html', 
                             error="Server Error", 
                             message=f"An error occurred while loading trade details: {str(e)}"), 500

@trade_details_bp.route('/trade/<int:trade_id>/update', methods=['POST'])
def update_trade(trade_id):
    data = request.get_json()
    notes = data.get('notes')
    chart_url = data.get('chart_url')
    
    with FuturesDB() as db:
        success = db.update_trade_details(trade_id, chart_url=chart_url, notes=notes)
    
    return jsonify({'success': success})