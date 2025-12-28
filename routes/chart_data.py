"""
Chart Data Routes
Handles OHLC data requests for interactive charts
NOW USING CACHE-ONLY APPROACH - NO API CALLS DURING PAGE LOADS
"""
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Dict, Any
from services.data_service import ohlc_service
from services.cache_only_chart_service import cache_only_chart_service
from services.background_data_manager import background_data_manager
from scripts.TradingLog_db import FuturesDB
from config import SUPPORTED_TIMEFRAMES, PAGE_LOAD_CONFIG
from utils.instrument_utils import get_root_symbol
from services.ohlc_service import OHLCOnDemandService
from services.symbol_service import symbol_service

# Import the chart execution extensions
import scripts.TradingLog_db_extension

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


def get_execution_overlay_for_chart(position_id: int, timeframe: str, instrument: str) -> List[Dict[str, Any]]:
    """
    Get execution overlay data for chart display from position executions.
    
    Args:
        position_id: Position identifier
        timeframe: Chart timeframe for timestamp alignment  
        instrument: Trading instrument (for validation)
        
    Returns:
        List of execution arrow data for chart overlay
    """
    try:
        with FuturesDB() as db:
            chart_data = db.get_position_executions_for_chart(position_id, timeframe)
            
        if not chart_data or not chart_data.get('executions'):
            return []
        
        # Convert to simplified arrow format for chart overlay
        arrows = []
        for execution in chart_data['executions']:
            arrow_data = {
                'timestamp': execution['timestamp_ms'],
                'price': execution['price'],
                'arrow_type': execution['execution_type'],
                'side': execution['side'],
                'tooltip_data': {
                    'quantity': execution['quantity'],
                    'pnl_dollars': execution['pnl_dollars'],
                    'execution_id': execution['id'],
                    'commission': execution['commission'],
                    'position_quantity': execution['position_quantity']
                }
            }
            arrows.append(arrow_data)
        
        return arrows
        
    except Exception as e:
        logger.error(f"Error getting execution overlay for position {position_id}: {e}")
        return []


