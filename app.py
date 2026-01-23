from flask import Flask, jsonify, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import os
import psutil
import threading
from config import config
from utils.logging_config import setup_application_logging, get_logger, log_system_info
from services.symbol_service import symbol_service
from routes.main import main_bp
from routes.trades import trades_bp
from routes.statistics import statistics_bp
from routes.trade_details import trade_details_bp
from routes.trade_links import trade_links_bp
from routes.chart_data import chart_data_bp
from routes.settings import settings_bp
from routes.reports import reports_bp
from routes.execution_analysis import execution_analysis_bp
from routes.positions import positions_bp
from routes.data_monitoring import data_monitoring_bp
from routes.profiles import profiles_bp
from routes.tasks import bp as tasks_bp
from routes.cache_management import cache_bp
from routes.csv_management import csv_management_bp
from routes.custom_fields import custom_fields_bp
from routes.validation import validation_bp
from routes.validation_cleanup import validation_cleanup_bp
from routes.execution_review import execution_review_bp
from routes.import_logs import import_logs_bp
from scripts.TradingLog_db import FuturesDB
from services.background_services import start_background_services, stop_background_services, get_services_status
from services.background_data_manager import background_data_manager
from scripts.automated_data_sync import start_automated_data_sync, stop_automated_data_sync, get_data_sync_status, force_data_sync
from config import BACKGROUND_DATA_CONFIG
import atexit

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

# Task 5.4: Import NinjaTrader import service
try:
    from services.ninjatrader_import_service import ninjatrader_import_service
    NINJATRADER_IMPORT_AVAILABLE = True
    logger.info("NinjaTrader import service imported successfully")
except ImportError as e:
    logger.warning(f"NinjaTrader import service not available: {e}")
    ninjatrader_import_service = None
    NINJATRADER_IMPORT_AVAILABLE = False

# Task Group 4: Import Daily Import Scheduler
try:
    from services.daily_import_scheduler import daily_import_scheduler
    DAILY_IMPORT_SCHEDULER_AVAILABLE = True
    logger.info("Daily import scheduler imported successfully")
except ImportError as e:
    logger.warning(f"Daily import scheduler not available: {e}")
    daily_import_scheduler = None
    DAILY_IMPORT_SCHEDULER_AVAILABLE = False

app = Flask(__name__)

# Prometheus Metrics for Trading Application
# Request Metrics - with safe registration to prevent duplication errors
try:
    request_count = Counter('flask_requests_total', 'Total Flask requests', ['method', 'endpoint', 'status'])
    request_duration = Histogram('flask_request_duration_seconds', 'Flask request duration', ['method', 'endpoint'])
except ValueError as e:
    # Metrics already registered, retrieve existing ones
    from prometheus_client import REGISTRY
    request_count = None
    request_duration = None
    for collector in list(REGISTRY._collector_to_names.keys()):
        if hasattr(collector, '_name'):
            if collector._name == 'flask_requests_total':
                request_count = collector
            elif collector._name == 'flask_request_duration_seconds':
                request_duration = collector

# Trading-Specific Business Metrics - with safe registration
try:
    trades_processed = Counter('trading_trades_processed_total', 'Total trades processed', ['account', 'instrument'])
    positions_created = Counter('trading_positions_created_total', 'Total positions created', ['instrument'])
    chart_requests = Counter('trading_chart_requests_total', 'Total chart data requests', ['instrument', 'timeframe'])
    ohlc_data_points = Counter('trading_ohlc_data_points_total', 'Total OHLC data points stored', ['instrument', 'timeframe'])
    database_queries = Counter('trading_database_queries_total', 'Total database queries', ['table', 'operation'])
    database_query_duration = Histogram('trading_database_query_duration_seconds', 'Database query duration', ['table', 'operation'])
except ValueError as e:
    # Metrics already registered, use existing ones
    print(f"Prometheus trading metrics already registered: {e}")

# System Health Metrics - with safe registration
# Initialize to None first so they're always defined
system_cpu_usage = None
system_memory_usage = None
system_disk_usage = None
database_connections = None
redis_connections = None
background_services_status = None
file_watcher_status = None
cache_hit_ratio = None
chart_load_time = None
position_calculation_time = None
data_sync_duration = None

