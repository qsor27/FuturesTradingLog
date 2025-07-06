# Enhanced Settings Categories API

## Overview

The Enhanced Settings Categories feature provides a unified API for managing all application settings in a categorized structure. This replaces the fragmented approach of managing settings through separate endpoints and files.

## Key Features

- **Categorized Structure**: Settings are organized into logical categories (chart, trading, notifications)
- **Unified API**: Single endpoint for fetching and updating all settings
- **Profile Integration**: Automatic synchronization with user profiles
- **Validation**: Comprehensive validation for all setting types
- **Backward Compatibility**: Existing settings APIs continue to work

## API Endpoints

### GET /api/v2/settings/categorized

Fetches all settings in categorized format.

**Response:**
```json
{
  "success": true,
  "settings": {
    "chart": {
      "default_timeframe": "1h",
      "default_data_range": "1week",
      "volume_visibility": true,
      "last_updated": "2024-01-01T12:00:00Z"
    },
    "trading": {
      "instrument_multipliers": {
        "ES": 50,
        "NQ": 20
      }
    },
    "notifications": {}
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### PUT /api/v2/settings/categorized

Updates categorized settings.

**Request:**
```json
{
  "settings": {
    "chart": {
      "default_timeframe": "4h",
      "volume_visibility": false
    },
    "trading": {
      "instrument_multipliers": {
        "ES": 50,
        "NQ": 20,
        "YM": 5
      }
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings updated successfully: chart, trading",
  "updated_sections": ["chart", "trading"],
  "settings": {
    "chart": { ... },
    "trading": { ... }
  }
}
```

### POST /api/v2/settings/validate

Validates settings without saving them.

**Request:**
```json
{
  "settings": {
    "chart": {
      "default_timeframe": "2h",  // Invalid
      "default_data_range": "1week",
      "volume_visibility": "yes"  // Invalid type
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "valid": false,
  "validation_results": {
    "chart": {
      "valid": false,
      "errors": [
        "Invalid timeframe. Must be one of ['1m', '3m', '5m', '15m', '1h', '4h', '1d']",
        "volume_visibility must be a boolean"
      ]
    }
  }
}
```

## Settings Categories

### Chart Settings

Controls chart display preferences:

- **default_timeframe**: Default chart timeframe (`1m`, `3m`, `5m`, `15m`, `1h`, `4h`, `1d`)
- **default_data_range**: Default data range (`1day`, `3days`, `1week`, `2weeks`, `1month`, `3months`, `6months`)
- **volume_visibility**: Show/hide volume bars (boolean)
- **last_updated**: Timestamp of last update

### Trading Settings

Controls trading-related preferences:

- **instrument_multipliers**: Dictionary of instrument multipliers for P&L calculations

### Notifications Settings

Reserved for future notification preferences (currently empty).

## Data Storage

- **Chart Settings**: Stored in `chart_settings` database table
- **Trading Settings**: Stored in `data/config/instrument_multipliers.json`
- **Profile Integration**: Settings are automatically synced to the active user profile's `settings_snapshot`

## Profile Integration

When settings are updated via the categorized API:

1. Settings are saved to their respective storage locations
2. The active user profile's `settings_snapshot` is updated with the new settings
3. This ensures profile-based settings management remains synchronized

## Validation Rules

### Chart Settings

- `default_timeframe`: Must be one of the valid timeframes
- `default_data_range`: Must be one of the valid data ranges
- `volume_visibility`: Must be a boolean value

### Trading Settings

- `instrument_multipliers`: Must be a dictionary where all values are numeric

## Error Handling

The API provides comprehensive error handling:

- **400 Bad Request**: Invalid request format or validation failures
- **500 Internal Server Error**: Database or file system errors
- **Graceful Degradation**: Falls back to defaults when storage is unavailable

## Implementation Details

### Backend Integration

The categorized settings API integrates with existing systems:

- Uses existing `FuturesDB.get_chart_settings()` and `FuturesDB.update_chart_settings()`
- Reads/writes instrument multipliers from JSON file
- Automatically updates user profiles when settings change

### Validation Functions

Internal validation functions ensure data integrity:

- `_validate_chart_settings()`: Validates chart setting values
- `_validate_trading_settings()`: Validates trading setting values
- `_update_active_profile_settings()`: Syncs settings with user profiles

## Testing

The implementation includes comprehensive tests:

- **Unit Tests**: `test_settings_validation.py` - Tests validation logic
- **Integration Tests**: `test_categorized_settings.py` - Tests API endpoints
- **Syntax Validation**: Ensures code quality and imports

## Backward Compatibility

The enhanced settings API is fully backward compatible:

- Existing `/api/v1/settings/chart` endpoints continue to work
- Existing settings pages and forms remain functional
- Migration is optional - both old and new APIs can coexist

## Usage Examples

### Frontend Integration

```javascript
// Fetch all settings
const response = await fetch('/api/v2/settings/categorized');
const { settings } = await response.json();

// Update chart settings
await fetch('/api/v2/settings/categorized', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    settings: {
      chart: {
        default_timeframe: '4h',
        volume_visibility: false
      }
    }
  })
});
```

### Profile Management

```javascript
// Settings are automatically included in profile snapshots
const profile = await createProfile({
  profile_name: 'My Trading Profile',
  settings_snapshot: {
    chart: { default_timeframe: '1h' },
    trading: { instrument_multipliers: { ES: 50 } }
  }
});
```

## Benefits

1. **Unified Interface**: Single API for all settings management
2. **Better Organization**: Logical categorization of settings
3. **Enhanced Validation**: Comprehensive validation before saving
4. **Profile Integration**: Automatic synchronization with user profiles
5. **Extensibility**: Easy to add new setting categories
6. **Backward Compatibility**: Existing code continues to work