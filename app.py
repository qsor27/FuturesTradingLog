from flask import Flask, jsonify
from config import config
from logging_config import setup_application_logging, get_logger, log_system_info
from routes.main import main_bp
from routes.trades import trades_bp
from routes.upload import upload_bp
from routes.statistics import statistics_bp
from routes.trade_details import trade_details_bp
from routes.trade_links import trade_links_bp
from routes.chart_data import chart_data_bp
from futures_db import FuturesDB

# Setup logging before any other operations
setup_application_logging()
logger = get_logger(__name__)

# Import file watcher conditionally to avoid test import issues
try:
    from services.file_watcher import file_watcher
    FILE_WATCHER_AVAILABLE = True
    logger.info("File watcher service imported successfully")
except ImportError as e:
    logger.warning(f"File watcher not available: {e}")
    file_watcher = None
    FILE_WATCHER_AVAILABLE = False

app = Flask(__name__)

# Apply configuration
app.config.update(config.flask_config)

# Register blueprints
app.register_blueprint(main_bp)  # Main routes (no prefix)
app.register_blueprint(trades_bp, url_prefix='/trades')
app.register_blueprint(upload_bp, url_prefix='/upload')
app.register_blueprint(statistics_bp)  # Changed from stats_bp to statistics_bp
app.register_blueprint(trade_details_bp, url_prefix='/trade')
app.register_blueprint(trade_links_bp)
app.register_blueprint(chart_data_bp)  # Chart data API routes

@app.route('/health')
def health_check():
    try:
        # Test database connection
        with FuturesDB() as db:
            db.cursor.execute("SELECT 1")
            db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"
    
    # Check log directory
    log_dir = config.data_dir / 'logs'
    logs_accessible = log_dir.exists() and log_dir.is_dir()
    
    health_data = {
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'file_watcher_running': file_watcher.is_running() if FILE_WATCHER_AVAILABLE else False,
        'file_watcher_available': FILE_WATCHER_AVAILABLE,
        'logs_accessible': logs_accessible,
        'log_directory': str(log_dir)
    }
    
    logger.info(f"Health check: {health_data}")
    return jsonify(health_data), 200 if db_status == 'healthy' else 503

@app.route('/api/file-watcher/status')
def file_watcher_status():
    """Get file watcher status"""
    if not FILE_WATCHER_AVAILABLE:
        return jsonify({'error': 'File watcher not available'}), 503
    
    return jsonify({
        'running': file_watcher.is_running(),
        'check_interval': file_watcher.check_interval
    })

@app.route('/api/file-watcher/process-now', methods=['POST'])
def process_files_now():
    """Manually trigger file processing"""
    if not FILE_WATCHER_AVAILABLE:
        return jsonify({'error': 'File watcher not available'}), 503
    
    try:
        file_watcher.process_now()
        return jsonify({'message': 'File processing triggered successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    # Log system information for troubleshooting
    log_system_info()
    
    # Start the file watcher service if auto-import is enabled and available
    if FILE_WATCHER_AVAILABLE and config.auto_import_enabled:
        file_watcher.start()
        logger.info(f"File watcher started - checking every {config.auto_import_interval} seconds")
        print(f"File watcher started - checking every {config.auto_import_interval} seconds")
    elif not FILE_WATCHER_AVAILABLE:
        logger.warning("File watcher not available - skipping auto-import")
        print("File watcher not available - skipping auto-import.")
    else:
        logger.info("Auto-import is disabled")
        print("Auto-import is disabled. Set AUTO_IMPORT_ENABLED=true to enable automatic file processing.")
    
    logger.info(f"Starting Flask application on {config.host}:{config.port}")
    
    try:
        app.run(debug=config.debug, port=config.port, host=config.host)
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        raise
    finally:
        # Stop the file watcher when the app shuts down
        if FILE_WATCHER_AVAILABLE and config.auto_import_enabled:
            logger.info("Stopping file watcher service")
            file_watcher.stop()
        logger.info("Application shutdown complete")