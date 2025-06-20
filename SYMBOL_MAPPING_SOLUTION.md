# Comprehensive Symbol Mapping Solution

## Problem Analysis

The application currently has symbol mapping issues across three different contexts:

1. **NinjaTrader imports**: Use full contract names like "MNQ SEP25" (with expiration months)
2. **Internal storage**: Stores base symbols like "MNQ" (without expiration)  
3. **yfinance API**: Uses format like "NQ=F" or "MNQ=F" for the same contracts

## Current Issues Identified

### 1. Incorrect yfinance Symbol Mappings
Based on Yahoo Finance research, the current mappings are WRONG:

**Current (INCORRECT):**
```python
'MNQ': 'NQ=F',     # Micro Nasdaq-100 -> WRONG
'NQ': 'NQ=F',      # Nasdaq-100
'MES': 'ES=F',     # Micro S&P 500 -> WRONG
```

**Correct mappings should be:**
```python
'MNQ': 'MNQ=F',    # Micro E-mini Nasdaq-100 Index Future
'NQ': 'NQ=F',      # Nasdaq-100 Future
'MES': 'MES=F',    # MICRO E-MINI S&P 500 INDEX FUTURE
'ES': 'ES=F',      # E-Mini S&P 500 Future
```

### 2. Inconsistent Symbol Handling
- Position templates use `.split()[0]` to extract base symbols
- Database migration normalizes to base symbols
- Chart API tries exact match first, then base symbol fallback
- yfinance mapping doesn't distinguish micro vs full contracts

### 3. Multiple Transformation Points
Symbol transformations happen in multiple places:
- `templates/positions/detail.html`: `position.instrument.split()[0]`
- `templates/trade_detail.html`: `trade.instrument.split()[0]`
- `data_service.py`: `_get_base_instrument()` and `_get_yfinance_symbol()`
- `TradingLog_db.py`: `migrate_instrument_names_to_base_symbols()`

## Proposed Solution: Centralized Symbol Management Service

### 1. Create `SymbolMappingService` Class

```python
# symbol_service.py
class SymbolMappingService:
    """Centralized service for all instrument symbol transformations"""
    
    def __init__(self):
        # Mapping from base symbols to yfinance symbols
        self.yfinance_mapping = {
            # Nasdaq
            'MNQ': 'MNQ=F',    # Micro E-mini Nasdaq-100
            'NQ': 'NQ=F',      # E-mini Nasdaq-100
            
            # S&P 500
            'MES': 'MES=F',    # Micro E-mini S&P 500
            'ES': 'ES=F',      # E-mini S&P 500
            
            # Russell 2000
            'M2K': 'RTY=F',    # Micro E-mini Russell 2000 (maps to RTY=F)
            'RTY': 'RTY=F',    # E-mini Russell 2000
            
            # Dow Jones
            'MYM': 'YM=F',     # Micro E-mini Dow (maps to YM=F)
            'YM': 'YM=F',      # E-mini Dow Jones
            
            # Commodities
            'CL': 'CL=F',      # Crude Oil
            'GC': 'GC=F',      # Gold
            'SI': 'SI=F',      # Silver
            'ZN': 'ZN=F',      # 10-Year Treasury Note
            'ZB': 'ZB=F',      # 30-Year Treasury Bond
        }
    
    def get_base_symbol(self, instrument: str) -> str:
        """Extract base symbol from any instrument format"""
        return instrument.split()[0].upper()
    
    def get_yfinance_symbol(self, instrument: str) -> str:
        """Get yfinance symbol for any instrument format"""
        base = self.get_base_symbol(instrument)
        return self.yfinance_mapping.get(base, f"{base}=F")
    
    def get_display_name(self, instrument: str) -> str:
        """Get human-readable display name"""
        base = self.get_base_symbol(instrument)
        display_names = {
            'MNQ': 'Micro NASDAQ-100',
            'NQ': 'NASDAQ-100',
            'MES': 'Micro S&P 500',
            'ES': 'S&P 500',
            'RTY': 'Russell 2000',
            'M2K': 'Micro Russell 2000',
            'YM': 'Dow Jones',
            'MYM': 'Micro Dow Jones',
            'CL': 'Crude Oil',
            'GC': 'Gold',
            'SI': 'Silver',
        }
        return display_names.get(base, base)
    
    def normalize_for_storage(self, instrument: str) -> str:
        """Normalize instrument symbol for database storage"""
        return self.get_base_symbol(instrument)
    
    def validate_symbol(self, instrument: str) -> bool:
        """Check if symbol is supported"""
        base = self.get_base_symbol(instrument)
        return base in self.yfinance_mapping
```

### 2. Update Templates to Use Service

```jinja2
<!-- templates/positions/detail.html -->
{% set chart_instrument = symbol_service.get_base_symbol(position.instrument) %}

<!-- templates/trade_detail.html -->
{% set chart_instrument = symbol_service.get_base_symbol(trade.instrument) %}
```

### 3. Update Data Service

```python
# data_service.py
from symbol_service import SymbolMappingService

class OHLCDataService:
    def __init__(self):
        self.symbol_service = SymbolMappingService()
        # Remove old symbol_mapping and methods
    
    def _get_yfinance_symbol(self, instrument: str) -> str:
        return self.symbol_service.get_yfinance_symbol(instrument)
    
    def get_chart_data(self, instrument: str, timeframe: str, start_date, end_date):
        # Try exact instrument first, then base symbol
        base_instrument = self.symbol_service.get_base_symbol(instrument)
        # ... rest of method
```

### 4. Template Filter for Jinja2

```python
# app.py
from symbol_service import SymbolMappingService

symbol_service = SymbolMappingService()

@app.template_filter('base_symbol')
def base_symbol_filter(instrument):
    return symbol_service.get_base_symbol(instrument)

@app.template_filter('display_name')
def display_name_filter(instrument):
    return symbol_service.get_display_name(instrument)
```

Then in templates:
```jinja2
{% set chart_instrument = position.instrument|base_symbol %}
<h2>{{ position.instrument|display_name }} Position</h2>
```

## Implementation Benefits

1. **Single Source of Truth**: All symbol transformations go through one service
2. **Correct yfinance Mappings**: MNQ->MNQ=F, MES->MES=F (not wrong mappings)
3. **Consistent Behavior**: Same logic everywhere in the application
4. **Easy Maintenance**: Add new symbols in one place
5. **Validation**: Can check if symbols are supported
6. **Display Names**: Human-readable names for UI

## Testing Plan

1. **Test yfinance mappings** with actual API calls
2. **Test chart loading** with various symbol formats
3. **Test database migration** with new service
4. **Test template rendering** with filter functions
5. **Test symbol validation** for unsupported instruments

## Migration Strategy

1. Create `SymbolMappingService` class
2. Add template filters to `app.py`
3. Update templates to use filters instead of `.split()[0]`
4. Update `data_service.py` to use the service
5. Test thoroughly with existing data
6. Deploy and monitor for issues

This solution eliminates the symbol mapping confusion and provides a robust, centralized approach to handling instrument symbols across all contexts.