try:
    system_cpu_usage = Gauge('system_cpu_usage_percent', 'CPU usage percentage')
    system_memory_usage = Gauge('system_memory_usage_bytes', 'Memory usage in bytes')
    system_disk_usage = Gauge('system_disk_usage_bytes', 'Disk usage in bytes')
    database_connections = Gauge('trading_database_connections_active', 'Active database connections')
    redis_connections = Gauge('trading_redis_connections_active', 'Active Redis connections')

    # Application Health Metrics
    background_services_status = Gauge('trading_background_services_status', 'Background services status', ['service'])
    file_watcher_status = Gauge('trading_file_watcher_status', 'File watcher status')
    cache_hit_ratio = Gauge('trading_cache_hit_ratio', 'Cache hit ratio percentage')

    # Performance Metrics
    chart_load_time = Histogram('trading_chart_load_time_seconds', 'Chart loading time', ['instrument', 'timeframe'])
    position_calculation_time = Histogram('trading_position_calculation_time_seconds', 'Position calculation time')
    data_sync_duration = Histogram('trading_data_sync_duration_seconds', 'Data synchronization duration', ['instrument'])
except ValueError as e:
    # Metrics already registered - they remain None and metrics collection will be skipped
    print(f"Prometheus system/performance metrics already registered: {e}")

# Apply configuration
app.config.update(config.flask_config)

# Register blueprints
# Request Monitoring Middleware
@app.before_request
def before_request():
    """Record request start time for metrics"""
    g.start_time = time.time()

@app.after_request
def after_request(response):
    """Record request metrics"""
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        method = request.method
        endpoint = request.endpoint or 'unknown'
        status = str(response.status_code)

        # Record metrics (safely handle None values)
        try:
            if request_count:
                request_count.labels(method=method, endpoint=endpoint, status=status).inc()
            if request_duration:
                request_duration.labels(method=method, endpoint=endpoint).observe(duration)
        except Exception as e:
            # Ignore metrics errors to prevent breaking the application
            pass

        # Log slow requests (> 1 second)
        if duration > 1.0:
            logger.warning(f"Slow request: {method} {request.path} took {duration:.2f}s")

    return response


@app.teardown_request
def teardown_request(exception=None):
    """Clean up database connections at end of request.

    This prevents 'database is locked' errors by ensuring database
    connections created during a request are properly closed.
    """
    # Clean up DatabaseManager context from custom_fields routes
    if hasattr(g, 'db_manager'):
        try:
            g.db_manager.__exit__(None, None, None)
            logger.debug("Database manager cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up database manager: {e}")
        finally:
            # Remove from g to prevent double cleanup
            delattr(g, 'db_manager')
            if hasattr(g, 'db_context'):
                delattr(g, 'db_context')
            if hasattr(g, 'custom_fields_service'):
                delattr(g, 'custom_fields_service')

# System Metrics Collection (runs in background)
def collect_system_metrics():
    """Collect system health metrics every 30 seconds"""
    while True:
        try:
            # Skip if metrics weren't registered (duplicate registry)
            if system_cpu_usage is None:
                time.sleep(30)
                continue

            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            system_cpu_usage.set(cpu_percent)
            system_memory_usage.set(memory.used)
            system_disk_usage.set(disk.used)

            # Cache hit ratio (if Redis available)
            try:
                from services.redis_cache_service import get_cache_stats
                stats = get_cache_stats()
                if cache_hit_ratio and 'hit_ratio' in stats:
                    cache_hit_ratio.set(stats['hit_ratio'])
            except Exception as e:
                logger.debug(f"Could not collect cache stats: {e}")

            # Background services status
            try:
                from services.background_services import get_services_status
                services = get_services_status()
                if background_services_status:
                    for service_name, is_running in services.items():
                        background_services_status.labels(service=service_name).set(1 if is_running else 0)
            except Exception as e:
                logger.debug(f"Could not collect service status: {e}")

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

        time.sleep(30)

# Start system metrics collection thread
metrics_thread = threading.Thread(target=collect_system_metrics, daemon=True)
metrics_thread.start()

