from flask import Blueprint, jsonify, request, render_template
from scripts.TradingLog_db import FuturesDB
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
import logging

logger = logging.getLogger(__name__)

trade_links_bp = Blueprint('trade_links', __name__)

@trade_links_bp.route('/update-group/<int:group_id>', methods=['POST'])
def update_group(group_id):
    data = request.get_json()
    notes = data.get('notes', '')
    chart_url = data.get('chart_url', '')
    validated = data.get('validated', False)
    reviewed = data.get('reviewed', False)
    
    # Get auto_update_positions parameter (default: true)
    auto_update_positions = data.get('auto_update_positions', True)
    
    try:
        with FuturesDB() as db:
            trades = db.get_linked_trades(group_id)
            success = True
            affected_positions = set()  # Track unique account/instrument combinations
            
            for trade in trades:
                if not db.update_trade_details(trade['id'], chart_url=chart_url, notes=notes, 
                                           confirmed_valid=validated, reviewed=reviewed):
                    success = False
                else:
                    # Track affected positions for update
                    account = trade.get('account')
                    instrument = trade.get('instrument')
                    if account and instrument:
                        affected_positions.add((account, instrument))
        
        response_data = {
            'success': success,
            'auto_update_positions': auto_update_positions
        }
        
        # Trigger automatic position updates if enabled and update was successful
        if success and auto_update_positions and affected_positions:
            try:
                position_updates = {}
                with EnhancedPositionServiceV2() as position_service:
                    for account, instrument in affected_positions:
                        result = position_service.rebuild_positions_for_account_instrument(account, instrument)
                        position_updates[f"{account}/{instrument}"] = result
                        
                        logger.info(f"Triggered position update for group {group_id}: {account}/{instrument}")
                
                response_data['position_updates'] = position_updates
                
            except Exception as pos_error:
                logger.error(f"Error triggering position updates for group {group_id}: {pos_error}")
                response_data['position_update_warning'] = f"Position updates failed: {str(pos_error)}"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in update_group for group {group_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@trade_links_bp.route('/link-trades', methods=['POST'])
def link_trades():
    data = request.get_json()
    trade_ids = data.get('trade_ids', [])
    
    if not trade_ids or len(trade_ids) < 2:
        return jsonify({
            'success': False,
            'message': 'At least two trades must be selected for linking'
        })
    
    with FuturesDB() as db:
        success, group_id = db.link_trades(trade_ids)
    
    return jsonify({
        'success': success,
        'group_id': group_id
    })

@trade_links_bp.route('/unlink-trades', methods=['POST'])
def unlink_trades():
    data = request.get_json()
    trade_ids = data.get('trade_ids', [])
    
    if not trade_ids:
        return jsonify({
            'success': False,
            'message': 'No trades selected for unlinking'
        })
    
    with FuturesDB() as db:
        success = db.unlink_trades(trade_ids)
    
    return jsonify({
        'success': success
    })

@trade_links_bp.route('/linked-trades/<int:group_id>')
def linked_trades(group_id):
    with FuturesDB() as db:
        trades = db.get_linked_trades(group_id)
        stats = db.get_group_statistics(group_id)
        # Get notes and chart URL from the first trade to show as group values
        if trades:
            group_notes = trades[0].get('notes', '')
            group_chart_url = trades[0].get('chart_url', '')
        else:
            group_notes = ''
            group_chart_url = ''
    
    return render_template(
        'linked_trades.html',
        trades=trades,
        group_id=group_id,
        stats=stats,
        group_notes=group_notes,
        group_chart_url=group_chart_url
    )
