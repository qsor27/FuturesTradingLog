# Chart Data Fix - Instrument Name Consistency

## Problem
Chart system missing candle data due to instrument name inconsistency:
- **Trades**: `"MNQ SEP25"` (with expiration)
- **OHLC data**: Sometimes `"MNQ"` (base) or `"MNQ SEP25"` (full)
- **Result**: Lookup failures between trades and OHLC data

## Solution
1. **Normalized Storage**: All OHLC data stored using base symbols (`MNQ` not `MNQ SEP25`)
2. **Smart Lookup**: Chart API maps `"MNQ SEP25"` → `"MNQ"` automatically  
3. **Auto Migration**: `migrate_instrument_names_to_base_symbols()` converts existing data
4. **Testing**: `test_instrument_mapping.py` validates all formats work

## Key Changes
```python
# data_service.py
def _get_base_instrument(self, instrument: str) -> str:
    return instrument.split()[0]  # "MNQ SEP25" → "MNQ"
```

## Testing
```bash
python test_instrument_mapping.py
```

## Result
Charts now work with any instrument format - consistent data storage with flexible access.