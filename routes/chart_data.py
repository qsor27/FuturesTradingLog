"""
Chart Data Routes
Handles OHLC data requests for interactive charts
"""
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timedelta
import logging
from data_service import ohlc_service
from TradingLog_db import FuturesDB

chart_data_bp = Blueprint('chart_data', __name__)
logger = logging.getLogger(__name__)

@chart_data_bp.route('/api/chart-data/<instrument>')
def get_chart_data(instrument):
    """API endpoint for chart OHLC data"""
    try:
        # Get parameters
        timeframe = request.args.get('timeframe', '1m')
        days = int(request.args.get('days', 1))
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get chart data with automatic gap filling
        data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
        
        # Format for TradingView Lightweight Charts
        chart_data = []
        for record in data:
            chart_data.append({
                'time': record['timestamp'],
                'open': record['open_price'],
                'high': record['high_price'], 
                'low': record['low_price'],
                'close': record['close_price'],
                'volume': record['volume'] or 0
            })
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'instrument': instrument,
            'timeframe': timeframe,
            'count': len(chart_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/trade-markers/<int:trade_id>')
def get_trade_markers(trade_id):
    """Get trade entry/exit markers for chart overlay"""
    try:
        with FuturesDB() as db:
            # Get trade details
            trade = db.get_trade_by_id(trade_id)
            if not trade:
                return jsonify({'success': False, 'error': 'Trade not found'}), 404
            
            markers = []
            
            # Entry marker
            if trade.get('entry_time') and trade.get('entry_price'):
                entry_time = datetime.fromisoformat(trade['entry_time'])
                markers.append({
                    'time': int(entry_time.timestamp()),
                    'position': 'belowBar',
                    'color': '#2196F3' if trade.get('side_of_market') == 'Long' else '#F44336',
                    'shape': 'arrowUp' if trade.get('side_of_market') == 'Long' else 'arrowDown',
                    'text': f"Entry: {trade['entry_price']}"
                })
            
            # Exit marker
            if trade.get('exit_time') and trade.get('exit_price'):
                exit_time = datetime.fromisoformat(trade['exit_time'])
                markers.append({
                    'time': int(exit_time.timestamp()),
                    'position': 'aboveBar',
                    'color': '#4CAF50' if trade.get('dollars_gain_loss', 0) > 0 else '#F44336',
                    'shape': 'arrowDown' if trade.get('side_of_market') == 'Long' else 'arrowUp',
                    'text': f"Exit: {trade['exit_price']} (${trade.get('dollars_gain_loss', 0):.2f})"
                })
            
            return jsonify({
                'success': True,
                'markers': markers,
                'trade_id': trade_id
            })
            
    except Exception as e:
        logger.error(f"Error getting trade markers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/update-data/<instrument>')
def update_instrument_data(instrument):
    """Manually trigger data update for an instrument"""
    try:
        timeframes = request.args.getlist('timeframes')
        if not timeframes:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        success = ohlc_service.update_recent_data(instrument, timeframes)
        
        if success:
            with FuturesDB() as db:
                count = db.get_ohlc_count(instrument)
            
            return jsonify({
                'success': True,
                'message': f'Updated data for {instrument}',
                'total_records': count
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update data'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/chart/<instrument>')
def chart_page(instrument):
    """Standalone chart page for an instrument"""
    try:
        # Get recent trades for this instrument
        with FuturesDB() as db:
            # Get recent trades for this instrument
            db.cursor.execute("""
                SELECT * FROM trades 
                WHERE instrument = ? 
                ORDER BY entry_time DESC 
                LIMIT 10
            """, (instrument,))
            rows = db.cursor.fetchall()
            trades = []
            for row in rows:
                trade_dict = dict(row)
                # Convert date strings to datetime objects for template
                if trade_dict.get('entry_time'):
                    try:
                        trade_dict['entry_time'] = datetime.fromisoformat(trade_dict['entry_time'])
                    except (ValueError, TypeError):
                        trade_dict['entry_time'] = None
                if trade_dict.get('exit_time'):
                    try:
                        trade_dict['exit_time'] = datetime.fromisoformat(trade_dict['exit_time'])
                    except (ValueError, TypeError):
                        trade_dict['exit_time'] = None
                trades.append(trade_dict)
        
        return render_template('chart.html', 
                             instrument=instrument,
                             trades=trades)
        
    except Exception as e:
        logger.error(f"Error loading chart page: {e}")
        return f"Error loading chart: {e}", 500

@chart_data_bp.route('/api/instruments')
def get_available_instruments():
    """Get list of instruments with OHLC data"""
    try:
        with FuturesDB() as db:
            # Get unique instruments from both trades and OHLC data
            db.cursor.execute("""
                SELECT DISTINCT instrument FROM trades
                UNION
                SELECT DISTINCT instrument FROM ohlc_data
                ORDER BY instrument
            """)
            
            instruments = [row[0] for row in db.cursor.fetchall() if row[0]]
            
            return jsonify({
                'success': True,
                'instruments': instruments
            })
            
    except Exception as e:
        logger.error(f"Error getting instruments: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/available-timeframes/<instrument>')
def get_available_timeframes(instrument):
    """Get available timeframes for an instrument with data counts"""
    try:
        timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        available = {}
        
        with FuturesDB() as db:
            for tf in timeframes:
                count = db.get_ohlc_count(instrument, tf)
                if count > 0:
                    available[tf] = count
        
        # Find best fallback timeframe (prefer 1h, then 1d, then others)
        fallback_order = ['1h', '1d', '4h', '15m', '5m', '1m']
        best_timeframe = None
        for tf in fallback_order:
            if tf in available:
                best_timeframe = tf
                break
        
        return jsonify({
            'success': True,
            'instrument': instrument,
            'available_timeframes': available,
            'best_timeframe': best_timeframe,
            'total_timeframes': len(available)
        })
        
    except Exception as e:
        logger.error(f"Error getting available timeframes for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/batch-update-instruments', methods=['POST'])
def batch_update_instruments():
    """API endpoint to batch update multiple instruments across all timeframes"""
    try:
        data = request.get_json() or {}
        
        # Get instruments from request or use active instruments
        instruments = data.get('instruments', [])
        timeframes = data.get('timeframes', ['1m', '3m', '5m', '15m', '1h', '4h', '1d'])
        
        if not instruments:
            # No specific instruments provided - update all active instruments
            logger.info("No instruments specified, updating all active instruments")
            results = ohlc_service.update_all_active_instruments(timeframes)
        else:
            # Update specific instruments
            logger.info(f"Updating specific instruments: {instruments}")
            results = ohlc_service.batch_update_multiple_instruments(instruments, timeframes)
        
        # Calculate summary statistics
        total_requests = sum(len(tf_results) for tf_results in results.values())
        successful_requests = sum(
            1 for tf_results in results.values() 
            for success in tf_results.values() if success
        )
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_instruments': len(results),
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'success_rate': round(success_rate, 1)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/update-timeframes/<instrument>', methods=['POST'])
def update_instrument_timeframes(instrument):
    """API endpoint to update all timeframes for a specific instrument"""
    try:
        data = request.get_json() or {}
        timeframes = data.get('timeframes', ['1m', '3m', '5m', '15m', '1h', '4h', '1d'])
        
        logger.info(f"Updating timeframes for {instrument}: {timeframes}")
        
        results = ohlc_service.batch_update_multiple_instruments([instrument], timeframes)
        
        if instrument in results:
            timeframe_results = results[instrument]
            successful_timeframes = [tf for tf, success in timeframe_results.items() if success]
            failed_timeframes = [tf for tf, success in timeframe_results.items() if not success]
            
            return jsonify({
                'success': True,
                'instrument': instrument,
                'results': timeframe_results,
                'successful_timeframes': successful_timeframes,
                'failed_timeframes': failed_timeframes,
                'success_rate': round(len(successful_timeframes) / len(timeframes) * 100, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': f"No results returned for {instrument}"
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating timeframes for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/batch-update-status')
def get_batch_update_status():
    """Get information about what instruments can be batch updated"""
    try:
        with FuturesDB() as db:
            # Get active instruments from last 30 days
            recent_date = datetime.now() - timedelta(days=30)
            active_instruments = db.get_active_instruments_since(recent_date)
            
            # Get all instruments that have OHLC data
            db.cursor.execute("""
                SELECT DISTINCT instrument 
                FROM ohlc_data 
                ORDER BY instrument
            """)
            instruments_with_data = [row[0] for row in db.cursor.fetchall()]
            
            # Get count of OHLC records per instrument and timeframe
            db.cursor.execute("""
                SELECT instrument, timeframe, COUNT(*) as record_count,
                       MIN(timestamp) as earliest_data,
                       MAX(timestamp) as latest_data
                FROM ohlc_data 
                GROUP BY instrument, timeframe
                ORDER BY instrument, timeframe
            """)
            
            data_summary = {}
            for row in db.cursor.fetchall():
                instrument = row[0]
                timeframe = row[1]
                record_count = row[2]
                earliest_timestamp = row[3]
                latest_timestamp = row[4]
                
                if instrument not in data_summary:
                    data_summary[instrument] = {}
                
                data_summary[instrument][timeframe] = {
                    'record_count': record_count,
                    'earliest_data': datetime.fromtimestamp(earliest_timestamp).isoformat() if earliest_timestamp else None,
                    'latest_data': datetime.fromtimestamp(latest_timestamp).isoformat() if latest_timestamp else None
                }
        
        return jsonify({
            'success': True,
            'active_instruments': active_instruments,
            'instruments_with_data': instruments_with_data,
            'data_summary': data_summary,
            'supported_timeframes': ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        })
        
    except Exception as e:
        logger.error(f"Error getting batch update status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500