"""
Centralized logging configuration for the Futures Trading Log application.
All logs are written to the data/logs directory for easy troubleshooting.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from config import config

def setup_application_logging():
    """
    Configure application-wide logging to data/logs directory.
    
    Creates multiple log files:
    - app.log: Main application log (Flask routes, general operations)
    - error.log: Error-only log for quick troubleshooting
    - file_watcher.log: File monitoring and import operations (created by file_watcher.py)
    - database.log: Database operations and performance
    """
    
    # Ensure logs directory exists
    log_dir = config.data_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 1. Main application log file (all messages)
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(app_handler)
    
    # 2. Error-only log file (errors and above)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'error.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # 3. Console output (for development)
    if config.debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
    
    # 4. Database logger (separate file for database operations)
    db_logger = logging.getLogger('database')
    db_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'database.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3
    )
    db_handler.setLevel(logging.INFO)
    db_handler.setFormatter(detailed_formatter)
    db_logger.addHandler(db_handler)
    db_logger.propagate = False  # Don't send to root logger
    
    # 5. Flask logger configuration
    flask_logger = logging.getLogger('werkzeug')
    flask_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'flask.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3
    )
    flask_handler.setLevel(logging.INFO)
    flask_handler.setFormatter(simple_formatter)
    flask_logger.addHandler(flask_handler)
    
    # Log the logging setup
    logging.info("Application logging configured successfully")
    logging.info(f"Log files location: {log_dir}")
    logging.info("Available log files: app.log, error.log, database.log, flask.log, file_watcher.log")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

def log_system_info():
    """Log system information for troubleshooting"""
    logger = get_logger(__name__)
    
    logger.info("=== Futures Trading Log Application Started ===")
    logger.info(f"Data directory: {config.data_dir}")
    logger.info(f"Database path: {config.db_path}")
    logger.info(f"Debug mode: {config.debug}")
    logger.info(f"Flask host: {config.host}")
    logger.info(f"Flask port: {config.port}")
    
    # Log environment variables
    env_vars = ['DATA_DIR', 'FLASK_ENV', 'AUTO_IMPORT_ENABLED', 'AUTO_IMPORT_INTERVAL']
    for var in env_vars:
        value = os.getenv(var, 'Not set')
        logger.info(f"Environment {var}: {value}")

def log_error_with_context(logger: logging.Logger, error: Exception, context: str = ""):
    """
    Log an error with additional context for troubleshooting.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context about when/where the error occurred
    """
    logger.error(f"ERROR: {context}")
    logger.error(f"Exception type: {type(error).__name__}")
    logger.error(f"Exception message: {str(error)}")
    if hasattr(error, '__traceback__'):
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")