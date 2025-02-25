from flask import Blueprint, jsonify, current_app
from datetime import datetime
from market_data.ninja_reader import NinjaMarketData
from futures_db import FuturesDB
from config import config
import logging

bp = Blueprint('chart_data', __name__)
logger = logging.getLogger(__name__)

def get_ninja_reader():
    """Get or create NinjaMarketData instance"""
    if not hasattr(current_app, 'ninja_reader'):
        try:
            logger.info("Creating new NinjaMarketData instance")
            current_app.ninja_reader = NinjaMarketData(None)  # Path is no longer needed
        except Exception as e:
            logger.error(f"Failed to create NinjaMarketData: {e}")
            raise
    return current_app.ninja_reader

def get_trade_by_id(trade_id):
    """Get trade details from database"""
    with FuturesDB() as db:
        return db.get_trade_by_id(trade_id)

@bp.route('/api/chart-data/<int:trade_id>')
def get_trade_chart_data(trade_id):
    try:
        logger.info(f"Getting chart data for trade {trade_id}")
        # Get trade details from database
        trade = get_trade_by_id(trade_id)
        if trade is None:
            logger.error(f"Trade {trade_id} not found")
            return jsonify({
                'status': 'error',
                'message': 'Trade not found'
            }), 404
        
        logger.info(f"Found trade: {trade}")
        
        # Parse datetime from trade
        entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
        exit_time = None
        if trade['exit_time']:
            exit_time = datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S')
        
        # Get chart settings from config
        minutes_before = config.settings.get('chart_settings', {}).get('minutes_before', 60)
        minutes_after = config.settings.get('chart_settings', {}).get('minutes_after', 60)
        
        logger.info(f"Getting market data for {trade['instrument']} around {entry_time}")
        
        # Get market data around trade time
        reader = get_ninja_reader()
        df = reader.get_data_around_time(
            symbol=trade['instrument'],
            timestamp=entry_time,
            minutes_before=minutes_before,
            minutes_after=minutes_after
        )
        
        if df is None or df.empty:
            logger.error(f"No market data found for {trade['instrument']} around {entry_time}")
            return jsonify({
                'status': 'error',
                'message': 'No market data available for this time period'
            }), 404
            
        logger.info(f"Found {len(df)} data points")
        
        # Format data for chart
        chart_data = reader.format_for_chart(df)
        logger.info(f"Formatted {len(chart_data)} points for chart")
        
        response_data = {
            'status': 'success',
            'data': chart_data,
            'trade': {
                'entry_time': int(entry_time.timestamp()),
                'entry_price': float(trade['entry_price']),
                'exit_time': int(exit_time.timestamp()) if exit_time else None,
                'exit_price': float(trade['exit_price']) if trade['exit_price'] else None
            }
        }
        logger.info("Successfully prepared chart data response")
        return jsonify(response_data)
        
    except Exception as e:
        logger.exception(f"Error getting chart data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500