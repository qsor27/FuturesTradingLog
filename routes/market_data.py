from flask import Blueprint, jsonify, current_app
from datetime import datetime, timedelta
import logging
from futures_db import FuturesDB

logger = logging.getLogger(__name__)
market_data_bp = Blueprint('market_data', __name__)

@market_data_bp.route('/trade/<int:trade_id>/market-data')
def get_trade_market_data(trade_id):
    """Get market data for a specific trade."""
    try:
        # Use the app's NinjaMarketData instance (which uses DLL API)
        ninja_reader = current_app.ninja_reader
        
        with FuturesDB() as db:
            trade = db.get_trade_by_id(trade_id)
            
            if not trade:
                logger.warning(f"Trade {trade_id} not found")
                return jsonify({'error': 'Trade not found'}), 404
                
            try:
                # Parse trade timestamps
                entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
                start_time = entry_time - timedelta(minutes=150)  # 2.5 hours before
                
                # If we have an exit time, use that to define the window
                if trade['exit_time']:
                    exit_time = datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S')
                    end_time = exit_time + timedelta(minutes=150)  # 2.5 hours after
                else:
                    end_time = entry_time + timedelta(minutes=300)  # 5 hours if no exit
                
                logger.info(f"Fetching market data for trade {trade_id}:")
                logger.info(f"  Instrument: {trade['instrument']}")
                logger.info(f"  Trade time: {entry_time}")
                logger.info(f"  Time window: {start_time} to {end_time}")
                
                market_data = ninja_reader.api.get_bars(
                    instrument=trade['instrument'],
                    start_date=start_time,
                    end_date=end_time,
                    timeframe='1 Minute'
                )
                
                logger.info(f"  Received {len(market_data)} bars")
                if market_data:
                    logger.info(f"  First bar: {market_data[0]}")
                    logger.info(f"  Last bar: {market_data[-1]}")
                
                # Format the trade data
                formatted_trade = {
                    'instrument': trade['instrument'],
                    'side_of_market': trade['side_of_market'],
                    'entry_time': int(entry_time.timestamp()),
                    'entry_price': float(trade['entry_price']),
                }
                
                if trade['exit_time']:
                    formatted_trade['exit_time'] = int(datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S').timestamp())
                    formatted_trade['exit_price'] = float(trade['exit_price'])
                
                # Format market data bars
                formatted_bars = []
                for bar in market_data:
                    # Convert timestamp to Unix timestamp
                    bar_time = datetime.strptime(bar['time'], '%Y-%m-%d %H:%M:%S')
                    formatted_bars.append({
                        'time': int(bar_time.timestamp()),
                        'open': float(bar['open']),
                        'high': float(bar['high']),
                        'low': float(bar['low']),
                        'close': float(bar['close'])
                    })
                
                # Get connection status
                status = ninja_reader.api.get_status()
                
                return jsonify({
                    'bars': formatted_bars,
                    'trade': formatted_trade,
                    'data_source': 'live' if status['connected'] else 'sample'
                })
                
            except ValueError as e:
                logger.error(f"Error parsing trade time: {e}")
                return jsonify({'error': 'Invalid trade time format'}), 400
                
    except Exception as e:
        logger.error(f"Error getting market data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500