# Blueprint registration
app.register_blueprint(main_bp)  # Main routes (no prefix)
app.register_blueprint(trades_bp, url_prefix='/trades')
app.register_blueprint(statistics_bp)  # Changed from stats_bp to statistics_bp
app.register_blueprint(trade_details_bp, url_prefix='/trade')
app.register_blueprint(trade_links_bp)
app.register_blueprint(chart_data_bp)  # Chart data API routes
app.register_blueprint(settings_bp)  # Settings routes
app.register_blueprint(reports_bp)  # Reports routes
app.register_blueprint(execution_analysis_bp)  # Execution analysis routes
app.register_blueprint(positions_bp, url_prefix='/positions')  # Positions routes
app.register_blueprint(data_monitoring_bp)  # Data monitoring routes
app.register_blueprint(profiles_bp)  # Profile management routes
app.register_blueprint(tasks_bp)  # Task management routes
app.register_blueprint(cache_bp)  # Cache management routes
app.register_blueprint(csv_management_bp)  # CSV management routes
app.register_blueprint(import_logs_bp)  # Import logs routes
app.register_blueprint(custom_fields_bp)  # Custom fields API routes
app.register_blueprint(validation_bp)  # Position-Execution integrity validation routes
app.register_blueprint(validation_cleanup_bp)
app.register_blueprint(execution_review_bp)  # Position validation and database cleanup API routes

# Initialize validation routes with app context
from routes.validation import init_validation_routes
init_validation_routes(app)

# Template filters for symbol handling
@app.template_filter('base_symbol')
def base_symbol_filter(instrument):
    """Extract base symbol from instrument (e.g., 'MNQ SEP25' -> 'MNQ')"""
    return symbol_service.get_base_symbol(instrument)

@app.template_filter('display_name')
def display_name_filter(instrument):
    """Get human-readable name (e.g., 'MNQ' -> 'Micro NASDAQ-100')"""
    return symbol_service.get_display_name(instrument)

@app.template_filter('full_display_name')
def full_display_name_filter(instrument):
    """Get full display name with expiration (e.g., 'MNQ SEP25' -> 'Micro NASDAQ-100 SEP25')"""
    return symbol_service.get_full_display_name(instrument)

@app.template_filter('yfinance_symbol')
def yfinance_symbol_filter(instrument):
    """Get yfinance symbol (e.g., 'MNQ SEP25' -> 'MNQ=F')"""
    return symbol_service.get_yfinance_symbol(instrument)

@app.template_filter('contract_multiplier')
def contract_multiplier_filter(instrument):
    """Get contract multiplier (e.g., 'MNQ' -> 2.0)"""
    return symbol_service.get_multiplier(instrument)

@app.template_filter('timestamp_to_date')
def timestamp_to_date_filter(timestamp):
    """Convert timestamp to readable date"""
    if timestamp:
        from datetime import datetime
        try:
            # Handle different timestamp formats
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            elif isinstance(timestamp, str):
                # Try parsing ISO format string
                try:
                    dt = datetime.fromisoformat(timestamp)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    return timestamp
            elif hasattr(timestamp, 'strftime'):
                # Already a datetime object
                return timestamp.strftime('%Y-%m-%d')
        except (ValueError, OSError):
            return str(timestamp)
    return 'N/A'

