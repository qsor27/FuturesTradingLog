import os
from pathlib import Path

class Config:
    """Application configuration"""
    
    def __init__(self):
        # Get base data directory from environment or use default
        if os.getenv('FLASK_ENV') == 'testing':
            # Use /app/data in Docker test environment
            self.data_dir = Path('/app/data')
        else:
            # Use configured path for production with cross-platform default
            default_data_dir = str(Path.home() / 'FuturesTradingLog' / 'data')
            self.data_dir = Path(os.getenv('DATA_DIR', default_data_dir))
        
        # Ensure all required directories exist
        self.db_dir = self.data_dir / 'db'
        self.config_dir = self.data_dir / 'config'
        self.charts_dir = self.data_dir / 'charts'
        self.logs_dir = self.data_dir / 'logs'
        self.archive_dir = self.data_dir / 'archive'
        
        # Create directories if they don't exist (handle permission errors gracefully)
        for directory in [self.db_dir, self.config_dir, self.charts_dir, self.logs_dir, self.archive_dir]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                # If we can't create the directory, check if it already exists
                if not directory.exists():
                    raise PermissionError(f"Cannot create directory {directory} and it doesn't exist")
                # If it exists but we can't write to it, warn but continue
                if not os.access(directory, os.W_OK):
                    print(f"Warning: Directory {directory} exists but is not writable")
            except Exception as e:
                print(f"Warning: Could not ensure directory {directory} exists: {e}")
        
        # Database path - using clean database without WAL issues
        self.db_path = self.db_dir / 'futures_trades_clean.db'
        
        # Config files
        self.instrument_config = self.config_dir / 'instrument_multipliers.json'
        
        # Trade log file
        self.trade_log = self.data_dir / 'trade_log.csv'
        
    @property
    def debug(self) -> bool:
        """Return True if in debug mode"""
        return os.getenv('FLASK_ENV') in ('development', 'test_local')
        
    def get_chart_path(self, filename: str) -> Path:
        """Get full path for a chart file"""
        return self.charts_dir / filename
        
    def get_log_path(self, filename: str) -> Path:
        """Get full path for a log file"""
        return self.logs_dir / filename

    @property
    def flask_config(self) -> dict:
        """Return Flask configuration dictionary"""
        return {
            'SECRET_KEY': os.getenv('FLASK_SECRET_KEY', 'dev'),
            'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max file size
        }

    @property
    def host(self) -> str:
        """Return host to bind to"""
        return os.getenv('FLASK_HOST', '0.0.0.0')

    @property
    def port(self) -> int:
        """Return port to bind to"""
        return int(os.getenv('FLASK_PORT', 5000))

    @property
    def auto_import_enabled(self) -> bool:
        """Return True if automatic import is enabled (default: true)"""
        return os.getenv('AUTO_IMPORT_ENABLED', 'true').lower() == 'true'

    @property
    def auto_import_interval(self) -> int:
        """Return auto import check interval in seconds (default 5 minutes)"""
        return int(os.getenv('AUTO_IMPORT_INTERVAL', 300))

    @property
    def redis_url(self) -> str:
        """Return Redis connection URL"""
        return os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    @property
    def cache_enabled(self) -> bool:
        """Return True if caching is enabled (default: true)"""
        return os.getenv('CACHE_ENABLED', 'true').lower() == 'true'

    @property
    def cache_ttl_days(self) -> int:
        """Return cache TTL in days (default: 30 days for more aggressive caching)"""
        return int(os.getenv('CACHE_TTL_DAYS', 30))

    @property
    def use_priority_timeframes(self) -> bool:
        """Return True to use priority timeframes (6) instead of all timeframes (18)

        Priority timeframes reduce API calls by 67% while covering all major trading styles.
        Set OHLC_USE_PRIORITY_TIMEFRAMES=false to fetch all 18 timeframes (default: true)
        """
        return os.getenv('OHLC_USE_PRIORITY_TIMEFRAMES', 'true').lower() == 'true'