@chart_data_bp.route('/api/chart-data/<instrument>')
def get_chart_data(instrument):
    """
    API endpoint for chart OHLC data - CACHE-ONLY MODE
    This endpoint NEVER triggers Yahoo Finance API calls
    """
    try:
        # Get parameters
        timeframe = request.args.get('timeframe', '1m')
        days = int(request.args.get('days', 1))
        position_id = request.args.get('position_id')  # Optional position ID for execution overlays
        
        # Allow explicit start_date and end_date parameters
        start_date_param = request.args.get('start_date')
        end_date_param = request.args.get('end_date')
        
        if start_date_param and end_date_param:
            # Use provided date range
            start_date = datetime.fromisoformat(start_date_param)
            end_date = datetime.fromisoformat(end_date_param)
        else:
            # Check if we have data for this instrument and use available range if recent data doesn't exist
            with FuturesDB() as db:
                db.cursor.execute(
                    'SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                    (instrument, timeframe)
                )
                result = db.cursor.fetchone()
                
                if result[0] and result[1]:
                    # We have data - check if it's recent (within last 7 days)
                    available_start = datetime.fromtimestamp(result[0])
                    available_end = datetime.fromtimestamp(result[1])
                    now = datetime.now()
                    
                    # If latest data is more than 1 day old, use available range instead of "now"
                    if (now - available_end).days > 1:
                        logger.info(f"Using available data range for {instrument} ({available_start} to {available_end}) instead of current dates")
                        end_date = available_end
                        start_date = max(available_start, available_end - timedelta(days=days))
                    else:
                        # Recent data available, use normal date calculation
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=days)
                else:
                    # No data available, use current date range (will return empty)
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=days)
        
        # Use cache-only chart service (NEVER triggers API calls)
        if PAGE_LOAD_CONFIG['cache_only_mode']:
            response = cache_only_chart_service.get_chart_data(
                instrument, timeframe, start_date, end_date
            )

            # Add execution overlay if position_id is provided
            if position_id and response.get('success'):
                try:
                    response['executions'] = get_execution_overlay_for_chart(int(position_id), timeframe, instrument)
                except Exception as e:
                    logger.warning(f"Failed to add execution overlay for position {position_id}: {e}")
                    response['executions'] = []

            # Add available_timeframes when no data is returned (for frontend fallback)
            if response.get('count', 0) == 0 or not response.get('data'):
                available_timeframes = {}
                date_range_timeframes = {}  # Timeframes with data in requested date range
                best_timeframe = None
                preferred_order = ['1h', '15m', '5m', '1m', '4h', '1d']  # Prefer 1h for position charts

                # Convert dates to timestamps for query
                start_ts = int(start_date.timestamp()) if start_date else None
                end_ts = int(end_date.timestamp()) if end_date else None

                with FuturesDB() as db:
                    for tf in preferred_order:
                        # First check total count (for available_timeframes display)
                        db.cursor.execute(
                            'SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                            (instrument, tf)
                        )
                        total_count = db.cursor.fetchone()[0]
                        if total_count > 0:
                            available_timeframes[tf] = total_count

                            # Then check count within date range (for best_timeframe selection)
                            if start_ts and end_ts:
                                db.cursor.execute(
                                    'SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ? AND timestamp >= ? AND timestamp <= ?',
                                    (instrument, tf, start_ts, end_ts)
                                )
                                range_count = db.cursor.fetchone()[0]
                                if range_count > 0:
                                    date_range_timeframes[tf] = range_count
                                    if best_timeframe is None:
                                        best_timeframe = tf
                            else:
                                # No date range specified, use total count
                                if best_timeframe is None:
                                    best_timeframe = tf

                response['available_timeframes'] = available_timeframes
                response['best_timeframe'] = best_timeframe
                logger.info(f"No data for {instrument}/{timeframe}, available timeframes: {available_timeframes}, date-range timeframes: {date_range_timeframes}")

            # Add cache status headers for debugging
            if response.get('cache_status'):
                response_headers = {}
                cache_status = response['cache_status']
                response_headers['X-Cache-Status'] = 'fresh' if cache_status.get('is_fresh') else 'stale'
                response_headers['X-Data-Source'] = response['metadata'].get('data_source', 'unknown')
                response_headers['X-Processing-Time'] = str(response['metadata'].get('processing_time_ms', 0))

                return jsonify(response), 200, response_headers

            return jsonify(response)
        
        # Fallback to direct database query (legacy mode)
        else:
            logger.warning("Using legacy database mode - cache_only_mode is disabled")
            
            chart_data = []
            
            with FuturesDB() as db:
                query = '''
                    SELECT timestamp, open_price, high_price, low_price, close_price, volume
                    FROM ohlc_data 
                    WHERE instrument = ? AND timeframe = ? 
                    AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                '''
                
                db.cursor.execute(query, (instrument, timeframe, start_date, end_date))
                results = db.cursor.fetchall()
                
                # Format for TradingView Lightweight Charts
                for row in results:
                    # Convert datetime to timestamp for TradingView
                    timestamp = row[0]
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    chart_data.append({
                        'time': int(timestamp.timestamp()),
                        'open': float(row[1]),
                        'high': float(row[2]), 
                        'low': float(row[3]),
                        'close': float(row[4]),
                        'volume': int(row[5] or 0)
                    })
            
            response = {
                'success': True,
                'data': chart_data,
                'instrument': instrument,
                'timeframe': timeframe,
                'count': len(chart_data),
                'has_data': len(chart_data) > 0,
                'cache_status': {'mode': 'legacy', 'cache_only_mode': False}
            }
            
            # Add execution overlay if position_id is provided
            if position_id:
                try:
                    response['executions'] = get_execution_overlay_for_chart(int(position_id), timeframe, instrument)
                except Exception as e:
                    logger.warning(f"Failed to add execution overlay for position {position_id}: {e}")
                    response['executions'] = []
            
            return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data': [],
            'cache_status': {'error': True}
        }), 500


