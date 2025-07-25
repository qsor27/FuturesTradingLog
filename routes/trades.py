from flask import Blueprint, render_template, request, jsonify
from TradingLog_db import FuturesDB

trades_bp = Blueprint('trades', __name__)

@trades_bp.route('/detail/<int:trade_id>')
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
                        'net_pnl': trade['dollars_gain_loss'] - (trade['commission'] or 0),
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
                    linked_trades = db.get_linked_trades(trade['link_group_id'])
                    group_stats = db.get_group_statistics(trade['link_group_id'])
                    if linked_trades and group_stats:
                        group_total_pnl = group_stats.get('total_pnl', 0)
                        group_total_commission = group_stats.get('total_commission', 0)
                except Exception as e:
                    print(f"Error getting linked trades: {e}")
        
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

@trades_bp.route('/delete-trades', methods=['POST'])
def delete_trades():
    data = request.get_json()
    trade_ids = data.get('trade_ids', [])
    
    if not trade_ids:
        return jsonify({'success': False, 'error': 'No trade IDs provided'})
    
    with FuturesDB() as db:
        success = db.delete_trades(trade_ids)
    
    return jsonify({'success': success})

@trades_bp.route('/update-notes/<int:trade_id>', methods=['POST'])
def update_notes(trade_id):
    data = request.get_json()
    notes = data.get('notes', '')
    chart_url = data.get('chart_url', '')
    validated = data.get('validated', False)
    reviewed = data.get('reviewed', False)
    
    with FuturesDB() as db:
        success = db.update_trade_details(trade_id, chart_url=chart_url, notes=notes,
                                         confirmed_valid=validated, reviewed=reviewed)
    
    return jsonify({'success': success})

@trades_bp.context_processor
def utility_processor():
    """Add helper functions to the template context."""
    def get_row_class(pnl):
        if pnl is None:
            return ''
        return 'positive' if pnl > 0 else 'negative' if pnl < 0 else ''

    def get_side_class(side):
        if not side:
            return ''
        return f'side-{side.lower()}'

    return dict(
        get_row_class=get_row_class,
        get_side_class=get_side_class
    )
