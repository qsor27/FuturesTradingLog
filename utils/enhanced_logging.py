"""
Enhanced Logging Configuration

Implements Gemini's recommendations for:
- Structured logging with context
- Enhanced error handling with recovery
- Performance logging for troubleshooting
"""

import logging
import logging.handlers
import json
import traceback
import time
import functools
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import sys
import os

from config import config


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record):
        # Create base log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add performance metrics if present
        if hasattr(record, 'duration'):
            log_entry['performance'] = {
                'duration_ms': record.duration,
                'operation': getattr(record, 'operation', 'unknown')
            }
        
        # Add context if present
        if hasattr(record, 'context'):
            log_entry['context'] = record.context
        
        return json.dumps(log_entry)


class ContextFilter(logging.Filter):
    """Filter to add contextual information to log records"""
    
    def __init__(self, context: Dict[str, Any] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record):
        # Add context to record
        if self.context:
            if not hasattr(record, 'context'):
                record.context = {}
            record.context.update(self.context)
        
        # Add process and thread info
        record.process_id = os.getpid()
        record.thread_id = record.thread
        
        return True


class PerformanceLogger:
    """Logger for performance monitoring and debugging"""
    
    def __init__(self, logger_name: str = 'performance'):
        self.logger = logging.getLogger(logger_name)
    
    def log_operation(self, operation: str, duration_ms: float, 
                     context: Dict[str, Any] = None, 
                     success: bool = True):
        """Log a timed operation"""
        extra = {
            'duration': duration_ms,
            'operation': operation,
            'context': context or {},
            'success': success
        }
        
        if duration_ms > 1000:  # Slow operation
            self.logger.warning(f"Slow operation: {operation} took {duration_ms:.1f}ms", extra=extra)
        else:
            self.logger.info(f"Operation: {operation} completed in {duration_ms:.1f}ms", extra=extra)
    
    def log_database_query(self, query_type: str, table: str, 
                          duration_ms: float, rows_affected: int = 0):
        """Log database query performance"""
        context = {
            'query_type': query_type,
            'table': table,
            'rows_affected': rows_affected,
            'queries_per_second': 1000 / duration_ms if duration_ms > 0 else 0
        }
        
        self.log_operation(f"db_{query_type}_{table}", duration_ms, context)
    
    def log_cache_operation(self, operation: str, cache_key: str, 
                           hit: bool, duration_ms: float):
        """Log cache operation performance"""
        context = {
            'cache_key': cache_key,
            'cache_hit': hit,
            'operation': operation
        }
        
        self.log_operation(f"cache_{operation}", duration_ms, context, hit)
    
    def log_file_operation(self, operation: str, file_path: str, 
                          file_size: int, duration_ms: float):
        """Log file operation performance"""
        context = {
            'file_path': file_path,
            'file_size_bytes': file_size,
            'throughput_mbps': (file_size / (1024 * 1024)) / (duration_ms / 1000) if duration_ms > 0 else 0
        }
        
        self.log_operation(f"file_{operation}", duration_ms, context)


def setup_enhanced_logging(log_level: str = 'INFO', 
                          enable_structured: bool = True,
                          enable_performance: bool = True) -> Dict[str, logging.Logger]:
    """
    Set up enhanced logging configuration.
    
    Returns:
        Dictionary of configured loggers
    """
    # Ensure log directory exists
    log_dir = config.data_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    if enable_structured:
        structured_formatter = StructuredFormatter()
        human_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        human_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
    
    # Console handler (human readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(human_formatter)
    root_logger.addHandler(console_handler)
    
    # Application log file (structured if enabled)
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    app_handler.setLevel(logging.DEBUG)
    if enable_structured:
        app_handler.setFormatter(structured_formatter)
    else:
        app_handler.setFormatter(human_formatter)
    root_logger.addHandler(app_handler)
    
    # Error log file (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'error.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(human_formatter)
    root_logger.addHandler(error_handler)
    
    # Create specialized loggers
    loggers = {}
    
    # Performance logger
    if enable_performance:
        perf_logger = logging.getLogger('performance')
        perf_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'performance.log',
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=3
        )
        perf_handler.setLevel(logging.INFO)
        if enable_structured:
            perf_handler.setFormatter(structured_formatter)
        else:
            perf_handler.setFormatter(human_formatter)
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        loggers['performance'] = PerformanceLogger()
    
    # Security logger
    security_logger = logging.getLogger('security')
    security_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'security.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(human_formatter)
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    loggers['security'] = security_logger
    
    # Cache logger
    cache_logger = logging.getLogger('cache')
    cache_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'cache.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3
    )
    cache_handler.setLevel(logging.DEBUG)
    if enable_structured:
        cache_handler.setFormatter(structured_formatter)
    else:
        cache_handler.setFormatter(human_formatter)
    cache_logger.addHandler(cache_handler)
    cache_logger.setLevel(logging.DEBUG)
    loggers['cache'] = cache_logger
    
    # Position processing logger
    position_logger = logging.getLogger('position_service')
    loggers['position'] = position_logger
    
    # File processing logger
    file_logger = logging.getLogger('file_processing')
    loggers['file_processing'] = file_logger
    
    return loggers


