# Specification: Daily OHLC Candlestick Data Sync with Import Process

## Goal
Integrate OHLC (candlestick) data synchronization with the daily NinjaTrader CSV import process, downloading **all available Yahoo Finance timeframes** for instruments found in the imported CSV file at 2:05pm PT, replacing all existing automated sync schedules with a single daily sync.

## Problem Statement

The current OHLC data synchronization strategy uses multiple independent schedules that run regardless of whether trades occurred:

1. **Hourly Sync**: Updates recent data every hour, even when no trading activity
2. **Daily Sync at 2am UTC**: Full sync at suboptimal time (6pm PT / 9pm ET previous day)
3. **Weekly Sync**: Deep historical sync every Sunday at 3am UTC
4. **Incomplete Timeframe Coverage**: Only syncs 8 of 18 available Yahoo Finance timeframes

**Issues with Current Approach:**
- **Inefficient Resource Usage**: Syncing hourly when no trades may have occurred
- **Suboptimal Timing**: Daily sync at 2am UTC (before market close at 2pm PT)
- **Disconnected from Import**: OHLC sync not tied to actual trading activity
- **Limited Timeframe Coverage**: Missing 10 useful timeframes (2m, 60m, 90m, 2h, 6h, 8h, 12h, 5d, 1wk, 1mo, 3mo)
- **No Coordination**: Import and OHLC sync run independently

## Futures Market Schedule Context

**Trading Session Times:**
- **Sunday**: 3pm PT (open) → Monday 2pm PT (close)
- **Monday-Thursday**: 3pm PT (open) → Next day 2pm PT (close)
- **Friday**: Market closes at 2pm PT, reopens Sunday 3pm PT

**Daily Import Schedule:**
- Runs at **2:05pm Pacific Time** daily
- Monitors for `NinjaTrader_Executions_YYYYMMDD.csv` files
- Imports executions that occurred during the completed trading session

**Optimal OHLC Sync Timing:**
- Run **immediately after** CSV import completes at 2:05pm PT
- Only sync instruments that were actually traded (found in CSV)
- Download complete OHLC history for all available timeframes
- Single daily sync replaces all existing sync schedules

## User Stories

- As a trader, I want OHLC data synced automatically after my daily import so I have complete candlestick data for all my traded instruments
- As a trader, I want **all available Yahoo Finance timeframes** downloaded so I can analyze price action at any granularity
- As a system operator, I want OHLC sync to happen once daily (not hourly) to reduce API usage and system load
- As a developer, I want OHLC sync integrated with import so data is available immediately for position analysis and charting

## Specific Requirements

### Integration Requirements

**Trigger Mechanism:**
- OHLC sync runs **immediately after** CSV import completes successfully
- Triggered by import completion event, not separate schedule
- Only runs when import finds and processes a CSV file
- If import fails or no CSV file found, OHLC sync does not run

**Timing:**
- Daily import scheduler runs at **2:05pm Pacific Time**
- OHLC sync starts immediately when import completes (typically 2:05-2:10pm PT)
- Entire workflow completes before 3pm PT when new trading session begins

### Instrument Selection Requirements

**Source of Instruments:**
- Extract unique instruments from the **CSV file being imported**
- Parse the "Instrument" column to get full instrument names (e.g., "MNQ 12-24", "MES 12-24")
- Map CSV instrument names to Yahoo Finance ticker symbols
- Download OHLC for each unique instrument found

**Instrument Mapping:**
- Use existing `config/instrument_multipliers.json` mappings
- Map NinjaTrader contract names to Yahoo Finance symbols
- Handle futures contract rollovers (different expiration months)
- Example mappings:
  - "MNQ 12-24" → "NQ=F" (E-mini NASDAQ-100 Futures)
  - "MES 12-24" → "ES=F" (E-mini S&P 500 Futures)
  - "MGC 12-24" → "GC=F" (Gold Futures)