@chart_data_bp.route('/api/chart-data-simple/<instrument>')
def get_simple_chart_data(instrument):
    """
    Simplified chart data API endpoint - Single, reliable data fetch with clear error handling
    NO fallback logic, NO resolution adaptation, NO emergency data fetching
    """
    print(f"SIMPLE ROUTE ENTERED: {instrument}")
    try:
        # Get basic parameters
        timeframe = request.args.get('timeframe', '1h')
        days = int(request.args.get('days', 7))
        
        logger.info(f"ROUTE CALLED: Simple chart data request: {instrument}, {timeframe}, {days} days")
        print(f"ROUTE CALLED: Simple chart data request: {instrument}, {timeframe}, {days} days")
        
        # Calculate date range - support custom start_date and end_date parameters
        start_date_param = request.args.get('start_date')
        end_date_param = request.args.get('end_date')
        
        if start_date_param and end_date_param:
            # Use provided date range
            start_date = datetime.fromisoformat(start_date_param)
            end_date = datetime.fromisoformat(end_date_param)
            logger.info(f"Using custom date range: {start_date} to {end_date}")
        else:
            # Use default date calculation
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        # Get available timeframes first for error suggestions
        available_timeframes = []
        with FuturesDB() as db:
            for tf in ['1m', '5m', '15m', '1h', '4h', '1d']:
                db.cursor.execute(
                    'SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                    (instrument, tf)
                )
                count = db.cursor.fetchone()[0]
                if count > 0:
                    available_timeframes.append(tf)
        
        # Use cache-only chart service for data retrieval
        if PAGE_LOAD_CONFIG['cache_only_mode']:
            logger.info(f"Using cache_only_chart_service for {instrument} {timeframe} from {start_date} to {end_date}")
            response = cache_only_chart_service.get_chart_data(
                instrument, timeframe, start_date, end_date
            )
            logger.info(f"cache_only_chart_service returned: success={response.get('success')}, count={response.get('count')}")
            print(f"DEBUG: cache_only_chart_service response keys: {list(response.keys())}")
            print(f"DEBUG: response success: {response.get('success')}")
            print(f"DEBUG: response data: {len(response.get('data', [])) if response.get('data') else 0} records")
        else:
            # Fallback to direct database query
            chart_data = []
            with FuturesDB() as db:
                query = '''
                    SELECT timestamp, open_price, high_price, low_price, close_price, volume
                    FROM ohlc_data 
                    WHERE instrument = ? AND timeframe = ? 
                    AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                '''
                
                db.cursor.execute(query, (instrument, timeframe, 
                                         int(start_date.timestamp()), 
                                         int(end_date.timestamp())))
                results = db.cursor.fetchall()
                
                for row in results:
                    timestamp = row[0]
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp = int(timestamp.timestamp())
                    elif not isinstance(timestamp, int):
                        timestamp = int(timestamp)
                    
                    chart_data.append({
                        'time': timestamp,
                        'open': float(row[1]),
                        'high': float(row[2]), 
                        'low': float(row[3]),
                        'close': float(row[4]),
                        'volume': int(row[5] or 0)
                    })
            
            response = {
                'success': True,
                'data': chart_data,
                'instrument': instrument,
                'timeframe': timeframe,
                'days': days,
                'count': len(chart_data)
            }
        
        # Check if we have data
        if not response.get('success') or not response.get('data') or len(response.get('data', [])) == 0:
            return jsonify({
                'success': False,
                'instrument': instrument,
                'timeframe': timeframe,
                'days': days,
                'count': 0,
                'data': None,
                'error': f'No data available for {instrument} with {timeframe} timeframe',
                'message': f'Try a different timeframe. Data may be available for: {available_timeframes}' if available_timeframes else 'No data available for this instrument',
                'available_timeframes': available_timeframes,
                'last_updated': None
            })
        
        # Success response
        return jsonify({
            'success': True,
            'instrument': instrument,
            'timeframe': timeframe,
            'days': days,
            'count': len(response['data']),
            'data': response['data'],
            'error': None,
            'message': f'Successfully loaded {len(response["data"])} candles',
            'available_timeframes': available_timeframes,
            'last_updated': datetime.now().isoformat()
        })
        
    except ValueError as ve:
        logger.error(f"Invalid parameters for simple chart data: {ve}")
        return jsonify({
            'success': False,
            'error': f'Invalid parameters: {str(ve)}',
            'instrument': instrument,
            'timeframe': request.args.get('timeframe', '1h'),
            'days': request.args.get('days', 7),
            'count': 0,
            'data': None
        }), 400
        
    except Exception as e:
        logger.error(f"Error getting simple chart data: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'instrument': instrument,
            'timeframe': request.args.get('timeframe', '1h'),
            'days': request.args.get('days', 7),
            'count': 0,
            'data': None
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
        
        # Check if we have data for this instrument and use available range if recent data doesn't exist
        with FuturesDB() as db:
            db.cursor.execute(
                'SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                (instrument, optimal_timeframe)
            )
            result = db.cursor.fetchone()
            
            if result[0] and result[1]:
                # We have data - check if it's recent (within last 7 days)
                available_start = datetime.fromtimestamp(result[0])
                available_end = datetime.fromtimestamp(result[1])
                now = datetime.now()
                
                # If latest data is more than 1 day old, use available range instead of "now"
                if (now - available_end).days > 1:
                    logger.info(f"Using available data range for {instrument} ({available_start} to {available_end}) instead of current dates")
                    end_date = available_end
                    start_date = max(available_start, available_end - timedelta(days=days))
                else:
                    # Recent data available, use normal date calculation
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=days)
            else:
                # No data available, use current date range (will return empty)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
        
        # Get chart data with automatic gap filling
        logger.info(f"Calling ohlc_service.get_chart_data with dates: {start_date} to {end_date}")
        data = ohlc_service.get_chart_data(instrument, optimal_timeframe, start_date, end_date)
        logger.info(f"ohlc_service returned {len(data)} records")
        
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
        logger.info(f"Formatted {len(chart_data)} records for TradingView")
        
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


