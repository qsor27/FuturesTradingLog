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
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
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