**Error Handling:**
- If instrument not found in mapping, log warning and skip
- If Yahoo Finance API fails for an instrument, log error and continue with others
- Do not fail entire sync if one instrument fails

### Timeframe Requirements

**Complete Yahoo Finance Coverage:**

Download **ALL 18 available Yahoo Finance timeframes** (not just current 8):

**Minute Intervals:**
- `1m` - 1 minute (7 days historical max)
- `2m` - 2 minutes (60 days historical max) ⭐ NEW
- `5m` - 5 minutes (60 days historical max)
- `15m` - 15 minutes (60 days historical max)
- `30m` - 30 minutes (60 days historical max)
- `60m` - 60 minutes (60 days historical max) ⭐ NEW
- `90m` - 90 minutes (60 days historical max) ⭐ NEW

**Hourly Intervals:**
- `1h` - 1 hour (730 days historical max)
- `2h` - 2 hours (730 days historical max) ⭐ NEW
- `4h` - 4 hours (730 days historical max)
- `6h` - 6 hours (730 days historical max) ⭐ NEW
- `8h` - 8 hours (730 days historical max) ⭐ NEW
- `12h` - 12 hours (730 days historical max) ⭐ NEW

**Daily and Longer:**
- `1d` - 1 day (unlimited historical)
- `5d` - 5 days (unlimited historical) ⭐ NEW
- `1wk` - 1 week (unlimited historical) ⭐ NEW
- `1mo` - 1 month (unlimited historical) ⭐ NEW
- `3mo` - 3 months (unlimited historical) ⭐ NEW

**Timeframe Mapping:**
- `3m` maps to `5m` (Yahoo Finance does not support 3m directly)
- All other timeframes use Yahoo Finance native intervals

### Data Retention Requirements

**Historical Data Window:**
- **1m timeframe**: Last 7 days (Yahoo Finance limit)
- **Intraday (2m-90m, 1h-12h)**: Last 60 days (Yahoo Finance limit)
- **Daily+ (1d-3mo)**: Last 365 days (configurable, no Yahoo limit)

**Incremental Updates:**
- Only download new data since last sync (gap filling)
- Append new candles to existing database records
- Update most recent incomplete candle if still forming