# Make symbol_service available in templates
@app.context_processor
def inject_symbol_service():
    return dict(symbol_service=symbol_service)

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

    # Check background services
    services_status = get_services_status()

    # Check data sync system (DEPRECATED - no longer started automatically)
    # OHLC sync is now triggered after daily CSV imports
    data_sync_status = {
        'is_running': False,
        'deprecated': True,
        'note': 'OHLC sync now triggered by Daily Import Scheduler after CSV imports'
    }
    data_sync_healthy = True  # Not a health issue since it's intentionally disabled

    # Check NinjaTrader import service (Task 5.6)
    ninjatrader_import_status = {}
    if NINJATRADER_IMPORT_AVAILABLE:
        try:
            ninjatrader_import_status = ninjatrader_import_service.get_status()
        except Exception as e:
            logger.error(f"NinjaTrader import status check failed: {e}")
            ninjatrader_import_status = {'error': str(e)}

    # Check Daily Import Scheduler (Task Group 4)
    daily_import_status = {}
    if DAILY_IMPORT_SCHEDULER_AVAILABLE:
        try:
            daily_import_status = daily_import_scheduler.get_status()
        except Exception as e:
            logger.error(f"Daily import scheduler status check failed: {e}")
            daily_import_status = {'error': str(e)}

    health_data = {
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'file_watcher_running': file_watcher.is_running() if FILE_WATCHER_AVAILABLE else False,
        'file_watcher_available': FILE_WATCHER_AVAILABLE,
        'ninjatrader_import_running': ninjatrader_import_status.get('running', False) if NINJATRADER_IMPORT_AVAILABLE else False,
        'ninjatrader_import_available': NINJATRADER_IMPORT_AVAILABLE,
        'daily_import_scheduler_running': daily_import_status.get('running', False) if DAILY_IMPORT_SCHEDULER_AVAILABLE else False,
        'daily_import_scheduler_available': DAILY_IMPORT_SCHEDULER_AVAILABLE,
        'background_services': services_status,
        'automated_data_sync': data_sync_status,
        'logs_accessible': logs_accessible,
        'log_directory': str(log_dir),
        'development_mode': True,  # Indicates direct deployment mode
        'deployment_type': 'direct'  # vs 'github-actions'
    }

    logger.info(f"Health check: {health_data}")
    return jsonify(health_data), 200 if db_status == 'healthy' else 503

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health/detailed')
def detailed_health_check():
    """Enhanced health check with comprehensive metrics"""
    try:
        start_time = time.time()

        # Database health
        db_status = "healthy"
        db_response_time = 0
        try:
            with FuturesDB() as db:
                start_db = time.time()
                db.cursor.execute("SELECT COUNT(*) FROM trades")
                trade_count = db.cursor.fetchone()[0]
                db.cursor.execute("SELECT COUNT(*) FROM ohlc_data")
                ohlc_count = db.cursor.fetchone()[0]
                db_response_time = time.time() - start_db
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "error"
            trade_count = 0
            ohlc_count = 0

        # System resources
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Background services
        services_status = get_services_status()

        # Cache status
        cache_status = "unavailable"
        cache_stats = {}
        try:
            from services.redis_cache_service import get_cache_stats
            cache_stats = get_cache_stats()
            cache_status = "healthy" if cache_stats.get('connected', False) else "error"
        except Exception as e:
            logger.debug(f"Cache status check failed: {e}")

        # Data sync status (DEPRECATED - no longer started automatically)
        # OHLC sync is now triggered after daily CSV imports
        data_sync_status = {
            'is_running': False,
            'deprecated': True,
            'note': 'OHLC sync now triggered by Daily Import Scheduler after CSV imports'
        }

        # File watcher status (DEPRECATED - prefer Daily Import Scheduler)
        file_watcher_running = file_watcher.is_running() if FILE_WATCHER_AVAILABLE else False

        # NinjaTrader import service status (Task 5.6)
        ninjatrader_import_running = False
        ninjatrader_import_status = {}
        if NINJATRADER_IMPORT_AVAILABLE:
            try:
                ninjatrader_import_status = ninjatrader_import_service.get_status()
                ninjatrader_import_running = ninjatrader_import_status.get('running', False)
            except Exception as e:
                logger.error(f"NinjaTrader import status check failed: {e}")
                ninjatrader_import_status = {'error': str(e)}

        health_data = {
            'status': 'healthy' if db_status == 'healthy' else 'degraded',
            'response_time_ms': round((time.time() - start_time) * 1000, 2),
            'database': {
                'status': db_status,
                'response_time_ms': round(db_response_time * 1000, 2),
                'trade_count': trade_count,
                'ohlc_count': ohlc_count
            },
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'disk_percent': (disk.used / disk.total) * 100,
                'disk_used_gb': round(disk.used / (1024**3), 2)
            },
            'services': {
                'background_services': services_status,
                'file_watcher': {
                    'running': file_watcher_running,
                    'available': FILE_WATCHER_AVAILABLE,
                    'deprecated': True,
                    'note': 'Use Daily Import Scheduler (2:05pm PT) instead'
                },
                'ninjatrader_import': {
                    'running': ninjatrader_import_running,
                    'available': NINJATRADER_IMPORT_AVAILABLE,
                    'status': ninjatrader_import_status
                },
                'data_sync': {
                    'deprecated': True,
                    'status': data_sync_status
                }
            },
            'cache': {
                'status': cache_status,
                'stats': cache_stats
            },
            'timestamp': time.time()
        }

        # Update Prometheus metrics
        database_query_duration.labels(table='health', operation='check').observe(db_response_time)

        logger.info(f"Detailed health check completed in {health_data['response_time_ms']}ms")

        return jsonify(health_data), 200 if db_status == 'healthy' else 503

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
        }), 503
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