# Timeframe configuration constants (expanded to support all 18 Yahoo Finance timeframes)
SUPPORTED_TIMEFRAMES = [
    '1m', '2m', '5m', '15m', '30m', '60m', '90m',  # Minute intervals
    '1h', '2h', '4h', '6h', '8h', '12h',            # Hourly intervals
    '1d', '5d', '1wk', '1mo', '3mo'                 # Daily and longer
]

# yfinance timeframe mapping (expanded to support all 18 timeframes)
YFINANCE_TIMEFRAME_MAP = {
    '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
    '60m': '60m', '90m': '90m',
    '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
    '1d': '1d', '5d': '5d', '1wk': '1wk', '1mo': '1mo', '3mo': '3mo',
    '3m': '5m'  # Backward compatibility
}

# Background processing configuration
BACKGROUND_DATA_CONFIG = {
    'enabled': True,
    'max_concurrent_instruments': int(os.getenv('BG_MAX_CONCURRENT_INSTRUMENTS', 3)),
    'priority_update_interval': int(os.getenv('BG_PRIORITY_UPDATE_INTERVAL', 120)),  # 2 minutes
    'full_update_interval': int(os.getenv('BG_FULL_UPDATE_INTERVAL', 300)),         # 5 minutes
    'cache_hit_target': float(os.getenv('BG_CACHE_HIT_TARGET', 0.99)),              # 99%
    'batch_timeout': int(os.getenv('BG_BATCH_TIMEOUT', 300)),                       # 5 minutes
    'real_time_gap_detection': os.getenv('BG_REALTIME_GAP_DETECTION', 'true').lower() == 'true',
    'user_activity_tracking': os.getenv('BG_USER_ACTIVITY_TRACKING', 'true').lower() == 'true',
    'priority_instruments': os.getenv('BG_PRIORITY_INSTRUMENTS', 'ES,MNQ,YM').split(','),
    'all_timeframes': SUPPORTED_TIMEFRAMES
}

# Page load optimization configuration  
PAGE_LOAD_CONFIG = {
    'cache_only_mode': os.getenv('PAGE_CACHE_ONLY_MODE', 'true').lower() == 'true',
    'graceful_degradation': os.getenv('PAGE_GRACEFUL_DEGRADATION', 'true').lower() == 'true',
    'cache_status_indicators': os.getenv('PAGE_CACHE_STATUS_INDICATORS', 'true').lower() == 'true',
    'preload_user_instruments': os.getenv('PAGE_PRELOAD_USER_INSTRUMENTS', 'true').lower() == 'true',
    'cache_hit_target': float(os.getenv('PAGE_CACHE_HIT_TARGET', 0.99))
}

YAHOO_FINANCE_CONFIG = {
    'rate_limiting': {
        'adaptive_enabled': True,
        'base_delay': 0.8,
        'max_delay': 30.0,
        'success_window': 100,
        'failure_threshold': 0.1,
        'batch_delay_multiplier': 0.3
    },
    'batch_processing': {
        'max_concurrent_instruments': 3,
        'timeframes_per_batch': 7,
        'cache_check_batch_size': 50,
        'priority_instruments': ['ES', 'MNQ', 'YM'],
        'batch_timeout': 300
    },
    'error_handling': {
        'circuit_breaker_threshold': 5,
        'circuit_breaker_timeout': 300,
        'max_retries': 5,
        'retry_delays': [1, 3, 8, 15, 30],
        'batch_failure_threshold': 0.3
    },
    'network': {
        'connect_timeout': 8,
        'read_timeout': 25,
        'pool_connections': 15,
        'pool_maxsize': 30,
        'session_reuse': True
    },
    'data_quality': {
        'validation_enabled': True,
        'min_completeness_score': 0.95,
        'max_gap_tolerance': 5,
        'batch_validation': True
    },
    'scalability': {
        'auto_scaling_enabled': True,
        'max_instruments': 100,
        'cache_warming_enabled': True,
        'background_update_interval': 300,
        'incremental_update_interval': 120,
        'real_time_gap_detection': True,
        'user_activity_tracking': True
    },
    'page_load_optimization': {
        'cache_only_mode': True,
        'graceful_degradation': True,
        'cache_status_indicators': True,
        'preload_user_instruments': True,
        'cache_hit_target': 0.99
    }
}

# Create global config instance
config = Config()