**Database Storage:**
- Store in `ohlc_data` table (existing schema)
- Columns: `id`, `instrument`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`
- Indexes on `(instrument, timeframe, timestamp)` for fast queries
- Deduplicate on insert (ignore duplicate timestamp entries)

### Sync Schedule Replacement

**Remove ALL Existing Schedules:**
- ❌ Remove hourly OHLC sync
- ❌ Remove daily 2am UTC OHLC sync
- ❌ Remove weekly Sunday 3am UTC OHLC sync
- ✅ Keep ONLY the new daily post-import OHLC sync

**New Single Daily Sync:**
- Runs at 2:05pm PT (triggered by import completion)
- Downloads OHLC for all instruments in imported CSV
- Downloads all 18 Yahoo Finance timeframes
- No other automated syncs throughout the day

**Manual Sync Capability:**
- Retain ability to manually trigger OHLC sync via API endpoint
- Admin can run `/api/sync/ohlc` manually if needed
- Manual sync can specify custom instrument list and timeframes

### Performance Requirements

**API Rate Limiting:**
- Yahoo Finance: ~2000 requests/hour limit (unofficial)
- Batch instruments to stay under rate limits
- 18 timeframes × N instruments = 18N API calls
- Example: 5 instruments = 90 API calls (well under limit)
- Add 100ms delay between API calls to avoid rate limiting

**Execution Time:**
- Target: Complete within 5 minutes for typical 3-5 instruments
- Maximum: 15 minutes for 10+ instruments
- Timeout: 30 minutes absolute maximum, log error if exceeded

**Concurrency:**
- Download timeframes sequentially for each instrument (avoid rate limits)
- Process multiple instruments in parallel (max 3 concurrent workers)
- Use thread pool for parallel instrument downloads

### Error Handling and Logging

**Critical Failures:**
- Import process fails → Do NOT run OHLC sync
- All instruments fail to sync → Log critical error, send alert
- Database connection fails → Log critical error, retry once

**Partial Failures:**
- Some instruments fail → Log warnings, continue with others
- Some timeframes fail → Log warnings, continue with other timeframes
- API rate limit hit → Wait 60 seconds, retry once

**Logging Requirements:**
- Log sync start with trigger reason (post-import)
- Log each instrument being synced with timeframes
- Log API call counts and timing metrics
- Log success/failure for each instrument/timeframe combination
- Log total sync duration and summary statistics

**Success Metrics:**
```
OHLC Sync Summary (triggered by import):
- Instruments synced: 5
- Timeframes synced: 18
- Total candles added: 12,450
- API calls made: 90
- Duration: 3m 45s
- Failures: 0
```

## Technical Implementation (Python)

### Architecture Changes

**1. Modify Daily Import Scheduler**

File: `services/daily_import_scheduler.py`

Add post-import hook to trigger OHLC sync:

```python
class DailyImportScheduler:
    def __init__(self):
        self.ohlc_service = OHLCDataService()

    def run_daily_import(self):
        """Run daily import at 2:05pm PT"""
        try:
            # Import CSV file
            csv_file = self.find_csv_file()
            if csv_file:
                imported_instruments = self.import_csv(csv_file)

                # Trigger OHLC sync immediately after successful import
                if imported_instruments:
                    self.trigger_ohlc_sync(imported_instruments)
            else:
                logger.info("No CSV file found, skipping import and OHLC sync")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            # Do NOT run OHLC sync if import fails

    def trigger_ohlc_sync(self, instruments):
        """Trigger OHLC sync for imported instruments"""
        logger.info(f"Triggering OHLC sync for {len(instruments)} instruments")

        # Get all available Yahoo Finance timeframes
        all_timeframes = self.ohlc_service.get_all_yahoo_timeframes()

        # Sync OHLC data
        self.ohlc_service.sync_instruments(
            instruments=instruments,
            timeframes=all_timeframes,
            reason="post_import"
        )
```

**2. Enhance OHLC Data Service**

File: `services/data_service.py`

Add method to get all available timeframes:

```python
class OHLCDataService:

    ALL_YAHOO_TIMEFRAMES = [
        # Minute intervals
        '1m', '2m', '5m', '15m', '30m', '60m', '90m',
        # Hourly intervals
        '1h', '2h', '4h', '6h', '8h', '12h',
        # Daily and longer
        '1d', '5d', '1wk', '1mo', '3mo'
    ]

    def get_all_yahoo_timeframes(self):
        """Return all 18 supported Yahoo Finance timeframes"""
        return self.ALL_YAHOO_TIMEFRAMES.copy()

    def sync_instruments(self, instruments, timeframes, reason="manual"):
        """
        Sync OHLC data for specified instruments and timeframes

        Args:
            instruments: List of instrument symbols (Yahoo Finance format)
            timeframes: List of timeframe strings (e.g., ['1m', '5m', '1h'])
            reason: Reason for sync ('post_import', 'manual', etc.)
        """
        logger.info(f"Starting OHLC sync (reason: {reason})")
        logger.info(f"Instruments: {len(instruments)}, Timeframes: {len(timeframes)}")

        start_time = time.time()
        stats = {
            'instruments_synced': 0,
            'timeframes_synced': 0,
            'candles_added': 0,
            'api_calls': 0,
            'failures': 0
        }

        for instrument in instruments:
            try:
                for timeframe in timeframes:
                    self._sync_instrument_timeframe(instrument, timeframe, stats)
                    time.sleep(0.1)  # 100ms delay between API calls

                stats['instruments_synced'] += 1

            except Exception as e:
                logger.error(f"Failed to sync {instrument}: {e}")
                stats['failures'] += 1
                continue

        duration = time.time() - start_time
        self._log_sync_summary(stats, duration, reason)