def log_performance(operation_name: str = None, 
                   logger: logging.Logger = None,
                   context: Dict[str, Any] = None):
    """
    Decorator to log function performance.
    
    Usage:
        @log_performance("database_query")
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine operation name
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Get logger
            log = logger or logging.getLogger('performance')
            
            # Start timing
            start_time = time.time()
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                success = True
                
            except Exception as e:
                success = False
                # Log the error with context
                log.error(f"Operation {op_name} failed: {str(e)}", 
                         extra={'context': context, 'operation': op_name})
                raise
            
            finally:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Log performance
                extra = {
                    'duration': duration_ms,
                    'operation': op_name,
                    'context': context or {},
                    'success': success
                }
                
                if duration_ms > 1000:  # Slow operation
                    log.warning(f"Slow operation: {op_name} took {duration_ms:.1f}ms", extra=extra)
                else:
                    log.debug(f"Operation: {op_name} completed in {duration_ms:.1f}ms", extra=extra)
            
            return result
        return wrapper
    return decorator


def log_with_context(context: Dict[str, Any]):
    """
    Decorator to add context to all log messages within a function.
    
    Usage:
        @log_with_context({"user_id": "123", "operation": "import"})
        def my_function():
            logger.info("This will include context")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger for this function
            logger = logging.getLogger(func.__module__)
            
            # Create context filter
            context_filter = ContextFilter(context)
            
            # Add filter to all handlers
            original_filters = []
            for handler in logger.handlers:
                original_filters.append(handler.filters.copy())
                handler.addFilter(context_filter)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Restore original filters
                for handler, original in zip(logger.handlers, original_filters):
                    handler.filters = original
        
        return wrapper
    return decorator


def handle_errors_gracefully(logger: logging.Logger = None, 
                            default_return: Any = None,
                            reraise: bool = True):
    """
    Decorator for enhanced error handling with logging.
    
    Usage:
        @handle_errors_gracefully(logger=my_logger, default_return={})
        def risky_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger
            log = logger or logging.getLogger(func.__module__)
            
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                # Log detailed error information
                error_context = {
                    'function': f"{func.__module__}.{func.__name__}",
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()),
                    'exception_type': type(e).__name__,
                    'exception_message': str(e)
                }
                
                log.error(
                    f"Error in {func.__name__}: {str(e)}",
                    exc_info=True,
                    extra={'context': error_context}
                )
                
                if reraise:
                    raise
                else:
                    log.warning(f"Returning default value due to error in {func.__name__}")
                    return default_return
        
        return wrapper
    return decorator


class SecurityLogger:
    """Specialized logger for security events"""
    
    def __init__(self):
        self.logger = logging.getLogger('security')
    
    def log_file_upload(self, filename: str, file_size: int, 
                       source_ip: str, success: bool, 
                       validation_errors: list = None):
        """Log file upload security event"""
        context = {
            'event_type': 'file_upload',
            'filename': filename,
            'file_size': file_size,
            'source_ip': source_ip,
            'success': success,
            'validation_errors': validation_errors or []
        }
        
        if success:
            self.logger.info(f"File upload successful: {filename}", extra={'context': context})
        else:
            self.logger.warning(f"File upload failed: {filename}", extra={'context': context})
    
    def log_cache_invalidation(self, operation: str, keys_affected: int, 
                              trigger: str, success: bool):
        """Log cache invalidation security event"""
        context = {
            'event_type': 'cache_invalidation',
            'operation': operation,
            'keys_affected': keys_affected,
            'trigger': trigger,
            'success': success
        }
        
        self.logger.info(f"Cache invalidation: {operation}", extra={'context': context})
    
    def log_data_validation(self, validation_type: str, items_validated: int,
                           errors_found: int, critical_errors: int = 0):
        """Log data validation security event"""
        context = {
            'event_type': 'data_validation',
            'validation_type': validation_type,
            'items_validated': items_validated,
            'errors_found': errors_found,
            'critical_errors': critical_errors
        }
        
        if critical_errors > 0:
            self.logger.error(f"Critical validation errors found: {validation_type}", extra={'context': context})
        elif errors_found > 0:
            self.logger.warning(f"Validation errors found: {validation_type}", extra={'context': context})
        else:
            self.logger.info(f"Validation completed successfully: {validation_type}", extra={'context': context})


# Global instances
performance_logger = None
security_logger = None

def get_performance_logger() -> PerformanceLogger:
    """Get global performance logger instance"""
    global performance_logger
    if performance_logger is None:
        performance_logger = PerformanceLogger()
    return performance_logger

def get_security_logger() -> SecurityLogger:
    """Get global security logger instance"""
    global security_logger
    if security_logger is None:
        security_logger = SecurityLogger()
    return security_logger


if __name__ == "__main__":
    # Test the enhanced logging setup
    print("Testing enhanced logging configuration...")
    
    # Set up logging
    loggers = setup_enhanced_logging(enable_structured=True, enable_performance=True)
    
    # Test basic logging
    logger = logging.getLogger(__name__)
    logger.info("Enhanced logging test started")
    
    # Test performance logging
    @log_performance("test_operation")
    def test_function():
        time.sleep(0.1)  # Simulate work
        return "success"
    
    result = test_function()
    
    # Test error handling
    @handle_errors_gracefully(default_return="error_handled")
    def error_function():
        raise ValueError("Test error")
    
    result = error_function()
    
    # Test security logging
    security = get_security_logger()
    security.log_file_upload("test.csv", 1024, "127.0.0.1", True)
    
    print("✓ Enhanced logging test completed")