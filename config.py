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
            # Use configured path for production
            self.data_dir = Path(os.getenv('DATA_DIR', 'C:/Containers/FuturesTradingLog/data'))
        
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
        return os.getenv('FLASK_ENV') == 'development'
        
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

# Create global config instance
config = Config()