```

**3. Remove Old Sync Schedules**

File: `scripts/automated_data_sync.py`

```python
# DELETE THIS FILE or comment out all schedule logic:

# REMOVE: schedule.every().hour.do(sync_recent_data)
# REMOVE: schedule.every().day.at("02:00").do(sync_daily_data)
# REMOVE: schedule.every().sunday.at("03:00").do(sync_historical_data)

# Only keep manual trigger capability via API endpoint
```

**4. Update Configuration**

File: `config/config.py`

```python
# Update supported timeframes to include ALL Yahoo Finance intervals
SUPPORTED_TIMEFRAMES = [
    '1m', '2m', '5m', '15m', '30m', '60m', '90m',  # Minutes
    '1h', '2h', '4h', '6h', '8h', '12h',           # Hours
    '1d', '5d', '1wk', '1mo', '3mo'                # Daily+
]

# Remove old timeframe preference order (no longer needed)
# TIMEFRAME_PREFERENCE_ORDER = [...]  # DELETE

# Add OHLC sync configuration
OHLC_SYNC_CONFIG = {
    'enabled': True,
    'trigger': 'post_import',  # Run after daily import
    'timeframes': 'all',        # Download all available timeframes
    'max_workers': 3,           # Parallel instrument downloads
    'api_delay_ms': 100,        # Delay between API calls
    'timeout_minutes': 30       # Maximum sync duration
}
```

### Instrument Mapping Strategy

**Extract Instruments from CSV:**

```python
def extract_instruments_from_csv(csv_file):
    """
    Parse CSV and extract unique instruments

    Example CSV format:
    Instrument,Action,Qty,Price,Time,...
    MNQ 12-24,Buy,2,21250.00,11/13/2024 10:30:00 AM,...
    MES 12-24,Sell,1,6025.50,11/13/2024 11:45:00 AM,...
    """
    df = pd.read_csv(csv_file)

    # Get unique instruments from CSV
    csv_instruments = df['Instrument'].unique().tolist()

    # Map to Yahoo Finance symbols
    yahoo_symbols = []
    for instrument in csv_instruments:
        symbol = map_to_yahoo_symbol(instrument)
        if symbol:
            yahoo_symbols.append(symbol)
        else:
            logger.warning(f"No Yahoo Finance mapping for {instrument}")

    return yahoo_symbols

def map_to_yahoo_symbol(ninjatrader_name):
    """
    Map NinjaTrader instrument name to Yahoo Finance symbol

    Examples:
    - "MNQ 12-24" → "NQ=F"
    - "MES 12-24" → "ES=F"
    - "MGC 02-25" → "GC=F"
    """
    # Load instrument multipliers config
    with open('data/config/instrument_multipliers.json') as f:
        mappings = json.load(f)

    # Extract base symbol (first part before space)
    base = ninjatrader_name.split()[0] if ' ' in ninjatrader_name else ninjatrader_name

    # Look up Yahoo Finance symbol
    return mappings.get(base, {}).get('yahoo_symbol')
```

### Data Retention Logic

**Determine Fetch Window by Timeframe:**

```python
def get_fetch_window(timeframe):
    """
    Get appropriate date range for timeframe based on Yahoo Finance limits

    Returns: (start_date, end_date)
    """
    end_date = datetime.now()

    if timeframe == '1m':
        # 1-minute data: Yahoo only provides last 7 days
        start_date = end_date - timedelta(days=7)
    elif timeframe in ['2m', '5m', '15m', '30m', '60m', '90m', '1h', '2h', '4h', '6h', '8h', '12h']:
        # Intraday data: Yahoo provides up to 60 days
        start_date = end_date - timedelta(days=60)
    else:
        # Daily+ data: No Yahoo limit, fetch last 365 days
        start_date = end_date - timedelta(days=365)

    return start_date, end_date
