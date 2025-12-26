"""
Environment-based configuration system
Provides different configurations for development, testing, and production
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import json


class BaseConfig(ABC):
    """Base configuration class"""
    
    def __init__(self):
        self._validate_environment()
        self._setup_paths()
        self._load_secrets()
    
    @abstractmethod
    def _validate_environment(self):
        """Validate environment-specific requirements"""
        pass
    
    def _setup_paths(self):
        """Setup directory paths"""
        # Base data directory
        self.data_dir = Path(os.getenv('DATA_DIR', self.get_default_data_dir()))
        
        # Subdirectories
        self.db_dir = self.data_dir / 'db'
        self.config_dir = self.data_dir / 'config'
        self.charts_dir = self.data_dir / 'charts'
        self.logs_dir = self.data_dir / 'logs'
        self.archive_dir = self.data_dir / 'archive'
        
        # Create directories if they don't exist
        for directory in [self.db_dir, self.config_dir, self.charts_dir, self.logs_dir, self.archive_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.db_path = self.db_dir / 'futures_trades.db'
        self.instrument_config = self.config_dir / 'instrument_multipliers.json'
        self.trade_log = self.data_dir / 'trade_log.csv'
    
    def _load_secrets(self):
        """Load secrets from environment or secure storage"""
        self.secret_key = os.getenv('FLASK_SECRET_KEY', self.get_default_secret_key())
        self.redis_password = os.getenv('REDIS_PASSWORD', '')
        self.database_encryption_key = os.getenv('DB_ENCRYPTION_KEY', '')
    
    @abstractmethod
    def get_default_data_dir(self) -> str:
        """Get default data directory for this environment"""
        pass
    
    @abstractmethod
    def get_default_secret_key(self) -> str:
        """Get default secret key for this environment"""
        pass
    
    # Flask configuration
    @property
    def flask_config(self) -> Dict[str, Any]:
        """Return Flask configuration dictionary"""
        return {
            'SECRET_KEY': self.secret_key,
            'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max file size
            'PERMANENT_SESSION_LIFETIME': 3600,  # 1 hour
            'SESSION_COOKIE_SECURE': self.use_https,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
        }
    
    # Database configuration
    @property
    def database_config(self) -> Dict[str, Any]:
        """Return database configuration"""
        return {
            'path': str(self.db_path),
            'wal_mode': True,
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
            'cache_size': -64000,  # 64MB cache
            'temp_store': 'memory',
            'mmap_size': 1073741824,  # 1GB memory map
        }
    
    # Redis configuration
    @property
    def redis_config(self) -> Dict[str, Any]:
        """Return Redis configuration"""
        return {
            'url': self.redis_url,
            'password': self.redis_password,
            'decode_responses': True,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'connection_pool_kwargs': {
                'max_connections': 20,
                'retry_on_timeout': True,
            }
        }
    
    # Logging configuration
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Return logging configuration"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
                'detailed': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
                }
            },
            'handlers': {
                'default': {
                    'level': self.log_level,
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout'
                },
                'file': {
                    'level': 'INFO',
                    'formatter': 'detailed',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(self.logs_dir / 'app.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5
                },
                'error_file': {
                    'level': 'ERROR',
                    'formatter': 'detailed',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(self.logs_dir / 'error.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5
                }
            },
            'loggers': {
                '': {
                    'handlers': ['default', 'file'],
                    'level': self.log_level,
                    'propagate': False
                },
                'error': {
                    'handlers': ['error_file'],
                    'level': 'ERROR',
                    'propagate': True
                }
            }
        }
    
    # Abstract properties that subclasses must implement
    @property
    @abstractmethod
    def debug(self) -> bool:
        """Return True if in debug mode"""
        pass
    
    @property
    @abstractmethod
    def log_level(self) -> str:
        """Return logging level"""
        pass
    
    @property
    @abstractmethod
    def use_https(self) -> bool:
        """Return True if HTTPS should be used"""
        pass
    
    @property
    @abstractmethod
    def redis_url(self) -> str:
        """Return Redis connection URL"""
        pass


class DevelopmentConfig(BaseConfig):
    """Development environment configuration"""
    
    def _validate_environment(self):
        """Validate development environment"""
        # Development environment should have minimal requirements
        pass
    
    def get_default_data_dir(self) -> str:
        """Get default data directory for development"""
        return str(Path.home() / 'FuturesTradingLog' / 'data')
    
    def get_default_secret_key(self) -> str:
        """Get default secret key for development"""
        return 'dev-secret-key-change-in-production'
    
    @property
    def debug(self) -> bool:
        return True
    
    @property
    def log_level(self) -> str:
        return 'DEBUG'
    
    @property
    def use_https(self) -> bool:
        return False
    
    @property
    def redis_url(self) -> str:
        return os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    @property
    def host(self) -> str:
        return os.getenv('FLASK_HOST', '127.0.0.1')
    
    @property
    def port(self) -> int:
        return int(os.getenv('FLASK_PORT', 5000))
    
    @property
    def auto_import_enabled(self) -> bool:
        return os.getenv('AUTO_IMPORT_ENABLED', 'false').lower() == 'true'
    
    @property
    def auto_import_interval(self) -> int:
        return int(os.getenv('AUTO_IMPORT_INTERVAL', 30))  # 30 seconds for dev
    
    @property
    def cache_enabled(self) -> bool:
        return os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    
    @property
    def cache_ttl_days(self) -> int:
        return int(os.getenv('CACHE_TTL_DAYS', 1))  # 1 day for dev


class TestingConfig(BaseConfig):
    """Testing environment configuration"""
    
    def _validate_environment(self):
        """Validate testing environment"""
        # Testing environment should be isolated
        pass
    
    def get_default_data_dir(self) -> str:
        """Get default data directory for testing"""
        return '/tmp/futures_trading_test'
    
    def get_default_secret_key(self) -> str:
        """Get default secret key for testing"""
        return 'test-secret-key'
    
    @property
    def debug(self) -> bool:
        return True
    
    @property
    def log_level(self) -> str:
        return 'WARNING'  # Less verbose for tests
    
    @property
    def use_https(self) -> bool:
        return False
    
    @property
    def redis_url(self) -> str:
        return os.getenv('REDIS_URL', 'redis://localhost:6379/1')  # Use different DB
    
    @property
    def host(self) -> str:
        return '127.0.0.1'
    
    @property
    def port(self) -> int:
        return 5001  # Different port for tests
    
    @property
    def auto_import_enabled(self) -> bool:
        return False  # Disable auto import in tests
    
    @property
    def auto_import_interval(self) -> int:
        return 300
    
    @property
    def cache_enabled(self) -> bool:
        return False  # Disable cache in tests for consistency
    
    @property
    def cache_ttl_days(self) -> int:
        return 1


class ProductionConfig(BaseConfig):
    """Production environment configuration"""
    
    def _validate_environment(self):
        """Validate production environment"""
        required_env_vars = [
            'FLASK_SECRET_KEY',
            'DATA_DIR',
            'REDIS_URL'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    def get_default_data_dir(self) -> str:
        """Get default data directory for production"""
        return '/app/data'
    
    def get_default_secret_key(self) -> str:
        """Get default secret key for production"""
        # In production, this should never be used as FLASK_SECRET_KEY is required
        raise ValueError("FLASK_SECRET_KEY must be set in production")
    
    @property
    def debug(self) -> bool:
        return False
    
    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def use_https(self) -> bool:
        return os.getenv('USE_HTTPS', 'true').lower() == 'true'
    
    @property
    def redis_url(self) -> str:
        return os.getenv('REDIS_URL')
    
    @property
    def host(self) -> str:
        return os.getenv('FLASK_HOST', '0.0.0.0')
    
    @property
    def port(self) -> int:
        return int(os.getenv('FLASK_PORT', 5000))
    
    @property
    def auto_import_enabled(self) -> bool:
        return os.getenv('AUTO_IMPORT_ENABLED', 'false').lower() == 'true'
    
    @property
    def auto_import_interval(self) -> int:
        return int(os.getenv('AUTO_IMPORT_INTERVAL', 300))  # 5 minutes
    
    @property
    def cache_enabled(self) -> bool:
        return os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    
    @property
    def cache_ttl_days(self) -> int:
        return int(os.getenv('CACHE_TTL_DAYS', 14))


class ConfigurationManager:
    """Configuration manager that selects appropriate config based on environment"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration based on environment"""
        env = os.getenv('FLASK_ENV', 'development').lower()
        
        config_classes = {
            'development': DevelopmentConfig,
            'dev': DevelopmentConfig,
            'testing': TestingConfig,
            'test': TestingConfig,
            'test_local': TestingConfig,
            'production': ProductionConfig,
            'prod': ProductionConfig,
        }
        
        config_class = config_classes.get(env, DevelopmentConfig)
        self._config = config_class()
    
    @property
    def config(self) -> BaseConfig:
        """Get current configuration"""
        return self._config
    
    def reload_config(self):
        """Reload configuration (useful for testing)"""
        self._config = None
        self._load_config()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for debugging"""
        return {
            'environment': os.getenv('FLASK_ENV', 'development'),
            'config_class': self._config.__class__.__name__,
            'debug': self._config.debug,
            'data_dir': str(self._config.data_dir),
            'db_path': str(self._config.db_path),
            'log_level': self._config.log_level,
            'cache_enabled': self._config.cache_enabled,
            'auto_import_enabled': self._config.auto_import_enabled,
            'host': self._config.host,
            'port': self._config.port,
        }


# Global configuration manager instance
config_manager = ConfigurationManager()

# Convenience function to get current config
def get_config() -> BaseConfig:
    """Get current configuration"""
    return config_manager.config


# Convenience function to get configuration summary
def get_config_summary() -> Dict[str, Any]:
    """Get configuration summary"""
    return config_manager.get_config_summary()


# Environment validation function
def validate_environment():
    """Validate current environment configuration"""
    try:
        config = get_config()
        
        # Check required directories
        required_dirs = [config.data_dir, config.db_dir, config.config_dir, 
                        config.logs_dir, config.archive_dir]
        
        for directory in required_dirs:
            if not directory.exists():
                raise ValueError(f"Required directory does not exist: {directory}")
            if not directory.is_dir():
                raise ValueError(f"Path is not a directory: {directory}")
        
        # Check database path
        if config.db_path.exists() and not config.db_path.is_file():
            raise ValueError(f"Database path is not a file: {config.db_path}")
        
        # Check instrument config
        if config.instrument_config.exists():
            try:
                with open(config.instrument_config, 'r') as f:
                    json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ValueError(f"Invalid instrument config: {e}")
        
        return True
        
    except Exception as e:
        raise ValueError(f"Environment validation failed: {e}")


# Create default instrument config if it doesn't exist
def create_default_instrument_config():
    """Create default instrument multipliers config"""
    config = get_config()
    
    if not config.instrument_config.exists():
        default_multipliers = {
            'ES': 50.0,
            'NQ': 20.0,
            'YM': 5.0,
            'RTY': 50.0,
            'CL': 1000.0,
            'GC': 100.0,
            'SI': 5000.0,
            'ZN': 1000.0,
            'ZB': 1000.0,
            'ZS': 50.0,
            'ZC': 50.0,
            'ZW': 50.0,
            'NG': 10000.0,
            'HG': 25000.0,
            'EUR': 125000.0,
            'GBP': 62500.0,
            'JPY': 12500000.0,
            'CHF': 125000.0,
            'CAD': 100000.0,
            'AUD': 100000.0
        }
        
        with open(config.instrument_config, 'w') as f:
            json.dump(default_multipliers, f, indent=2)
        
        print(f"Created default instrument config: {config.instrument_config}")


# Initialize configuration on import
try:
    validate_environment()
    create_default_instrument_config()
except Exception as e:
    print(f"Configuration warning: {e}")