@chart_data_bp.route('/api/debug-ohlc-service/<instrument>')
def debug_ohlc_service(instrument):
    """Debug route to test ohlc_service directly"""
    try:
        from datetime import datetime
        
        # Use the exact same parameters as the failing adaptive route
        start_date = datetime(2025, 6, 16, 23, 20, 51)
        end_date = datetime(2025, 6, 17, 23, 20, 51)
        timeframe = '1h'
        
        logger.info(f"DEBUG: Testing ohlc_service.get_chart_data('{instrument}', '{timeframe}', {start_date}, {end_date})")
        
        data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
        
        logger.info(f"DEBUG: ohlc_service returned {len(data)} records")
        
        return jsonify({
            'success': True,
            'instrument': instrument,
            'timeframe': timeframe,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'count': len(data),
            'data': data[:5] if data else []  # Return first 5 records for debugging
        })
        
    except Exception as e:
        logger.error(f"DEBUG: Error in debug route: {e}")
        return jsonify({'error': str(e)}), 500

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
        # Preference: hourly intervals, then daily, then shorter intervals
        timeframe_preference = ['1h', '1d', '15m', '5m', '30m', '4h', '2h', '1m', '2m']
        best_timeframe = None
        if available_timeframes:
            for pref in timeframe_preference:
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