```

## Configuration Settings

**Environment Variables:**

```bash
# OHLC Sync Configuration
OHLC_SYNC_ENABLED=true
OHLC_SYNC_TRIGGER=post_import  # post_import | manual | scheduled
OHLC_SYNC_TIMEFRAMES=all       # all | comma-separated list
OHLC_SYNC_MAX_WORKERS=3
OHLC_API_DELAY_MS=100
OHLC_SYNC_TIMEOUT_MINUTES=30
```

**Admin Configuration Panel:**
- Enable/disable daily OHLC sync
- Configure which timeframes to download
- Set API rate limiting parameters
- View sync history and statistics

## Testing Requirements

**Unit Tests:**
- Test instrument extraction from CSV
- Test NinjaTrader → Yahoo Finance symbol mapping
- Test timeframe fetch window calculation
- Test API rate limiting logic
- Test error handling for failed instruments

**Integration Tests:**
- Test full workflow: CSV import → OHLC sync triggered → Data saved
- Test with multiple instruments in CSV
- Test with all 18 timeframes
- Test partial failure handling (some instruments fail)
- Test rate limiting doesn't cause failures

**Performance Tests:**
- Benchmark sync time for 1, 5, 10 instruments
- Verify stays under 5 minutes for typical 3-5 instruments
- Verify API calls stay under 2000/hour limit
- Test concurrent worker performance

**Manual Testing:**
- Import real NinjaTrader CSV file
- Verify OHLC sync triggers automatically
- Verify all 18 timeframes are downloaded
- Verify data appears in database correctly
- Check logs show expected behavior

## Success Criteria

- ✅ OHLC sync runs immediately after successful CSV import at 2:05pm PT
- ✅ All 18 Yahoo Finance timeframes are downloaded (not just 8)
- ✅ Only instruments found in imported CSV are synced
- ✅ All old sync schedules (hourly, daily 2am, weekly) are removed
- ✅ Sync completes within 5 minutes for typical 3-5 instruments
- ✅ Partial failures don't stop entire sync (graceful degradation)
- ✅ Detailed logging shows sync progress and results
- ✅ Database contains complete OHLC data for all traded instruments
- ✅ Manual sync capability retained for admin use

## Documentation Requirements

- Update README with new OHLC sync behavior
- Document all 18 supported timeframes with historical limits
- Explain post-import trigger mechanism
- Provide troubleshooting guide for sync failures
- Document instrument mapping configuration
- Add API endpoint documentation for manual sync

## Dependencies

- Python 3.9+
- `yfinance` library version 0.2.28 or higher
- SQLite database with `ohlc_data` table
- Daily import scheduler running at 2:05pm PT
- `data/config/instrument_multipliers.json` with Yahoo Finance mappings

## Related Specifications

- [2025-11-12 NinjaTrader Session Date Export](../2025-11-12-ninjatrader-session-date-export/) - Ensures CSV files use correct session dates
- [2025-11-03 Position Boundary Detection](../2025-11-03-position-boundary-detection/) - Daily import scheduler integration point
- [2025-10-31 NinjaTrader CSV Import Fix](../2025-10-31-ninjatrader-csv-import-fix/) - CSV import service that triggers OHLC sync

## Migration Strategy

**Phase 1: Implement New Sync Logic (No Breaking Changes)**
- Add post-import OHLC sync trigger
- Keep existing schedules running in parallel
- Add all 18 timeframes to downloads
- Test with production data

**Phase 2: Monitoring and Validation (1 week)**
- Monitor new post-import sync performance
- Verify all timeframes download successfully
- Compare data completeness with old schedules
- Fix any issues discovered

**Phase 3: Deprecate Old Schedules**
- Disable hourly, daily 2am, and weekly syncs
- Monitor for 1 week to ensure no data gaps
- Permanently remove old sync code

**Rollback Plan:**
- If critical issues found, re-enable old schedules immediately
- Investigate and fix new sync logic
- Retry deprecation after fixes validated
