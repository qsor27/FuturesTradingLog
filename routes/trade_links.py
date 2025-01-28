from flask import Blueprint, jsonify, request
from futures_db import FuturesDB

trade_links_bp = Blueprint('trade_links', __name__)

@trade_links_bp.route('/link-trades', methods=['POST'])
def link_trades():
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])
        chart_url = data.get('chart_url')
        notes = data.get('notes')
        
        if len(trade_ids) < 2:
            return jsonify({'success': False, 'message': 'At least two trades are required'})
        
        with FuturesDB() as db:
            success = db.link_trades(trade_ids, chart_url, notes)
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@trade_links_bp.route('/unlink-trades', methods=['POST'])
def unlink_trades():
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])
        
        if not trade_ids:
            return jsonify({'success': False, 'message': 'No trades specified'})
        
        with FuturesDB() as db:
            success = db.unlink_trades(trade_ids)
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})