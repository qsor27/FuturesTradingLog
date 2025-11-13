# Spec: Daily OHLC Candlestick Data Sync with Import Process

## Overview
Integrate OHLC (candlestick) data downloads with the daily CSV import process at 2:05pm PT, downloading **all 18 available Yahoo Finance timeframes** for instruments found in the imported CSV file. Replace all existing automated sync schedules with a single daily post-import sync.

## Problem
Current OHLC sync runs on independent schedules (hourly, daily 2am UTC, weekly) regardless of trading activity, only downloads 8 of 18 available timeframes, and is not coordinated with the daily import process.

## Solution
- Run OHLC sync **immediately after** CSV import completes at 2:05pm PT
- Download OHLC for **only the instruments in the imported CSV file**
- Download **all 18 Yahoo Finance timeframes** (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 5d, 1wk, 1mo, 3mo)
- **Remove all other automated sync schedules** (hourly, daily 2am UTC, weekly)
- Sync only once per day, triggered by import completion

## Key Changes

### Integration
- Daily import scheduler at 2:05pm PT triggers OHLC sync after successful import
- Extract unique instruments from imported CSV file
- Map NinjaTrader instrument names to Yahoo Finance symbols
- Pass instrument list to OHLC sync service

### Timeframe Expansion
**Currently Downloaded (8 timeframes):**
- 1m, 3m→5m, 5m, 15m, 30m, 1h, 4h, 1d

**NEW - All Yahoo Finance Timeframes (18 total):**
- **Minute**: 1m, 2m, 5m, 15m, 30m, 60m, 90m
- **Hourly**: 1h, 2h, 4h, 6h, 8h, 12h
- **Daily+**: 1d, 5d, 1wk, 1mo, 3mo

### Schedule Removal
- ❌ Remove hourly OHLC sync
- ❌ Remove daily 2am UTC OHLC sync
- ❌ Remove weekly Sunday 3am UTC OHLC sync
- ✅ Single daily sync at 2:05pm PT (post-import)

## Implementation

### Modified Files
1. **services/daily_import_scheduler.py** - Add post-import OHLC trigger
2. **services/data_service.py** - Expand to all 18 timeframes, add sync method
3. **config/config.py** - Update SUPPORTED_TIMEFRAMES with all 18
4. **scripts/automated_data_sync.py** - Remove all scheduled syncs

### Core Logic
```python
# In daily_import_scheduler.py
def run_daily_import(self):
    csv_file = self.find_csv_file()
    if csv_file:
        instruments = self.import_csv(csv_file)  # Returns list of instruments
        if instruments:
            self.trigger_ohlc_sync(instruments)  # Sync immediately

# In data_service.py
ALL_YAHOO_TIMEFRAMES = [
    '1m', '2m', '5m', '15m', '30m', '60m', '90m',
    '1h', '2h', '4h', '6h', '8h', '12h',
    '1d', '5d', '1wk', '1mo', '3mo'
]

def sync_instruments(self, instruments, timeframes):
    for instrument in instruments:
        for timeframe in timeframes:
            self.fetch_ohlc_data(instrument, timeframe)
```

## Benefits
- **Efficiency**: Only sync when trades actually occurred
- **Completeness**: All 18 Yahoo Finance timeframes available for analysis
- **Optimal Timing**: Sync right after market close at 2:05pm PT
- **Simplified Architecture**: Single daily sync instead of 3 independent schedules
- **Resource Optimization**: Fewer API calls, reduced system load

## Migration
1. **Phase 1**: Implement post-import sync, keep old schedules running
2. **Phase 2**: Monitor for 1 week, verify data completeness
3. **Phase 3**: Remove old sync schedules permanently

## Success Metrics
- OHLC sync runs immediately after import (within 1 minute)
- All 18 timeframes downloaded for each instrument in CSV
- Sync completes within 5 minutes for typical 3-5 instruments
- No data gaps compared to old sync schedules
- Zero hourly/daily/weekly syncs running
