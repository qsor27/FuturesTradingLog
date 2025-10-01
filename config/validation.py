"""
Configuration validation system
Validates configuration values, environment setup, and system dependencies
"""

import os
import json
import sqlite3
import logging

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import subprocess
import sys

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation check"""
    name: str
    level: ValidationLevel
    message: str
    suggestion: Optional[str] = None
    passed: bool = False
    details: Optional[Dict[str, Any]] = None


class ConfigValidator:
    """Configuration validation system"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / 'FuturesTradingLog' / 'data' / 'config'
        self.results: List[ValidationResult] = []
    
    def validate_all(self) -> List[ValidationResult]:
        """Run all validation checks"""
        self.results = []
        
        # Core validations
        self._validate_environment_variables()
        self._validate_directories()
        self._validate_database()
        self._validate_redis()
        self._validate_config_files()
        self._validate_dependencies()
        self._validate_permissions()
        self._validate_network()
        self._validate_system_resources()
        
        return self.results
    
    def _add_result(self, name: str, level: ValidationLevel, message: str, 
                   suggestion: Optional[str] = None, passed: bool = False,
                   details: Optional[Dict[str, Any]] = None):
        """Add a validation result"""
        result = ValidationResult(
            name=name,
            level=level,
            message=message,
            suggestion=suggestion,
            passed=passed,
            details=details
        )
        self.results.append(result)
    
    def _validate_environment_variables(self):
        """Validate environment variables"""
        env = os.getenv('FLASK_ENV', 'development')
        
        # Check FLASK_ENV
        valid_envs = ['development', 'testing', 'production']
        if env not in valid_envs:
            self._add_result(
                'flask_env',
                ValidationLevel.WARNING,
                f"Unknown FLASK_ENV value: {env}",
                f"Set FLASK_ENV to one of: {', '.join(valid_envs)}"
            )
        else:
            self._add_result(
                'flask_env',
                ValidationLevel.INFO,
                f"FLASK_ENV is set to {env}",
                passed=True
            )
        
        # Validate production-specific environment variables
        if env == 'production':
            required_prod_vars = ['FLASK_SECRET_KEY', 'DATA_DIR', 'REDIS_URL']
            for var in required_prod_vars:
                if not os.getenv(var):
                    self._add_result(
                        f'env_var_{var.lower()}',
                        ValidationLevel.ERROR,
                        f"Required environment variable {var} is not set",
                        f"Set {var} environment variable for production"
                    )
                else:
                    self._add_result(
                        f'env_var_{var.lower()}',
                        ValidationLevel.INFO,
                        f"Environment variable {var} is set",
                        passed=True
                    )
        
        # Validate optional environment variables
        optional_vars = {
            'FLASK_HOST': {'default': '0.0.0.0', 'validator': self._validate_host},
            'FLASK_PORT': {'default': '5000', 'validator': self._validate_port},
            'CACHE_TTL_DAYS': {'default': '14', 'validator': self._validate_positive_int},
            'AUTO_IMPORT_INTERVAL': {'default': '300', 'validator': self._validate_positive_int}
        }
        
        for var, config in optional_vars.items():
            value = os.getenv(var, config['default'])
            if not config['validator'](value):
                self._add_result(
                    f'env_var_{var.lower()}',
                    ValidationLevel.WARNING,
                    f"Invalid value for {var}: {value}",
                    f"Set {var} to a valid value"
                )
            else:
                self._add_result(
                    f'env_var_{var.lower()}',
                    ValidationLevel.INFO,
                    f"Environment variable {var} is valid",
                    passed=True
                )
    
    def _validate_host(self, host: str) -> bool:
        """Validate host address"""
        if not host:
            return False
        
        # Allow localhost, 0.0.0.0, and valid IP addresses
        if host in ['localhost', '0.0.0.0', '127.0.0.1']:
            return True
        
        # Basic IP validation
        parts = host.split('.')
        if len(parts) == 4:
            try:
                return all(0 <= int(part) <= 255 for part in parts)
            except ValueError:
                return False
        
        return False
    
    def _validate_port(self, port: str) -> bool:
        """Validate port number"""
        try:
            port_num = int(port)
            return 1 <= port_num <= 65535
        except ValueError:
            return False
    
    def _validate_positive_int(self, value: str) -> bool:
        """Validate positive integer"""
        try:
            return int(value) > 0
        except ValueError:
            return False
    
    def _validate_directories(self):
        """Validate directory structure"""
        data_dir = Path(os.getenv('DATA_DIR', str(Path.home() / 'FuturesTradingLog' / 'data')))
        
        required_dirs = {
            'data': data_dir,
            'db': data_dir / 'db',
            'config': data_dir / 'config',
            'logs': data_dir / 'logs',
            'charts': data_dir / 'charts',
            'archive': data_dir / 'archive'
        }
        
        for name, path in required_dirs.items():
            if not path.exists():
                self._add_result(
                    f'directory_{name}',
                    ValidationLevel.ERROR,
                    f"Required directory does not exist: {path}",
                    f"Create directory: mkdir -p {path}"
                )
            elif not path.is_dir():
                self._add_result(
                    f'directory_{name}',
                    ValidationLevel.ERROR,
                    f"Path exists but is not a directory: {path}",
                    f"Remove file and create directory: rm {path} && mkdir -p {path}"
                )
            else:
                # Check write permissions
                if not os.access(path, os.W_OK):
                    self._add_result(
                        f'directory_{name}_write',
                        ValidationLevel.ERROR,
                        f"No write permission for directory: {path}",
                        f"Fix permissions: chmod 755 {path}"
                    )
                else:
                    self._add_result(
                        f'directory_{name}',
                        ValidationLevel.INFO,
                        f"Directory is valid: {path}",
                        passed=True
                    )
    
    def _validate_database(self):
        """Validate database configuration and connectivity"""
        data_dir = Path(os.getenv('DATA_DIR', str(Path.home() / 'FuturesTradingLog' / 'data')))
        db_path = data_dir / 'db' / 'futures_trades.db'
        
        try:
            # Test database connection
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Test basic operations
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            
            # Check if required tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('trades', 'positions', 'ohlc_data')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            self._add_result(
                'database_connectivity',
                ValidationLevel.INFO,
                f"Database connection successful (SQLite {version})",
                passed=True,
                details={'version': version, 'tables': tables}
            )
            
            # Check for required tables
            required_tables = ['trades', 'positions', 'ohlc_data']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                self._add_result(
                    'database_tables',
                    ValidationLevel.WARNING,
                    f"Missing database tables: {', '.join(missing_tables)}",
                    "Run database migration to create missing tables"
                )
            else:
                self._add_result(
                    'database_tables',
                    ValidationLevel.INFO,
                    "All required database tables exist",
                    passed=True
                )
            
        except sqlite3.Error as e:
            self._add_result(
                'database_connectivity',
                ValidationLevel.ERROR,
                f"Database connection failed: {e}",
                f"Check database path and permissions: {db_path}"
            )
    
    def _validate_redis(self):
        """Validate Redis configuration and connectivity"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        try:
            # Test Redis connection
            if not REDIS_AVAILABLE:
                result.success = False
                result.message = "Redis module not available"
                return result
            
            r = redis.from_url(redis_url)
            r.ping()
            
            # Get Redis info
            info = r.info()
            
            self._add_result(
                'redis_connectivity',
                ValidationLevel.INFO,
                f"Redis connection successful (version {info.get('redis_version', 'unknown')})",
                passed=True,
                details={'version': info.get('redis_version'), 'memory': info.get('used_memory_human')}
            )
            
            # Check Redis memory usage
            memory_usage = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            
            if max_memory > 0:
                usage_percent = (memory_usage / max_memory) * 100
                if usage_percent > 80:
                    self._add_result(
                        'redis_memory',
                        ValidationLevel.WARNING,
                        f"Redis memory usage is high: {usage_percent:.1f}%",
                        "Consider increasing Redis memory limit or clearing cache"
                    )
                else:
                    self._add_result(
                        'redis_memory',
                        ValidationLevel.INFO,
                        f"Redis memory usage is healthy: {usage_percent:.1f}%",
                        passed=True
                    )
            
        except Exception as e:
            self._add_result(
                'redis_connectivity',
                ValidationLevel.WARNING,
                f"Redis connection failed: {e}",
                f"Check Redis server status and URL: {redis_url}"
            )
    
    def _validate_config_files(self):
        """Validate configuration files"""
        config_files = {
            'instrument_multipliers.json': self._validate_instrument_multipliers,
            'settings.json': self._validate_settings_file,
            'user_profiles.json': self._validate_profiles_file
        }
        
        for filename, validator in config_files.items():
            file_path = self.config_dir / filename
            
            if file_path.exists():
                if validator(file_path):
                    self._add_result(
                        f'config_file_{filename}',
                        ValidationLevel.INFO,
                        f"Configuration file is valid: {filename}",
                        passed=True
                    )
                else:
                    self._add_result(
                        f'config_file_{filename}',
                        ValidationLevel.ERROR,
                        f"Configuration file is invalid: {filename}",
                        f"Fix or regenerate configuration file: {file_path}"
                    )
            else:
                self._add_result(
                    f'config_file_{filename}',
                    ValidationLevel.WARNING,
                    f"Configuration file does not exist: {filename}",
                    f"Create default configuration file: {file_path}"
                )
    
    def _validate_instrument_multipliers(self, file_path: Path) -> bool:
        """Validate instrument multipliers file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return False
            
            # Check that all values are numbers
            for instrument, multiplier in data.items():
                if not isinstance(instrument, str) or not isinstance(multiplier, (int, float)):
                    return False
                if multiplier <= 0:
                    return False
            
            return True
            
        except (json.JSONDecodeError, IOError):
            return False
    
    def _validate_settings_file(self, file_path: Path) -> bool:
        """Validate settings file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return False
            
            # Basic structure validation
            for key, setting_data in data.items():
                if not isinstance(setting_data, dict):
                    return False
                
                required_fields = ['key', 'value', 'setting_type']
                if not all(field in setting_data for field in required_fields):
                    return False
            
            return True
            
        except (json.JSONDecodeError, IOError):
            return False
    
    def _validate_profiles_file(self, file_path: Path) -> bool:
        """Validate user profiles file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return False
            
            # Basic structure validation
            for profile_name, profile_data in data.items():
                if not isinstance(profile_data, dict):
                    return False
                
                required_fields = ['name', 'settings', 'created_at', 'updated_at']
                if not all(field in profile_data for field in required_fields):
                    return False
            
            return True
            
        except (json.JSONDecodeError, IOError):
            return False
    
    def _validate_dependencies(self):
        """Validate system dependencies"""
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            self._add_result(
                'python_version',
                ValidationLevel.ERROR,
                f"Python version {python_version.major}.{python_version.minor} is too old",
                "Upgrade to Python 3.8 or higher"
            )
        else:
            self._add_result(
                'python_version',
                ValidationLevel.INFO,
                f"Python version {python_version.major}.{python_version.minor} is supported",
                passed=True
            )
        
        # Check required packages
        required_packages = [
            'flask',
            'redis',
            'pandas',
            'numpy',
            'yfinance',
            'pytest'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self._add_result(
                    f'package_{package}',
                    ValidationLevel.INFO,
                    f"Required package is installed: {package}",
                    passed=True
                )
            except ImportError:
                self._add_result(
                    f'package_{package}',
                    ValidationLevel.ERROR,
                    f"Required package is missing: {package}",
                    f"Install package: pip install {package}"
                )
        
        # Check sqlite3 separately (built-in module)
        try:
            import sqlite3
            self._add_result(
                'package_sqlite3',
                ValidationLevel.INFO,
                "SQLite3 is available (built-in module)",
                passed=True
            )
        except ImportError:
            self._add_result(
                'package_sqlite3',
                ValidationLevel.ERROR,
                "SQLite3 is not available",
                "SQLite3 should be included with Python installation"
            )
    
    def _validate_permissions(self):
        """Validate file and directory permissions"""
        data_dir = Path(os.getenv('DATA_DIR', str(Path.home() / 'FuturesTradingLog' / 'data')))
        
        # Check if we can create files in data directory
        try:
            test_file = data_dir / '.permission_test'
            test_file.touch()
            test_file.unlink()
            
            self._add_result(
                'permissions_data_dir',
                ValidationLevel.INFO,
                "Data directory permissions are correct",
                passed=True
            )
        except (OSError, PermissionError):
            self._add_result(
                'permissions_data_dir',
                ValidationLevel.ERROR,
                f"Cannot write to data directory: {data_dir}",
                f"Fix permissions: chmod 755 {data_dir}"
            )
        
        # Check database file permissions
        db_path = data_dir / 'db' / 'futures_trades.db'
        if db_path.exists():
            if not os.access(db_path, os.R_OK | os.W_OK):
                self._add_result(
                    'permissions_database',
                    ValidationLevel.ERROR,
                    f"Cannot read/write database file: {db_path}",
                    f"Fix permissions: chmod 664 {db_path}"
                )
            else:
                self._add_result(
                    'permissions_database',
                    ValidationLevel.INFO,
                    "Database file permissions are correct",
                    passed=True
                )
    
    def _validate_network(self):
        """Validate network connectivity"""
        # Test internet connectivity for yfinance
        try:
            import urllib.request
            urllib.request.urlopen('https://finance.yahoo.com', timeout=5)
            
            self._add_result(
                'network_internet',
                ValidationLevel.INFO,
                "Internet connectivity is available",
                passed=True
            )
        except Exception:
            self._add_result(
                'network_internet',
                ValidationLevel.WARNING,
                "Internet connectivity is not available",
                "Check network connection for market data updates"
            )
        
        # Test local network ports
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                self._add_result(
                    'network_port',
                    ValidationLevel.WARNING,
                    f"Port {port} is already in use",
                    f"Stop other service on port {port} or use different port"
                )
            else:
                self._add_result(
                    'network_port',
                    ValidationLevel.INFO,
                    f"Port {port} is available",
                    passed=True
                )
        except Exception:
            self._add_result(
                'network_port',
                ValidationLevel.WARNING,
                f"Cannot check port {port} availability",
                "Check network configuration"
            )
    
    def _validate_system_resources(self):
        """Validate system resources"""
        try:
            import psutil
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self._add_result(
                    'system_memory',
                    ValidationLevel.WARNING,
                    f"System memory usage is high: {memory.percent:.1f}%",
                    "Consider closing other applications or adding more RAM"
                )
            else:
                self._add_result(
                    'system_memory',
                    ValidationLevel.INFO,
                    f"System memory usage is acceptable: {memory.percent:.1f}%",
                    passed=True
                )
            
            # Check disk space
            data_dir = Path(os.getenv('DATA_DIR', str(Path.home() / 'FuturesTradingLog' / 'data')))
            disk = psutil.disk_usage(str(data_dir))
            
            if disk.percent > 90:
                self._add_result(
                    'system_disk',
                    ValidationLevel.WARNING,
                    f"Disk space is low: {disk.percent:.1f}% used",
                    "Consider cleaning up old files or adding more storage"
                )
            else:
                self._add_result(
                    'system_disk',
                    ValidationLevel.INFO,
                    f"Disk space is sufficient: {disk.percent:.1f}% used",
                    passed=True
                )
            
        except ImportError:
            self._add_result(
                'system_resources',
                ValidationLevel.WARNING,
                "Cannot check system resources (psutil not installed)",
                "Install psutil for system monitoring: pip install psutil"
            )
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        errors = sum(1 for r in self.results if r.level == ValidationLevel.ERROR)
        warnings = sum(1 for r in self.results if r.level == ValidationLevel.WARNING)
        
        return {
            'total_checks': total,
            'passed': passed,
            'errors': errors,
            'warnings': warnings,
            'success_rate': (passed / total * 100) if total > 0 else 0,
            'overall_status': 'PASS' if errors == 0 else 'FAIL'
        }
    
    def print_results(self):
        """Print validation results to console"""
        print("\n" + "="*60)
        print("CONFIGURATION VALIDATION RESULTS")
        print("="*60)
        
        for result in self.results:
            status = "✓" if result.passed else ("✗" if result.level == ValidationLevel.ERROR else "⚠")
            print(f"{status} {result.name}: {result.message}")
            
            if result.suggestion:
                print(f"   Suggestion: {result.suggestion}")
        
        print("\n" + "-"*60)
        summary = self.get_validation_summary()
        print(f"Summary: {summary['passed']}/{summary['total_checks']} checks passed")
        print(f"Errors: {summary['errors']}, Warnings: {summary['warnings']}")
        print(f"Overall Status: {summary['overall_status']}")
        print("-"*60)


def validate_configuration(config_dir: Optional[Path] = None) -> Tuple[bool, List[ValidationResult]]:
    """Convenience function to validate configuration"""
    validator = ConfigValidator(config_dir)
    results = validator.validate_all()
    
    # Check if validation passed (no errors)
    has_errors = any(r.level == ValidationLevel.ERROR for r in results)
    
    return not has_errors, results


def validate_and_print(config_dir: Optional[Path] = None) -> bool:
    """Validate configuration and print results"""
    validator = ConfigValidator(config_dir)
    results = validator.validate_all()
    validator.print_results()
    
    # Return True if no errors
    return not any(r.level == ValidationLevel.ERROR for r in results)


if __name__ == '__main__':
    # CLI interface for validation
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate configuration')
    parser.add_argument('--config-dir', type=Path, help='Configuration directory path')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.config_dir)
    results = validator.validate_all()
    
    if args.json:
        import json
        output = {
            'summary': validator.get_validation_summary(),
            'results': [
                {
                    'name': r.name,
                    'level': r.level.value,
                    'message': r.message,
                    'suggestion': r.suggestion,
                    'passed': r.passed,
                    'details': r.details
                }
                for r in results
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        validator.print_results()
    
    # Exit with error code if validation failed
    has_errors = any(r.level == ValidationLevel.ERROR for r in results)
    sys.exit(1 if has_errors else 0)