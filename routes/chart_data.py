"""
Chart Data Routes
Handles OHLC data requests for interactive charts
"""
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timedelta
import logging
from data_service import ohlc_service
from TradingLog_db import FuturesDB
from config import SUPPORTED_TIMEFRAMES, TIMEFRAME_PREFERENCE_ORDER
from utils.instrument_utils import get_root_symbol
from services.ohlc_service import OHLCOnDemandService

chart_data_bp = Blueprint('chart_data', __name__)
logger = logging.getLogger(__name__)


def get_optimal_resolution(duration_days: int, requested_timeframe: str = None) -> str:
    """
    Determine optimal resolution based on data range to maintain performance.
    Prevents memory issues with large datasets while preserving detail for small ranges.
    """
    # For very large ranges, force lower resolution regardless of requested timeframe
    if duration_days > 90:  # > 3 months
        return '1d'  # Daily candles
    elif duration_days > 30:  # > 1 month  
        return '4h'  # 4-hour candles
    elif duration_days > 7:   # > 1 week
        return '1h'  # Hourly candles
    elif duration_days > 1:   # > 1 day
        return '15m' # 15-minute candles
    else:
        return requested_timeframe or '1m'  # Use requested or 1-minute for small ranges


def estimate_candle_count(duration_days: int, timeframe: str) -> int:
    """Estimate number of candles for performance validation"""
    timeframe_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15,
        '1h': 60, '4h': 240, '1d': 1440
    }
    
    total_minutes = duration_days * 24 * 60
    candle_minutes = timeframe_minutes.get(timeframe, 1)
    
    # Account for market hours (roughly 23/24 hours for futures)
    market_factor = 0.96  # ~23 hours of 24
    
    return int(total_minutes * market_factor / candle_minutes)

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
            'count': len(chart_data),
            'has_data': len(chart_data) > 0
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chart_data_bp.route('/api/chart-data-adaptive/<instrument>')
def get_adaptive_chart_data(instrument):
    """Enhanced API endpoint with automatic resolution adaptation for 6-month support"""
    try:
        # Get parameters
        timeframe = request.args.get('timeframe', '1h')
        days = int(request.args.get('days', 1))
        force_resolution = request.args.get('resolution', None)  # Override auto-resolution
        
        logger.info(f"Adaptive chart data request: {instrument}, {timeframe}, {days} days")
        
        # Determine optimal resolution for performance
        if force_resolution:
            optimal_timeframe = force_resolution
            logger.info(f"Using forced resolution: {optimal_timeframe}")
        else:
            optimal_timeframe = get_optimal_resolution(days, timeframe)
            if optimal_timeframe != timeframe:
                logger.info(f"Resolution adapted: {timeframe} → {optimal_timeframe} for {days} days")
        
        # Estimate performance impact
        estimated_candles = estimate_candle_count(days, optimal_timeframe)
        logger.info(f"Estimated candles: {estimated_candles:,}")
        
        # Performance warning for large datasets
        if estimated_candles > 50000:
            logger.warning(f"Large dataset requested: {estimated_candles:,} candles")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get chart data with automatic gap filling
        data = ohlc_service.get_chart_data(instrument, optimal_timeframe, start_date, end_date)
        
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
        
        response_data = {
            'success': True,
            'data': chart_data,
            'instrument': instrument,
            'requested_timeframe': timeframe,
            'actual_timeframe': optimal_timeframe,
            'resolution_adapted': optimal_timeframe != timeframe,
            'days': days,
            'count': len(chart_data),
            'estimated_candles': estimated_candles,
            'performance_warning': estimated_candles > 50000
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting adaptive chart data: {e}")
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

@chart_data_bp.route('/api/position-entry-lines/<int:trade_id>')
def get_position_entry_lines(trade_id):
    """Get position entry price lines for chart overlay"""
    try:
        with FuturesDB() as db:
            # Get trade details
            trade = db.get_trade_by_id(trade_id)
            if not trade:
                return jsonify({'success': False, 'error': 'Trade not found'}), 404
            
            entry_lines = []
            
            # Get position data using the same method as the trade detail page
            try:
                position_data = db.get_position_analysis(trade_id)
                
                # Use position summary average entry price if available
                if (position_data and 
                    position_data.get('position_summary') and 
                    position_data['position_summary'].get('average_entry_price')):
                    
                    avg_entry_price = float(position_data['position_summary']['average_entry_price'])
                    side = trade.get('side_of_market', 'Unknown')
                    
                    # Add the main green average entry price line
                    entry_lines.append({
                        'price': avg_entry_price,
                        'side': side,
                        'type': 'average_entry',
                        'label': f"{side} Avg Entry: {avg_entry_price:.2f}",
                        'color': '#4CAF50'  # Green color for average entry
                    })
                    
                    logger.info(f"Added average entry price line for trade {trade_id}: {avg_entry_price:.2f}")
                    
                else:
                    # Fallback to simple trade entry price if position data unavailable
                    if trade.get('entry_price') and trade.get('side_of_market'):
                        side = trade.get('side_of_market')
                        entry_price = float(trade['entry_price'])
                        
                        entry_lines.append({
                            'price': entry_price,
                            'side': side,
                            'type': 'trade_entry',
                            'label': f"{side} Entry: {entry_price:.2f}",
                            'color': '#4CAF50'  # Green color
                        })
                        
                        logger.info(f"Using fallback trade entry price for trade {trade_id}: {entry_price:.2f}")
                
            except Exception as pos_error:
                logger.warning(f"Could not get position data for trade {trade_id}: {pos_error}")
                
                # Fallback to legacy linked trades approach
                if trade.get('link_group_id'):
                    db.cursor.execute("""
                        SELECT entry_price, side_of_market, quantity, entry_time
                        FROM trades 
                        WHERE link_group_id = ? AND entry_price IS NOT NULL
                        ORDER BY entry_time ASC
                    """, (trade['link_group_id'],))
                    
                    linked_trades = db.cursor.fetchall()
                    
                    if len(linked_trades) > 1:  # Multiple linked trades = position
                        # Calculate average entry price from linked trades
                        total_value = 0
                        total_quantity = 0
                        
                        for linked_trade in linked_trades:
                            if linked_trade[0] and linked_trade[2]:  # entry_price and quantity
                                price = float(linked_trade[0])
                                qty = int(linked_trade[2])
                                total_value += price * qty
                                total_quantity += qty
                        
                        if total_quantity > 0:
                            avg_price = total_value / total_quantity
                            side = trade.get('side_of_market', 'Unknown')
                            
                            entry_lines.append({
                                'price': avg_price,
                                'side': side,
                                'type': 'average_entry',
                                'label': f"{side} Avg Entry: {avg_price:.2f}",
                                'color': '#4CAF50'  # Green color
                            })
                            
                            logger.info(f"Calculated average entry from linked trades for {trade_id}: {avg_price:.2f}")
                
                # Final fallback to simple trade entry
                if not entry_lines and trade.get('entry_price') and trade.get('side_of_market'):
                    side = trade.get('side_of_market')
                    entry_price = float(trade['entry_price'])
                    
                    entry_lines.append({
                        'price': entry_price,
                        'side': side,
                        'type': 'trade_entry',
                        'label': f"{side} Entry: {entry_price:.2f}",
                        'color': '#4CAF50'  # Green color
                    })
            
            return jsonify({
                'success': True,
                'trade_id': trade_id,
                'instrument': trade.get('instrument'),
                'entry_lines': entry_lines,
                'count': len(entry_lines)
            })
            
    except Exception as e:
        logger.error(f"Error getting position entry lines for trade {trade_id}: {e}")
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
    """
    Get available timeframes for an instrument. If no data exists,
    it triggers a fetch and then returns the available timeframes.
    """
    try:
        root_symbol = get_root_symbol(instrument)
        logger.info(f"Getting available timeframes for {instrument} (root: {root_symbol})")
        
        with FuturesDB() as db:
            # 1. Check if any data exists for the root symbol
            fetch_attempted = False
            fetch_error = None
            
            if db.get_ohlc_count(root_symbol) == 0:
                logger.info(f"No OHLC data found for {root_symbol}. Triggering on-demand fetch.")
                fetch_attempted = True
                try:
                    # 2. If not, fetch and store it
                    ohlc_service = OHLCOnDemandService(db)
                    ohlc_service.fetch_and_store_ohlc(instrument)
                    
                    # Verify data was actually fetched
                    if db.get_ohlc_count(root_symbol) == 0:
                        fetch_error = "Data fetch completed but no records were stored"
                        logger.warning(f"On-demand fetch for {instrument} completed but no data was stored")
                    else:
                        logger.info(f"On-demand fetch for {instrument} succeeded, {db.get_ohlc_count(root_symbol)} records stored")
                        
                except Exception as e:
                    fetch_error = str(e)
                    logger.error(f"On-demand fetch failed for {instrument}: {e}")

            # 3. Now, query for the available timeframes with the (potentially) new data
            available_timeframes = []
            for timeframe in SUPPORTED_TIMEFRAMES:
                count = db.get_ohlc_count(root_symbol, timeframe)
                if count > 0:
                    available_timeframes.append({'timeframe': timeframe, 'count': count})
        
        # Determine best timeframe from the populated list
        best_timeframe = None
        if available_timeframes:
            for pref in TIMEFRAME_PREFERENCE_ORDER:
                if any(tf['timeframe'] == pref for tf in available_timeframes):
                    best_timeframe = pref
                    break
        
        # Convert to old format for backward compatibility
        available = {}
        for tf in available_timeframes:
            available[tf['timeframe']] = tf['count']
        
        # Determine overall success state
        has_data = len(available) > 0
        success = has_data or not fetch_attempted  # Success if we have data OR if we didn't need to fetch
        
        result = {
            'success': success,
            'instrument': instrument,
            'available_timeframes': available,
            'best_timeframe': best_timeframe,
            'total_timeframes': len(available),
            'fetch_attempted': fetch_attempted,
            'fetch_error': fetch_error,
            'has_data': has_data
        }
        
        logger.info(f"Final available timeframes for {root_symbol}: {list(available.keys())}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Critical error in get_available_timeframes for {instrument}: {e}")
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

@chart_data_bp.route('/api/gap-filling/force/<instrument>')
def force_gap_fill_api(instrument):
    """API endpoint to force gap filling for a specific instrument"""
    try:
        from background_services import gap_filling_service
        
        # Get optional parameters
        timeframes = request.args.getlist('timeframes') or ['5m', '15m', '1h', '1d']
        days_back = int(request.args.get('days', 7))
        
        logger.info(f"Force gap filling requested for {instrument}: {timeframes}, {days_back} days back")
        
        # Trigger gap filling
        results = gap_filling_service.force_gap_fill(instrument, timeframes, days_back)
        
        # Calculate success statistics
        successful_timeframes = [tf for tf, success in results.items() if success]
        failed_timeframes = [tf for tf, success in results.items() if not success]
        success_rate = (len(successful_timeframes) / len(timeframes) * 100) if timeframes else 0
        
        return jsonify({
            'success': True,
            'instrument': instrument,
            'results': results,
            'successful_timeframes': successful_timeframes,
            'failed_timeframes': failed_timeframes,
            'success_rate': round(success_rate, 1),
            'message': f"Gap filling completed for {instrument}"
        })
        
    except Exception as e:
        logger.error(f"Error in force gap fill API for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/gap-filling/emergency', methods=['POST'])
def emergency_gap_fill_api():
    """API endpoint for emergency gap filling of instruments with recent trades"""
    try:
        from background_services import gap_filling_service
        
        data = request.get_json() or {}
        days_back = data.get('days_back', 7)
        
        logger.warning(f"Emergency gap filling API triggered: {days_back} days back")
        
        # Trigger emergency gap filling
        results = gap_filling_service.emergency_gap_fill_for_trades(days_back)
        
        if not results:
            return jsonify({
                'success': True,
                'message': 'No instruments needed emergency gap filling',
                'results': {}
            })
        
        # Calculate summary statistics
        total_instruments = len(results)
        total_requests = sum(len(tf_results) for tf_results in results.values())
        successful_requests = sum(
            1 for tf_results in results.values() 
            for success in tf_results.values() if success
        )
        overall_success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_instruments': total_instruments,
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'overall_success_rate': round(overall_success_rate, 1)
            },
            'message': f"Emergency gap filling completed for {total_instruments} instruments"
        })
        
    except Exception as e:
        logger.error(f"Error in emergency gap fill API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500