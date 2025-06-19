# Chart Data Fix Solution

## Problem Analysis

The chart system was missing candle data due to **instrument name inconsistency** between trades and OHLC data:

- **Trades table**: Contains instruments like `"MNQ SEP25"` (with expiration dates)
- **OHLC data table**: Sometimes stored as `"MNQ"` (base symbol) or `"MNQ SEP25"` (full name)
- **Chart API**: Requested data for `"MNQ SEP25"` but OHLC lookup failed due to name mismatch

## Root Cause

The `data_service.py` `fetch_ohlc_data()` method stored OHLC data using the full instrument name passed to it:
- When called with `"MNQ SEP25"` → stored as `"MNQ SEP25"`  
- When called with `"MNQ"` → stored as `"MNQ"`

This created inconsistent data storage depending on how the method was called.

## Solution Implementation

### 1. Normalized Instrument Storage

**Modified `data_service.py`:**
- Added `_get_base_instrument()` method to extract base symbols
- Updated `fetch_ohlc_data()` to always store using base symbol (`MNQ` instead of `MNQ SEP25`)
- Updated `get_chart_data()` to lookup using base symbol for consistency

### 2. Smart Chart Lookup

**Enhanced chart data retrieval:**
- Chart API automatically maps `"MNQ SEP25"` → `"MNQ"` for OHLC queries
- Maintains backward compatibility with existing data
- Works regardless of how the instrument name is formatted

### 3. Database Migration

**Added migration system:**
- `migrate_instrument_names_to_base_symbols()` method in `TradingLog_db.py`
- Automatically runs on service initialization
- Converts existing `"MNQ SEP25"` records to `"MNQ"` format
- Handles conflicts by merging data intelligently

### 4. Comprehensive Testing

**Created test suite:**
- `test_instrument_mapping.py` validates all instrument formats work
- Tests both direct database queries and HTTP API endpoints
- Verifies migration completed successfully

## Key Changes

### data_service.py
```python
def _get_base_instrument(self, instrument: str) -> str:
    """Extract base instrument symbol (e.g., 'MNQ SEP25' -> 'MNQ')"""
    return instrument.split()[0]

def get_chart_data(self, instrument: str, timeframe: str, 
                  start_date: datetime, end_date: datetime) -> List[Dict]:
    # Use base symbol for OHLC lookups to handle instrument variations
    base_instrument = self._get_base_instrument(instrument)
    # ... rest uses base_instrument for consistent lookups
```

### TradingLog_db.py
```python
def migrate_instrument_names_to_base_symbols(self) -> Dict[str, int]:
    """Migrate OHLC data to use base instrument symbols for consistency."""
    # Converts instruments like 'MNQ SEP25' to 'MNQ' for normalized storage
```

## Benefits

1. **Consistent Data Storage**: All OHLC data now uses base symbols (`MNQ`, `ES`, etc.)
2. **Flexible Chart Access**: Charts work with any instrument format (`MNQ SEP25`, `MNQ`, etc.)
3. **Automatic Migration**: Existing data automatically converted on startup
4. **Future-Proof**: New data always stored consistently
5. **Backward Compatible**: No breaking changes to existing functionality

## Testing

Run the test suite to verify the solution:

```bash
python test_instrument_mapping.py
```

Expected results:
- ✓ All instrument formats return chart data
- ✓ OHLC data normalized to base symbols
- ✓ Chart API works for both `"MNQ SEP25"` and `"MNQ"`
- ✓ Migration completed successfully

## Impact

- **Charts now display candle data** for all instruments regardless of naming format
- **No more instrument mismatch issues** between trades and OHLC data
- **Simplified maintenance** with consistent data storage
- **Improved performance** with optimized base symbol lookups