import os
from flask import Flask, jsonify, g
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

# Initialize database connection
def get_db():
    if 'db_instance' not in g:
        g.db_instance = FuturesDB()
    return g.db_instance

# Close database connection when request ends
@app.teardown_appcontext
def close_db(error):
    db_instance = g.pop('db_instance', None)
    if db_instance:
        db_instance.close_db()

# Periodic database optimization
@app.before_request
def before_request():
    # Run optimization every 1000 requests (approximately)
    if 'request_count' not in g:
        g.request_count = 0
    g.request_count += 1
    
    if g.request_count % 1000 == 0:
        db = get_db()
        db.optimize_db()

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(trades_bp, url_prefix='/trades')
app.register_blueprint(upload_bp, url_prefix='/upload')
app.register_blueprint(statistics_bp)
app.register_blueprint(trade_details_bp, url_prefix='/trade')
app.register_blueprint(trade_links_bp)

# Add health check endpoint
@app.route('/health')
def health_check():
    try:
        # Test database connection
        db = get_db()
        db.get_db().execute('SELECT 1').fetchone()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

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
    # Ensure database directory exists
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)
    
    # Initialize database
    with app.app_context():
        db = get_db()
        
    app.run(debug=True, port=5000, host='0.0.0.0')