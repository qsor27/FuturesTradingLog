import os
from flask import Flask, jsonify
from routes.main import main_bp
from routes.trades import trades_bp
from routes.upload import upload_bp
from routes.statistics import statistics_bp
from routes.trade_details import trade_details_bp
from routes.trade_links import trade_links_bp
from futures_db import FuturesDB

app = Flask(__name__)

# Configure database path from environment variable
app.config['DATABASE_PATH'] = os.getenv('DATABASE_PATH', '/app/data/trades.db')

# Register blueprints
app.register_blueprint(main_bp)  # Main routes (no prefix)
app.register_blueprint(trades_bp, url_prefix='/trades')
app.register_blueprint(upload_bp, url_prefix='/upload')
app.register_blueprint(statistics_bp)  # Changed from stats_bp to statistics_bp
app.register_blueprint(trade_details_bp, url_prefix='/trade')
app.register_blueprint(trade_links_bp)

# Add health check endpoint
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

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

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')