@app.route('/api/background-services/status')
def background_services_status():
    """Get background services status"""
    try:
        status = get_services_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/stats')
def cache_stats():
    """Get cache statistics"""
    try:
        from services.redis_cache_service import get_cache_service
        cache_service = get_cache_service()

        if not cache_service or not cache_service.redis_client:
            return jsonify({'error': 'Cache service not available'}), 503

        stats = cache_service.get_cache_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clean', methods=['POST'])
def cache_clean():
    """Manually trigger cache cleanup"""
    try:
        from services.redis_cache_service import get_cache_service
        cache_service = get_cache_service()

        if not cache_service or not cache_service.redis_client:
            return jsonify({'error': 'Cache service not available'}), 503

        stats = cache_service.clean_expired_cache()
        return jsonify({'message': 'Cache cleanup completed', 'stats': stats}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data-sync/status')
def data_sync_status():
    """Get automated data sync system status"""
    try:
        status = get_data_sync_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data-sync/force/<sync_type>', methods=['POST'])
def force_data_sync_api(sync_type):
    """Force a data sync operation"""
    try:
        valid_types = ['startup', 'hourly', 'daily', 'weekly']
        if sync_type not in valid_types:
            return jsonify({
                'error': f'Invalid sync type. Must be one of: {", ".join(valid_types)}'
            }), 400

        logger.info(f"Force data sync requested: {sync_type}")
        results = force_data_sync(sync_type)

        return jsonify({
            'message': f'{sync_type.title()} data sync completed',
            'results': results
        }), 200
    except Exception as e:
        logger.error(f"Error in force data sync: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gap-filling/force/<instrument>', methods=['POST'])
def force_gap_filling(instrument):
    """Manually trigger gap filling for specific instrument"""
    try:
        from services.background_services import gap_filling_service
        from flask import request

        data = request.get_json() or {}
        timeframes = data.get('timeframes', ['1m', '5m', '15m', '1h', '4h', '1d'])
        days_back = data.get('days_back', 7)

        results = gap_filling_service.force_gap_fill(instrument, timeframes, days_back)
        return jsonify({
            'message': f'Gap filling triggered for {instrument}',
            'results': results
        }), 200
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

# Business Metrics Collection Functions
def record_trade_processed(account: str, instrument: str):
    """Record a trade being processed for monitoring"""
    try:
        trades_processed.labels(account=account, instrument=instrument).inc()
    except Exception as e:
        logger.debug(f"Failed to record trade metric: {e}")

def record_position_created(instrument: str):
    """Record a position being created for monitoring"""
    try:
        positions_created.labels(instrument=instrument).inc()
    except Exception as e:
        logger.debug(f"Failed to record position metric: {e}")

def record_chart_request(instrument: str, timeframe: str):
    """Record a chart data request for monitoring"""
    try:
        chart_requests.labels(instrument=instrument, timeframe=timeframe).inc()
    except Exception as e:
        logger.debug(f"Failed to record chart metric: {e}")

def record_database_query(table: str, operation: str, duration: float):
    """Record database query metrics"""
    try:
        database_queries.labels(table=table, operation=operation).inc()
        database_query_duration.labels(table=table, operation=operation).observe(duration)
    except Exception as e:
        logger.debug(f"Failed to record database metric: {e}")

def record_ohlc_data_points(instrument: str, timeframe: str, count: int):
    """Record OHLC data points being stored"""
    try:
        ohlc_data_points.labels(instrument=instrument, timeframe=timeframe).inc(count)
    except Exception as e:
        logger.debug(f"Failed to record OHLC metric: {e}")

# Alert Management Functions
def check_and_send_alerts():
    """Check system health and send alerts if needed"""
    try:
        import psutil

        alerts_to_send = []

        # CPU Alert
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > 90:
            alerts_to_send.append({
                'severity': 'critical',
                'component': 'system',
                'message': f'Critical CPU usage: {cpu_percent}%'
            })

        # Memory Alert
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            alerts_to_send.append({
                'severity': 'critical',
                'component': 'system',
                'message': f'Critical memory usage: {memory.percent}%'
            })

        # Disk Alert
        disk = psutil.disk_usage('/')
        disk_gb = disk.used / (1024**3)
        if disk_gb > 45:
            alerts_to_send.append({
                'severity': 'critical',
                'component': 'storage',
                'message': f'Critical disk usage: {disk_gb:.1f}GB'
            })

        # Database connectivity
        try:
            with FuturesDB() as db:
                start_time = time.time()
                db.cursor.execute("SELECT 1")
                db_response_time = time.time() - start_time

                if db_response_time > 2.0:
                    alerts_to_send.append({
                        'severity': 'warning',
                        'component': 'database',
                        'message': f'Slow database response: {db_response_time:.2f}s'
                    })
        except Exception as e:
            alerts_to_send.append({
                'severity': 'critical',
                'component': 'database',
                'message': f'Database connection failed: {str(e)}'
            })

        # Send email alerts for critical issues
        for alert in alerts_to_send:
            if alert['severity'] == 'critical':
                send_email_alert(alert)

    except Exception as e:
        logger.error(f"Error checking alerts: {e}")

def send_email_alert(alert_data):
    """Send email alert for critical issues"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        import os

        # Email configuration
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        alert_recipients = os.getenv('ALERT_RECIPIENTS', '').split(',')

        if not smtp_username or not smtp_password or not alert_recipients[0]:
            logger.warning("Email alerting not configured - skipping alert")
            return

        subject = f"[{alert_data['severity'].upper()}] Trading App Alert - {alert_data['component']}"
        body = f"""
Trading Application Alert

Severity: {alert_data['severity'].upper()}
Component: {alert_data['component']}
Message: {alert_data['message']}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}

Please check the monitoring dashboard at /monitoring for more details.
        """

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_username
        msg['To'] = ', '.join(alert_recipients)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Critical alert email sent: {alert_data['message']}")

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")

# Periodic alert checking (runs every 5 minutes)
def start_alert_monitoring():
    """Start background alert monitoring"""
    import schedule

    schedule.every(5).minutes.do(check_and_send_alerts)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)

    alert_thread = threading.Thread(target=run_scheduler, daemon=True)
    alert_thread.start()
    logger.info("Alert monitoring started")

# Start alert monitoring
start_alert_monitoring()

if __name__ == '__main__':
    # Log system information for troubleshooting
    log_system_info()

    # Initialize database schema before any services start
    try:
        logger.info("Initializing database schema...")
        with FuturesDB() as db:
            logger.info("Database schema initialized successfully")
            print("[OK] Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        print(f"[ERROR] Database initialization failed: {e}")
        raise

    # DEPRECATED: File watcher continuous polling for CSV files
    # Trade imports now happen via the Daily Import Scheduler at 2:05pm PT
    # The file watcher is disabled by default to prevent duplicate imports
    # To re-enable (not recommended): set AUTO_IMPORT_ENABLED=true
    if FILE_WATCHER_AVAILABLE and config.auto_import_enabled:
        logger.warning("=" * 80)
        logger.warning("DEPRECATION WARNING: File watcher auto-import is enabled")
        logger.warning("Trade imports should use the Daily Import Scheduler (2:05pm PT)")
        logger.warning("Consider setting AUTO_IMPORT_ENABLED=false")
        logger.warning("=" * 80)
        file_watcher.start()
        logger.info(f"File watcher started - checking every {config.auto_import_interval} seconds")
        print(f"[WARN] File watcher started (deprecated) - checking every {config.auto_import_interval} seconds")
    else:
        logger.info("File watcher disabled (using Daily Import Scheduler at 2:05pm PT)")
        print("File watcher disabled - trade imports scheduled for 2:05pm PT daily")

    # Task 5.4: Start NinjaTrader import background watcher
    # NOTE: This continuous watcher will be deprecated in favor of the daily import scheduler
    # For now, we keep it disabled to avoid conflicts with the new daily import strategy
    # To re-enable: set ENABLE_CONTINUOUS_WATCHER=true in environment
    enable_continuous_watcher = os.getenv('ENABLE_CONTINUOUS_WATCHER', 'false').lower() == 'true'

    if NINJATRADER_IMPORT_AVAILABLE and enable_continuous_watcher:
        try:
            ninjatrader_import_service.start_watcher()
            logger.info("NinjaTrader import background watcher started successfully")
            print(f"NinjaTrader import watcher started (polling every {ninjatrader_import_service._poll_interval} seconds)")
        except Exception as e:
            logger.warning(f"NinjaTrader import watcher failed to start: {e}")
            print(f"Warning: NinjaTrader import watcher failed to start: {e}")
    elif NINJATRADER_IMPORT_AVAILABLE:
        logger.info("NinjaTrader continuous watcher disabled (using daily import scheduler instead)")
        print("NinjaTrader continuous watcher disabled (using daily import scheduler at 2:05pm PT)")
    else:
        logger.info("NinjaTrader import service not available")
        print("NinjaTrader import service not available")

    # Task Group 4: Start Daily Import Scheduler
    if DAILY_IMPORT_SCHEDULER_AVAILABLE:
        try:
            daily_import_scheduler.start()
            logger.info("Daily import scheduler started successfully")
            print(f"[OK] Daily import scheduler started - automatic import at 2:05pm PT")
            print(f"   Next scheduled import: {daily_import_scheduler._get_next_import_time()}")
        except Exception as e:
            logger.warning(f"Daily import scheduler failed to start: {e}")
            print(f"[WARN] Daily import scheduler failed to start: {e}")
    else:
        logger.info("Daily import scheduler not available")
        print("Daily import scheduler not available")

    # Start enhanced background data manager (replaces old gap-filling)
    if BACKGROUND_DATA_CONFIG['enabled']:
        try:
            background_data_manager.start()
            logger.info("Enhanced Background Data Manager started successfully")
            print("Enhanced Background Data Manager started (batch processing, cache-only charts)")
        except Exception as e:
            logger.warning(f"Enhanced Background Data Manager failed to start: {e}")
            print(f"Warning: Enhanced Background Data Manager failed to start: {e}")
    else:
        logger.info("Enhanced Background Data Manager is disabled")
        print("Enhanced Background Data Manager is disabled (BACKGROUND_DATA_CONFIG['enabled'] = False)")

    # Start legacy background services for gap-filling and caching (as fallback)
    try:
        start_background_services()
        logger.info("Legacy background services started successfully")
        print("Legacy background services started (gap-filling, cache maintenance)")
    except Exception as e:
        logger.warning(f"Legacy background services failed to start: {e}")
        print(f"Warning: Legacy background services failed to start: {e}")

    # DEPRECATED: Automated data sync system
    # OHLC sync is now triggered automatically after daily CSV imports at 2:05pm PT
    # See: services/daily_import_scheduler.py
    # The AutomatedDataSyncer is no longer started automatically
    logger.info("AutomatedDataSyncer disabled (OHLC sync handled by Daily Import Scheduler)")
    print("AutomatedDataSyncer disabled - OHLC sync triggered after daily imports")

    # Task 5.5: Register cleanup handlers for graceful shutdown
    atexit.register(lambda: background_data_manager.stop())
    atexit.register(stop_background_services)

    # Register NinjaTrader import service cleanup
    if NINJATRADER_IMPORT_AVAILABLE:
        atexit.register(ninjatrader_import_service.stop_watcher)
        logger.info("NinjaTrader import watcher cleanup handler registered")

    # Register Daily Import Scheduler cleanup (Task Group 4)
    if DAILY_IMPORT_SCHEDULER_AVAILABLE:
        atexit.register(daily_import_scheduler.stop)
        logger.info("Daily import scheduler cleanup handler registered")

    logger.info(f"Starting Flask application on {config.host}:{config.port}")

    try:
        app.run(debug=config.debug, port=config.port, host=config.host)
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        raise
    finally:
        # Stop all services when the app shuts down
        if FILE_WATCHER_AVAILABLE and config.auto_import_enabled:
            logger.info("Stopping file watcher service")
            file_watcher.stop()

        # Stop NinjaTrader import watcher
        if NINJATRADER_IMPORT_AVAILABLE:
            logger.info("Stopping NinjaTrader import watcher")
            ninjatrader_import_service.stop_watcher()

        # Stop Daily Import Scheduler (Task Group 4)
        if DAILY_IMPORT_SCHEDULER_AVAILABLE:
            logger.info("Stopping daily import scheduler")
            daily_import_scheduler.stop()

        logger.info("Stopping background services")
        stop_background_services()

        logger.info("Stopping automated data sync system")
        stop_automated_data_sync()

        logger.info("Application shutdown complete")
