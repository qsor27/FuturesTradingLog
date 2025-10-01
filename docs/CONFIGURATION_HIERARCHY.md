# Configuration Hierarchy Documentation

## Overview

The Futures Trading Log application uses a hierarchical configuration system that supports multiple environments, centralized settings management, and comprehensive validation. This document outlines the complete configuration architecture.

## Configuration Layers

### 1. Environment-Based Configuration (`config/environments.py`)

The primary configuration layer that adapts to different deployment environments.

#### Configuration Classes

```python
BaseConfig (Abstract)
├── DevelopmentConfig
├── TestingConfig
└── ProductionConfig
```

#### Environment Detection

Configuration is automatically selected based on the `FLASK_ENV` environment variable:

- `development`/`dev` → `DevelopmentConfig`
- `testing`/`test`/`test_local` → `TestingConfig`
- `production`/`prod` → `ProductionConfig`

#### Configuration Properties

Each environment configuration provides:

```python
# Core paths
data_dir: Path              # Base data directory
db_path: Path              # Database file path
config_dir: Path           # Configuration directory
logs_dir: Path             # Logs directory

# Flask settings
flask_config: Dict         # Flask configuration dictionary
host: str                  # Bind host
port: int                  # Bind port
debug: bool               # Debug mode
secret_key: str           # Secret key

# Database configuration
database_config: Dict     # Database settings

# Redis configuration
redis_config: Dict        # Redis connection settings
redis_url: str            # Redis URL

# Application settings
auto_import_enabled: bool  # Auto import feature
auto_import_interval: int  # Import interval
cache_enabled: bool       # Caching feature
cache_ttl_days: int       # Cache TTL

# Logging configuration
logging_config: Dict      # Logging setup
log_level: str           # Log level
```

### 2. Settings Management (`config/settings_manager.py`)

Centralized user-configurable settings with persistence and validation.

#### Setting Types

```python
class SettingType(Enum):
    SYSTEM = "system"          # System-wide settings
    USER = "user"              # User preferences
    CHART = "chart"            # Chart display settings
    TRADING = "trading"        # Trading preferences
    PERFORMANCE = "performance" # Performance tuning
    IMPORT = "import"          # Import configuration
```

#### Default Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `theme` | SYSTEM | `"dark"` | Application theme |
| `language` | SYSTEM | `"en"` | Application language |
| `default_timeframe` | CHART | `"1h"` | Default chart timeframe |
| `chart_height` | CHART | `400` | Chart height in pixels |
| `show_volume` | CHART | `true` | Show volume on charts |
| `show_positions` | CHART | `true` | Show positions on charts |
| `default_account` | TRADING | `""` | Default trading account |
| `risk_per_trade` | TRADING | `1.0` | Risk per trade percentage |
| `cache_enabled` | PERFORMANCE | `true` | Enable caching |
| `cache_ttl_minutes` | PERFORMANCE | `60` | Cache TTL in minutes |
| `auto_import_enabled` | IMPORT | `true` | Enable auto import |
| `positions_per_page` | USER | `50` | Positions per page |

#### User Profiles

Settings can be organized into named profiles:

```python
@dataclass
class UserProfile:
    name: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    is_default: bool = False
```

### 3. Configuration Validation (`config/validation.py`)

Comprehensive validation system that ensures configuration correctness.

#### Validation Categories

1. **Environment Variables**
   - `FLASK_ENV` validity
   - Required production variables
   - Optional variable formats

2. **Directory Structure**
   - Required directories exist
   - Write permissions
   - Path validity

3. **Database Configuration**
   - SQLite connectivity
   - Required tables
   - Schema validation

4. **Redis Configuration**
   - Connection testing
   - Memory usage
   - Configuration validity

5. **Configuration Files**
   - JSON syntax validation
   - Schema compliance
   - Data integrity

6. **System Dependencies**
   - Python version
   - Required packages
   - System resources

#### Validation Levels

```python
class ValidationLevel(Enum):
    ERROR = "error"      # Critical issues that prevent operation
    WARNING = "warning"  # Issues that may cause problems
    INFO = "info"        # Informational messages
```

## Configuration Files

### 1. Environment Files

#### `.env.development`
```bash
FLASK_ENV=development
FLASK_DEBUG=true
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
DATA_DIR=./data
REDIS_URL=redis://localhost:6379/0
```

#### `.env.production`
```bash
FLASK_ENV=production
FLASK_SECRET_KEY=your-secret-key
DATA_DIR=/app/data
REDIS_URL=redis://redis:6379/0
USE_HTTPS=true
```

### 2. Application Configuration Files

#### `data/config/instrument_multipliers.json`
```json
{
  "ES": 50.0,
  "NQ": 20.0,
  "YM": 5.0,
  "RTY": 50.0,
  "CL": 1000.0,
  "GC": 100.0
}
```

#### `data/config/settings.json`
```json
{
  "theme": {
    "key": "theme",
    "value": "dark",
    "setting_type": "system",
    "description": "Application theme",
    "validation_rules": {
      "choices": ["light", "dark", "auto"]
    }
  }
}
```

#### `data/config/user_profiles.json`
```json
{
  "Default": {
    "name": "Default",
    "settings": {
      "theme": "dark",
      "default_timeframe": "1h"
    },
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "is_default": true
  }
}
```

### 3. Test Configuration Files