@chart_data_bp.route('/api/emergency-data-populate/<instrument>', methods=['POST'])
def emergency_data_populate(instrument):
    """Emergency endpoint to populate missing OHLC data for chart display"""
    try:
        from scripts.emergency_data_fix import run_emergency_fix
        
        logger.info(f"Emergency data population requested for {instrument}")
        
        # Run the emergency data fix
        results = run_emergency_fix(instrument)
        
        if results['success']:
            return jsonify({
                'success': True,
                'message': f'Emergency data population completed for {instrument}',
                'populated_timeframes': results['populated_timeframes'],
                'total_records': results['total_records'],
                'errors': results.get('errors', [])
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Emergency data population failed for {instrument}',
                'errors': results.get('errors', [])
            }), 500
            
    except Exception as e:
        logger.error(f"Emergency data population failed for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/check-data-status/<instrument>')
def check_data_status(instrument):
    """Check current OHLC data status for an instrument"""
    try:
        with FuturesDB() as db:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
            status = {}
            total_records = 0
            
            for timeframe in timeframes:
                db.cursor.execute(
                    "SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?",
                    (instrument, timeframe)
                )
                count = db.cursor.fetchone()[0]
                status[timeframe] = count
                total_records += count
            
            # Determine if data is sufficient for chart display
            has_sufficient_data = any(count > 50 for count in status.values())
            best_timeframe = max(status, key=status.get) if status else None
            
            return jsonify({
                'success': True,
                'instrument': instrument,
                'timeframe_counts': status,
                'total_records': total_records,
                'has_sufficient_data': has_sufficient_data,
                'best_timeframe': best_timeframe if status[best_timeframe] > 0 else None,
                'needs_population': not has_sufficient_data
            })
            
    except Exception as e:
        logger.error(f"Error checking data status for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# NEW BACKGROUND DATA MANAGER MONITORING ENDPOINTS
# =============================================================================

@chart_data_bp.route('/api/background-data/status')
def get_background_data_status():
    """Get background data manager status and performance metrics"""
    try:
        metrics = background_data_manager.get_performance_metrics()
        cache_health = cache_only_chart_service.get_cache_health_status()
        
        return jsonify({
            'success': True,
            'background_data_manager': metrics,
            'cache_health': cache_health,
            'system_status': {
                'cache_only_mode': PAGE_LOAD_CONFIG['cache_only_mode'],
                'background_processing_enabled': BACKGROUND_DATA_CONFIG['enabled'],
                'priority_instruments': BACKGROUND_DATA_CONFIG['priority_instruments'],
                'update_intervals': {
                    'priority': BACKGROUND_DATA_CONFIG['priority_update_interval'],
                    'full': BACKGROUND_DATA_CONFIG['full_update_interval']
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting background data status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/background-data/instrument/<instrument>')
def get_instrument_data_status(instrument):
    """Get detailed data status for a specific instrument"""
    try:
        instrument_status = cache_only_chart_service.get_instrument_status(instrument)
        
        return jsonify({
            'success': True,
            'instrument_status': instrument_status
        })
        
    except Exception as e:
        logger.error(f"Error getting instrument status for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/background-data/force-update/<instrument>', methods=['POST'])
def force_update_instrument_data(instrument):
    """Force immediate background update for specific instrument"""
    try:
        data = request.get_json() or {}
        timeframes = data.get('timeframes')  # Optional, defaults to all timeframes
        
        logger.info(f"Force update requested for {instrument}: {timeframes}")
        
        # Trigger force update via background data manager
        result = background_data_manager.force_update_instrument(instrument, timeframes)
        
        return jsonify({
            'success': result.get('success', False),
            'instrument': instrument,
            'result': result,
            'message': f"Force update completed for {instrument}"
        })
        
    except Exception as e:
        logger.error(f"Error in force update for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_data_bp.route('/api/background-data/cache-health')
def get_cache_health_details():
    """Get detailed cache health and performance information"""
    try:
        health_status = cache_only_chart_service.get_cache_health_status()
        
        return jsonify({
            'success': True,
            'cache_health': health_status
        })
        
    except Exception as e:
        logger.error(f"Error getting cache health details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500