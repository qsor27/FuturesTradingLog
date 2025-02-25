from flask import Flask, jsonify
from config import config
from routes.main import main_bp
from routes.trades import trades_bp
from routes.upload import upload_bp
from routes.statistics import statistics_bp
from routes.trade_details import trade_details_bp
from routes.trade_links import trade_links_bp
from routes.chart_data import bp as chart_data_bp
from routes.ninja_trader import ninja_trader_bp
from routes.ninja_trader_dll import ninja_trader_dll_bp
from routes.market_data import market_data_bp
from routes.websocket import socketio, init_websocket
from futures_db import FuturesDB
from market_data.ninja_reader import NinjaMarketData
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    # Apply configuration
    app.config.update(config.flask_config)

    # Initialize WebSocket
    init_websocket(app)

    # Initialize NinjaTrader reader with DLL API
    # Pass use_dll=True to use NinjaTrader.Client.dll instead of socket API
    app.ninja_reader = NinjaMarketData(None, use_dll=True)

    # Register blueprints
    app.register_blueprint(main_bp)  # Main routes (no prefix)
    app.register_blueprint(trades_bp, url_prefix='/trades')
    app.register_blueprint(upload_bp, url_prefix='/upload')
    app.register_blueprint(statistics_bp)
    app.register_blueprint(trade_details_bp, url_prefix='/trade')
    app.register_blueprint(trade_links_bp)
    app.register_blueprint(chart_data_bp)
    app.register_blueprint(ninja_trader_bp)
    app.register_blueprint(ninja_trader_dll_bp)  # Add DLL-specific endpoints
    app.register_blueprint(market_data_bp)  # Add our new market data blueprint

    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy'}), 200

    # Add utility functions to template context
    @app.context_processor
    def utility_processor():
        def get_row_class(pnl):
            if pnl is None:
                return ''
            return 'positive' if pnl > 0 else 'negative' if pnl < 0 else ''

        def get_side_class(side):
            if not side:
                return ''
            return f'side-{side.lower()}'

        return {
            'min': min,
            'max': max,
            'get_row_class': get_row_class,
            'get_side_class': get_side_class
        }

    return app

app = create_app()

if __name__ == '__main__':
    logger.info(f"Starting Flask application with WebSocket support on {config.host}:{config.port}...")
    socketio.run(app, debug=config.debug, port=config.port, host=config.host)