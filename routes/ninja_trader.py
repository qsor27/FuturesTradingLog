from flask import Blueprint, jsonify, request

# Initialize variables
NINJA_TRADER_AVAILABLE = False
NINJA_TRADER_ERROR = None
NinjaTraderAPI = None

# Try to import NinjaTrader APIs
try:
    from ninja_trader_api import NinjaTraderAPI
    from ninjatrader_dll_api import NinjaTraderDLL
    NINJA_TRADER_AVAILABLE = True
    USE_DLL = True  # Set to True to use DLL API, False to use socket API
except ImportError as e:
    NINJA_TRADER_ERROR = str(e)
    print(f"Warning: NinjaTrader API not available: {e}")
except Exception as e:
    NINJA_TRADER_ERROR = str(e)
    print(f"Error initializing NinjaTrader API: {e}")
from ExecutionProcessing import process_trades
import json
from datetime import datetime, timedelta
from config import config

ninja_trader_bp = Blueprint('ninja_trader', __name__)

# Cache for NinjaTrader API instance
_nt_api = None

def get_nt_api():
    """Get or create NinjaTrader API instance."""
    global _nt_api
    if _nt_api is None:
        try:
            if USE_DLL:
                print("Using NinjaTrader DLL API")
                _nt_api = NinjaTraderDLL()
            else:
                print("Using NinjaTrader Socket API")
                _nt_api = NinjaTraderAPI()
        except Exception as e:
            print(f"Error creating NinjaTrader API: {e}")
            return None
    return _nt_api

@ninja_trader_bp.route('/api/ninja-trader/status', methods=['GET'])
def get_status():
    """Check NinjaTrader connection status."""
    if not NINJA_TRADER_AVAILABLE:
        return jsonify({
            'connected': False,
            'available': False,
            'error': NINJA_TRADER_ERROR or 'NinjaTrader API not available',
            'message': 'NinjaTrader integration is not available'
        })

    api = get_nt_api()
    return jsonify({
        'connected': bool(api and api.connected),
        'available': True,
        'error': None if api and api.connected else 'Not connected to NinjaTrader',
        'message': 'Connected to NinjaTrader' if api and api.connected else 'Not connected to NinjaTrader'
    })

@ninja_trader_bp.route('/api/ninja-trader/trades', methods=['GET'])
def get_trades():
    """Get recent trades from NinjaTrader."""
    api = get_nt_api()
    if not api or not api.connected:
        return jsonify({
            'success': False,
            'error': 'NinjaTrader API not available'
        }), 503

    try:
        # Get parameters
        days = request.args.get('days', '7', type=int)
        account = request.args.get('account', None)
        start_date = datetime.now() - timedelta(days=days)

        # Get execution data
        df = api.get_executions(start_date=start_date, account=account)
        
        # Load instrument multipliers
        with open(config.instrument_config, 'r') as f:
            multipliers = json.load(f)

        # Process trades
        processed_trades = process_trades(df, multipliers)

        return jsonify({
            'success': True,
            'trades': processed_trades
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ninja_trader_bp.route('/api/ninja-trader/market-data', methods=['GET'])
def get_market_data():
    """Get market data for a specific instrument."""
    api = get_nt_api()
    if not api or not api.connected:
        return jsonify({
            'success': False,
            'error': 'NinjaTrader API not available'
        }), 503

    try:
        # Get parameters
        instrument = request.args.get('instrument', type=str)
        timeframe = request.args.get('timeframe', '1 Day', type=str)
        days = request.args.get('days', '30', type=int)
        
        if not instrument:
            return jsonify({
                'success': False,
                'error': 'Instrument parameter is required'
            }), 400

        start_date = datetime.now() - timedelta(days=days)
        
        # Get market data
        bars = api.get_bars(
            instrument=instrument,
            start_date=start_date,
            timeframe=timeframe
        )

        return jsonify({
            'success': True,
            'data': bars
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ninja_trader_bp.errorhandler(Exception)
def handle_error(error):
    """Global error handler for ninja_trader blueprint."""
    return jsonify({
        'success': False,
        'error': str(error)
    }), 500