#### `pytest.ini`
```ini
[pytest]
testpaths = tests
addopts = --cov=. --cov-report=html --cov-report=xml
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    performance: marks tests as performance tests
```

#### `.coveragerc`
```ini
[run]
source = .
omit = tests/*, venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
```

## Configuration Usage

### 1. Basic Usage

```python
# Get current configuration
from config.environments import get_config

config = get_config()
print(f"Database path: {config.db_path}")
print(f"Debug mode: {config.debug}")
```

### 2. Settings Management

```python
# Get settings manager
from config.settings_manager import get_settings_manager

settings = get_settings_manager()

# Get setting value
theme = settings.get_setting('theme')

# Set setting value
settings.set_setting('theme', 'light')

# Get settings by type
chart_settings = settings.get_settings_by_type(SettingType.CHART)
```

### 3. Configuration Validation

```python
# Validate configuration
from config.validation import validate_configuration

is_valid, results = validate_configuration()

if not is_valid:
    for result in results:
        if result.level == ValidationLevel.ERROR:
            print(f"Error: {result.message}")
```

## Environment-Specific Behavior

### Development Environment

- **Debug Mode**: Enabled for detailed error messages
- **Hot Reload**: Automatic application restart on code changes
- **Verbose Logging**: DEBUG level logging
- **Local Services**: Redis and database on localhost
- **Fast Cache**: Short TTL for rapid development

### Testing Environment

- **Isolated Database**: Temporary database per test run
- **Disabled Features**: Auto-import and caching disabled
- **Minimal Logging**: WARNING level to reduce noise
- **Separate Redis DB**: Uses different Redis database
- **Deterministic Behavior**: Consistent test results

### Production Environment

- **Security**: HTTPS enabled, secure cookies
- **Performance**: Optimized caching and connection pooling
- **Monitoring**: INFO level logging with rotation
- **Persistence**: Persistent data storage
- **Validation**: Strict environment variable validation

## Configuration Precedence

Configuration values are resolved in the following order (highest to lowest precedence):

1. **Environment Variables** (highest precedence)
2. **User Profile Settings**
3. **Application Settings**
4. **Default Configuration Values** (lowest precedence)

## Best Practices

### 1. Environment Variables

- Use environment variables for deployment-specific settings
- Never commit secrets to version control
- Use descriptive variable names with consistent prefixes
- Validate all environment variables at startup

### 2. Settings Management

- Use appropriate setting types for organization
- Implement validation rules for all settings
- Provide meaningful descriptions for user-facing settings
- Use profiles for different user scenarios

### 3. Configuration Files

- Store configuration files in version control (except secrets)
- Use JSON for structured configuration data
- Validate configuration file syntax and schema
- Provide default configurations for all environments

### 4. Validation

- Validate configuration at application startup
- Use appropriate validation levels (ERROR, WARNING, INFO)
- Provide actionable suggestions for fixing issues
- Test configuration validation in CI/CD pipeline

## Troubleshooting

### Common Issues

1. **Configuration Not Found**
   - Check `FLASK_ENV` environment variable
   - Verify configuration files exist
   - Check file permissions

2. **Validation Failures**
   - Run `python -m config.validation` for details
   - Check environment variables
   - Verify service connectivity

3. **Settings Not Persisting**
   - Check write permissions on config directory
   - Verify settings manager initialization
   - Check for file system errors

### Debug Commands

```bash
# Validate configuration
python -m config.validation

# Check configuration summary
python -c "from config.environments import get_config_summary; print(get_config_summary())"

# Check settings summary
python -c "from config.settings_manager import get_settings_manager; print(get_settings_manager().get_settings_summary())"
```

## Migration Guide

### From Legacy Configuration

1. **Identify Current Settings**
   - Extract hardcoded values
   - Document environment-specific differences
   - List user-configurable options

2. **Create Environment Configurations**
   - Implement environment-specific classes
   - Move environment variables to appropriate configs
   - Add validation for critical settings

3. **Migrate User Settings**
   - Convert user preferences to settings system
   - Create default profiles
   - Implement settings migration scripts

4. **Update Application Code**
   - Replace direct configuration access
   - Use configuration managers
   - Add validation at startup

### Version Compatibility

- **Configuration format**: JSON with semantic versioning
- **Settings migration**: Automatic upgrade on version changes
- **Backwards compatibility**: Deprecated settings supported for one version
- **Breaking changes**: Documented in release notes

## Security Considerations

### 1. Secret Management

- Never store secrets in configuration files
- Use environment variables for sensitive data
- Implement secret rotation procedures
- Use secure secret management systems in production

### 2. File Permissions

- Restrict access to configuration directories
- Use appropriate file permissions (644 for config files)
- Regularly audit file permissions
- Implement configuration file encryption for sensitive data

### 3. Validation

- Validate all configuration inputs
- Sanitize user-provided configuration
- Implement rate limiting for configuration changes
- Log configuration changes for auditing

## Performance Considerations

### 1. Configuration Loading

- Cache configuration objects
- Lazy-load configuration when possible
- Minimize configuration file reads
- Use configuration validation at startup only

### 2. Settings Management

- Implement efficient settings storage
- Use appropriate caching strategies
- Minimize database queries for settings
- Batch settings updates when possible

### 3. Validation

- Perform expensive validation once at startup
- Use async validation for non-critical checks
- Implement validation result caching
- Skip validation in performance-critical paths