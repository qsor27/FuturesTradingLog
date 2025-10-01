# User Profiles Implementation

## Overview

This document describes the implementation of the **Setting Profiles/Templates** feature (HIGH IMPACT priority from TODO list) for the FuturesTradingLog application. This feature allows users to save multiple named configurations for different trading strategies and instantly switch between complex layouts.

## Database Schema

### Table: `user_profiles`

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    profile_name TEXT NOT NULL,
    description TEXT,
    settings_snapshot TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, profile_name)
);
```

### Indexes

For optimal performance, the following indexes are created:

```sql
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id_profile_name ON user_profiles(user_id, profile_name);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_default ON user_profiles(user_id, is_default);
CREATE INDEX IF NOT EXISTS idx_user_profiles_created_at ON user_profiles(created_at);
```

## Schema Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique identifier for the profile |
| `user_id` | INTEGER NOT NULL DEFAULT 1 | User identifier (defaults to 1 for single-user setup) |
| `profile_name` | TEXT NOT NULL | Human-readable name for the profile |
| `description` | TEXT | Optional description of the profile's purpose |
| `settings_snapshot` | TEXT NOT NULL | JSON string containing all settings |
| `is_default` | BOOLEAN NOT NULL DEFAULT 0 | Whether this is the default profile |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Profile creation timestamp |
| `updated_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

## Settings Snapshot Structure

The `settings_snapshot` field stores a JSON object combining various user preferences:

```json
{
    "chart_settings": {
        "default_timeframe": "1h",
        "default_data_range": "1week",
        "volume_visibility": true
    },
    "instrument_multipliers": {
        "NQ": 20,
        "ES": 50,
        "YM": 5,
        "RTY": 50
    },
    "theme_settings": {
        "dark_mode": true,
        "chart_background": "#000000",
        "grid_color": "#333333"
    },
    "display_preferences": {
        "show_pnl": true,
        "show_volume": true,
        "decimal_places": 2
    }
}
```

## API Methods

### CRUD Operations

#### Create Profile
```python
def create_user_profile(self, profile_name: str, settings_snapshot: Dict[str, Any], 
                       description: str = None, is_default: bool = False, 
                       user_id: int = 1) -> Optional[int]
```

#### Read Operations
```python
def get_user_profiles(self, user_id: int = 1) -> List[Dict[str, Any]]
def get_user_profile(self, profile_id: int) -> Optional[Dict[str, Any]]
def get_user_profile_by_name(self, profile_name: str, user_id: int = 1) -> Optional[Dict[str, Any]]
def get_default_user_profile(self, user_id: int = 1) -> Optional[Dict[str, Any]]
```

#### Update Profile
```python
def update_user_profile(self, profile_id: int, profile_name: str = None, 
                       settings_snapshot: Dict[str, Any] = None, 
                       description: str = None, is_default: bool = None) -> bool
```

#### Delete Profile
```python
def delete_user_profile(self, profile_id: int) -> bool
```

## Key Features

### 1. Default Profile Management
- Only one profile can be marked as default per user
- Setting a profile as default automatically unsets any existing default
- Applications can load default settings on startup

### 2. Unique Constraints
- Profile names must be unique per user
- Enforced at the database level with `UNIQUE(user_id, profile_name)`

### 3. JSON Settings Storage
- All settings are stored as JSON in the `settings_snapshot` field
- Supports nested structures for complex configurations
- Automatically parsed to Python dictionaries when retrieved

### 4. Comprehensive Indexing
- Optimized queries for common operations
- Fast lookup by user_id, profile_name, and default status
- Chronological sorting support

## Integration Points

### Database Initialization
The schema is automatically created during database initialization in `TradingLog_db.py`:
- Table creation in `__enter__` method
- Index creation with error handling
- Integration with existing database monitoring

### Monitoring Integration
- Table operations are tracked in the `_detect_table_from_query` method
- Database performance metrics include user_profiles operations

## Use Cases

### 1. Scalping vs Swing Trading
```python
# Scalping setup
scalping_settings = {
    'chart_settings': {
        'default_timeframe': '1m',
        'default_data_range': '3hours',
        'volume_visibility': True
    }
}

# Swing trading setup
swing_settings = {
    'chart_settings': {
        'default_timeframe': '4h',
        'default_data_range': '1month',
        'volume_visibility': False
    }
}
```

### 2. Instrument-Specific Configurations
```python
# NQ-focused profile
nq_settings = {
    'instrument_multipliers': {'NQ': 20},
    'chart_settings': {
        'default_timeframe': '5m',
        'default_data_range': '1week'
    }
}
```

### 3. Theme Variations
```python
# Dark mode trading
dark_settings = {
    'theme_settings': {
        'dark_mode': True,
        'chart_background': '#000000'
    }
}

# Light mode analysis
light_settings = {
    'theme_settings': {
        'dark_mode': False,
        'chart_background': '#ffffff'
    }
}
```

## Implementation Status

✅ **Complete**: Database schema and CRUD operations
✅ **Complete**: Index optimization for performance
✅ **Complete**: Integration with existing database patterns
✅ **Complete**: JSON settings storage and parsing
✅ **Complete**: Default profile management
✅ **Complete**: Comprehensive testing and validation

## Next Steps

1. **Frontend Integration**: Create UI components for profile management
2. **API Endpoints**: Implement Flask routes for profile CRUD operations
3. **Settings Migration**: Add functionality to migrate existing settings to profiles
4. **Import/Export**: Implement profile sharing and backup functionality
5. **Version History**: Add settings version tracking for safety

## Testing

The implementation has been thoroughly tested with:
- Schema creation and validation
- CRUD operations with realistic data
- Index performance verification
- Integration with existing database structure
- JSON serialization/deserialization
- Unique constraint enforcement
- Default profile management

## Files Modified

- `TradingLog_db.py`: Added user_profiles table creation and CRUD methods
- `example_user_profiles_usage.py`: Usage examples and integration patterns

## Example Usage

See `example_user_profiles_usage.py` for comprehensive usage examples including:
- Creating profiles with different configurations
- Retrieving and switching between profiles
- Application integration patterns
- Profile management workflows
- Data structure examples

This implementation provides a solid foundation for the Setting Profiles/Templates feature and can be extended with additional functionality as needed.