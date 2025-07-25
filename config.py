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
        
        # Create directories if they don't exist
        for directory in [self.db_dir, self.config_dir, self.charts_dir, self.logs_dir, self.archive_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Database path
        self.db_path = self.db_dir / 'futures_trades.db'
        
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
        """Return cache TTL in days (default: 14 days)"""
        return int(os.getenv('CACHE_TTL_DAYS', 14))

# Timeframe configuration constants
SUPPORTED_TIMEFRAMES = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
TIMEFRAME_PREFERENCE_ORDER = ['1h', '1d', '15m', '5m', '4h', '1m', '3m']

# yfinance timeframe mapping
YFINANCE_TIMEFRAME_MAP = {
    '1m': '1m',
    '3m': '3m', 
    '5m': '5m',
    '15m': '15m',
    '1h': '1h',
    '4h': '4h',
    '1d': '1d'
}

# Create global config instance
config = Config()