# Technical Specification: Daily OHLC Sync Integration

## Architecture Overview

### Current Architecture (To Be Replaced)

```
┌─────────────────────────────────────────────────────────────┐
│  Automated Data Sync (scripts/automated_data_sync.py)      │
│  - Hourly sync (every hour)                                 │
│  - Daily sync (2am UTC / 6pm PT previous day)               │
│  - Weekly sync (Sunday 3am UTC)                             │
│  - Independent of import process                            │
│  - Only syncs 8 timeframes                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Daily Import Scheduler (services/daily_import_scheduler.py)│
│  - Runs at 2:05pm PT                                        │
│  - Imports CSV files                                        │
│  - NO OHLC sync integration                                 │
└─────────────────────────────────────────────────────────────┘
```

### New Architecture (Post-Implementation)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Daily Import Scheduler (services/daily_import_scheduler.py)            │
│                                                                          │
│  1. Run at 2:05pm PT                                                    │
│  2. Find and import CSV file                                            │
│  3. Extract instruments from CSV ───┐                                   │
│  4. Trigger OHLC sync ──────────────┼─> OHLCDataService                │
│                                      │   - Sync ALL 18 timeframes       │
│                                      │   - Only for CSV instruments     │
│                                      │   - Complete within 5 minutes    │
│                                      └─> Database (ohlc_data table)     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  OLD Automated Data Sync - DELETED                          │
│  ❌ No hourly sync                                           │
│  ❌ No daily 2am sync                                        │
│  ❌ No weekly sync                                           │
└─────────────────────────────────────────────────────────────┘
```

## Component Specifications

### 1. Daily Import Scheduler Enhancement

**File**: `services/daily_import_scheduler.py`

**New Methods:**

```python
class DailyImportScheduler:
    def __init__(self):
        self.csv_service = CSVImportService()
        self.ohlc_service = OHLCDataService()
        self.instrument_mapper = InstrumentMapper()

    def run_daily_import(self) -> None:
        """
        Main entry point for daily import at 2:05pm PT

        Flow:
        1. Find CSV file (NinjaTrader_Executions_YYYYMMDD.csv)
        2. Import executions from CSV
        3. Extract unique instruments
        4. Trigger OHLC sync for those instruments
        """
        try:
            logger.info("Starting daily import at 2:05pm PT")

            # Step 1: Find CSV file
            csv_file = self._find_csv_file()
            if not csv_file:
                logger.info("No CSV file found, skipping import and OHLC sync")
                return

            # Step 2: Import CSV
            imported_instruments = self._import_csv(csv_file)
            if not imported_instruments:
                logger.warning("CSV import succeeded but no instruments found")
                return

            # Step 3: Trigger OHLC sync
            self._trigger_ohlc_sync(imported_instruments)

        except Exception as e:
            logger.error(f"Daily import failed: {e}", exc_info=True)
            # Do NOT run OHLC sync if import fails

    def _import_csv(self, csv_file: str) -> List[str]:
        """
        Import CSV file and extract unique instruments

        Args:
            csv_file: Full path to CSV file

        Returns:
            List of unique instrument names (NinjaTrader format)

        Example:
            ['MNQ 12-24', 'MES 12-24', 'MGC 02-25']
        """
        logger.info(f"Importing CSV file: {csv_file}")

        # Import executions (existing logic)
        self.csv_service.import_file(csv_file)

        # Extract unique instruments
        instruments = self._extract_instruments_from_csv(csv_file)

        logger.info(f"Extracted {len(instruments)} unique instruments: {instruments}")
        return instruments

    def _extract_instruments_from_csv(self, csv_file: str) -> List[str]:
        """
        Parse CSV and extract unique instrument names

        CSV Format:
        Instrument,Action,Qty,Price,Time,...
        MNQ 12-24,Buy,2,21250.00,11/13/2024 10:30:00 AM,...
        MES 12-24,Sell,1,6025.50,11/13/2024 11:45:00 AM,...
        """
        df = pd.read_csv(csv_file)

        # Get unique values from Instrument column
        unique_instruments = df['Instrument'].unique().tolist()

        # Filter out any null/empty values
        instruments = [inst for inst in unique_instruments if inst and pd.notna(inst)]

        return instruments

    def _trigger_ohlc_sync(self, ninjatrader_instruments: List[str]) -> None:
        """
        Trigger OHLC sync for specified instruments

        Args:
            ninjatrader_instruments: List of NinjaTrader instrument names
                Example: ['MNQ 12-24', 'MES 12-24']

        Flow:
        1. Map NinjaTrader names to Yahoo Finance symbols
        2. Get all 18 Yahoo Finance timeframes
        3. Call OHLC service to sync
        """
        logger.info(f"Triggering OHLC sync for {len(ninjatrader_instruments)} instruments")

        # Map to Yahoo Finance symbols
        yahoo_symbols = self.instrument_mapper.map_to_yahoo(ninjatrader_instruments)
        if not yahoo_symbols:
            logger.warning("No valid Yahoo Finance symbols found, skipping OHLC sync")
            return

        logger.info(f"Mapped to Yahoo symbols: {yahoo_symbols}")

        # Get all available timeframes
        all_timeframes = self.ohlc_service.get_all_yahoo_timeframes()

        # Sync OHLC data
        self.ohlc_service.sync_instruments(
            instruments=yahoo_symbols,
            timeframes=all_timeframes,
            reason="post_import"
        )
```

### 2. Instrument Mapper Component

**File**: `services/instrument_mapper.py` (NEW)

```python
class InstrumentMapper:
    """
    Maps NinjaTrader instrument names to Yahoo Finance symbols

    Uses: data/config/instrument_multipliers.json
    """

    def __init__(self, config_path: str = 'data/config/instrument_multipliers.json'):
        self.config_path = config_path
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Dict]:
        """
        Load instrument mappings from JSON config

        Expected format:
        {
            "MNQ": {
                "name": "Micro E-mini NASDAQ-100",
                "yahoo_symbol": "NQ=F",
                "multiplier": 2,
                "tick_size": 0.25
            },
            ...
        }
        """
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load instrument mappings: {e}")
            return {}

    def map_to_yahoo(self, ninjatrader_instruments: List[str]) -> List[str]:
        """
        Map NinjaTrader instrument names to Yahoo Finance symbols

        Args:
            ninjatrader_instruments: List of NinjaTrader format names
                Example: ['MNQ 12-24', 'MES 12-24', 'MGC 02-25']

        Returns:
            List of Yahoo Finance symbols
                Example: ['NQ=F', 'ES=F', 'GC=F']

        Logic:
        - Extract base symbol (part before space)
        - Look up in mappings dictionary
        - Return yahoo_symbol field
        """
        yahoo_symbols = []

        for nt_instrument in ninjatrader_instruments:
            # Extract base symbol (e.g., "MNQ 12-24" -> "MNQ")
            base_symbol = self._extract_base_symbol(nt_instrument)

            # Look up Yahoo Finance symbol
            yahoo_symbol = self._lookup_yahoo_symbol(base_symbol)

            if yahoo_symbol:
                yahoo_symbols.append(yahoo_symbol)
            else:
                logger.warning(f"No Yahoo Finance mapping for '{nt_instrument}' (base: '{base_symbol}')")

        return list(set(yahoo_symbols))  # Remove duplicates

    def _extract_base_symbol(self, nt_instrument: str) -> str:
        """
        Extract base symbol from NinjaTrader instrument name

        Examples:
        - "MNQ 12-24" -> "MNQ"
        - "MES 03-25" -> "MES"
        - "MGC" -> "MGC"
        """
        return nt_instrument.split()[0] if ' ' in nt_instrument else nt_instrument

    def _lookup_yahoo_symbol(self, base_symbol: str) -> Optional[str]:
        """
        Look up Yahoo Finance symbol for base symbol

        Args:
            base_symbol: Base symbol (e.g., "MNQ", "MES")

        Returns:
            Yahoo Finance symbol (e.g., "NQ=F") or None if not found
        """
        if base_symbol in self.mappings:
            return self.mappings[base_symbol].get('yahoo_symbol')
        return None
```

### 3. OHLC Data Service Enhancements

**File**: `services/data_service.py`

**New Constants:**

```python
# Complete list of all Yahoo Finance supported timeframes
ALL_YAHOO_TIMEFRAMES = [
    # Minute intervals (7-60 day historical limit)
    '1m', '2m', '5m', '15m', '30m', '60m', '90m',

    # Hourly intervals (730 day historical limit)
    '1h', '2h', '4h', '6h', '8h', '12h',

    # Daily and longer (unlimited historical)
    '1d', '5d', '1wk', '1mo', '3mo'
]

# Historical data limits by timeframe category
HISTORICAL_LIMITS = {
    '1m': 7,      # 7 days max
    'intraday': 60,   # 60 days max for 2m-90m, 1h-12h
    'daily': 365      # 365 days for 1d-3mo (configurable)
}
```

**New Methods:**

```python
class OHLCDataService:

    def get_all_yahoo_timeframes(self) -> List[str]:
        """
        Return all 18 supported Yahoo Finance timeframes

        Returns:
            List of timeframe strings
        """
        return ALL_YAHOO_TIMEFRAMES.copy()

    def sync_instruments(
        self,
        instruments: List[str],
        timeframes: List[str],
        reason: str = "manual"
    ) -> Dict[str, Any]:
        """
        Sync OHLC data for specified instruments and timeframes

        Args:
            instruments: List of Yahoo Finance symbols (e.g., ['NQ=F', 'ES=F'])
            timeframes: List of timeframe strings (e.g., ['1m', '5m', '1h'])
            reason: Reason for sync ('post_import', 'manual', etc.)

        Returns:
            Statistics dictionary with sync results

        Example return:
        {
            'instruments_synced': 5,
            'timeframes_synced': 18,
            'total_candles_added': 12450,
            'api_calls': 90,
            'failures': 0,
            'duration_seconds': 225.5
        }
        """
        logger.info(f"=== OHLC Sync Started (reason: {reason}) ===")
        logger.info(f"Instruments: {len(instruments)}, Timeframes: {len(timeframes)}")

        start_time = time.time()
        stats = {
            'instruments_synced': 0,
            'timeframes_synced': 0,
            'total_candles_added': 0,
            'api_calls': 0,
            'failures': 0,
            'duration_seconds': 0
        }

        # Sync each instrument
        for instrument in instruments:
            try:
                instrument_stats = self._sync_instrument(instrument, timeframes)

                stats['instruments_synced'] += 1
                stats['timeframes_synced'] += instrument_stats['timeframes_synced']
                stats['total_candles_added'] += instrument_stats['candles_added']
                stats['api_calls'] += instrument_stats['api_calls']

            except Exception as e:
                logger.error(f"Failed to sync instrument {instrument}: {e}")
                stats['failures'] += 1
                continue

        # Calculate duration
        stats['duration_seconds'] = time.time() - start_time

        # Log summary
        self._log_sync_summary(stats, reason)

        return stats

    def _sync_instrument(
        self,
        instrument: str,
        timeframes: List[str]
    ) -> Dict[str, int]:
        """
        Sync all timeframes for a single instrument

        Args:
            instrument: Yahoo Finance symbol (e.g., 'NQ=F')
            timeframes: List of timeframes to sync

        Returns:
            Statistics for this instrument
        """
        logger.info(f"Syncing instrument: {instrument}")

        stats = {
            'timeframes_synced': 0,
            'candles_added': 0,
            'api_calls': 0
        }

        for timeframe in timeframes:
            try:
                # Get appropriate date range for this timeframe
                start_date, end_date = self._get_fetch_window(timeframe)

                # Fetch data from Yahoo Finance
                candles = self.fetch_ohlc_data(
                    instrument=instrument,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )

                stats['api_calls'] += 1
                stats['timeframes_synced'] += 1
                stats['candles_added'] += len(candles) if candles else 0

                logger.debug(f"  {timeframe}: {len(candles) if candles else 0} candles")

                # Rate limiting: 100ms delay between API calls
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to sync {instrument} @ {timeframe}: {e}")
                continue

        logger.info(f"Completed {instrument}: {stats['timeframes_synced']} timeframes, "
                   f"{stats['candles_added']} candles, {stats['api_calls']} API calls")

        return stats

    def _get_fetch_window(self, timeframe: str) -> Tuple[datetime, datetime]:
        """
        Get appropriate date range for timeframe based on Yahoo Finance limits

        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')

        Returns:
            Tuple of (start_date, end_date)

        Historical Limits:
        - 1m: 7 days max
        - 2m-90m, 1h-12h: 60 days max (intraday)
        - 1d-3mo: 365 days (configurable, no Yahoo limit)
        """
        end_date = datetime.now()

        if timeframe == '1m':
            # 1-minute data: Yahoo only provides last 7 days
            start_date = end_date - timedelta(days=HISTORICAL_LIMITS['1m'])

        elif timeframe in ['2m', '5m', '15m', '30m', '60m', '90m',
                          '1h', '2h', '4h', '6h', '8h', '12h']:
            # Intraday data: Yahoo provides up to 60 days
            start_date = end_date - timedelta(days=HISTORICAL_LIMITS['intraday'])

        else:
            # Daily+ data: No Yahoo limit, fetch configured window
            start_date = end_date - timedelta(days=HISTORICAL_LIMITS['daily'])

        return start_date, end_date

    def _log_sync_summary(self, stats: Dict[str, Any], reason: str) -> None:
        """
        Log comprehensive sync summary

        Args:
            stats: Statistics dictionary from sync operation
            reason: Reason for sync
        """
        logger.info("=== OHLC Sync Summary ===")
        logger.info(f"Trigger: {reason}")
        logger.info(f"Instruments synced: {stats['instruments_synced']}")
        logger.info(f"Timeframes synced: {stats['timeframes_synced']}")
        logger.info(f"Total candles added: {stats['total_candles_added']}")
        logger.info(f"API calls made: {stats['api_calls']}")
        logger.info(f"Failures: {stats['failures']}")
        logger.info(f"Duration: {stats['duration_seconds']:.1f}s")
        logger.info("========================")
```

### 4. Configuration Updates

**File**: `config/config.py`

```python
# ============================================================================
# OHLC DATA SYNC CONFIGURATION
# ============================================================================

# All supported Yahoo Finance timeframes (18 total)
SUPPORTED_TIMEFRAMES = [
    # Minute intervals
    '1m', '2m', '5m', '15m', '30m', '60m', '90m',

    # Hourly intervals
    '1h', '2h', '4h', '6h', '8h', '12h',

    # Daily and longer
    '1d', '5d', '1wk', '1mo', '3mo'
]

# OHLC sync configuration
OHLC_SYNC_CONFIG = {
    # Enable/disable OHLC sync
    'enabled': True,

    # Trigger mode: 'post_import' | 'manual' | 'disabled'
    'trigger': 'post_import',

    # Timeframes to download: 'all' or list of specific timeframes
    'timeframes': 'all',

    # Maximum concurrent instrument downloads (parallel workers)
    'max_workers': 3,

    # Delay between API calls (milliseconds)
    'api_delay_ms': 100,

    # Maximum sync duration before timeout (minutes)
    'timeout_minutes': 30,

    # Historical data limits (days)
    'historical_limits': {
        '1m': 7,        # 1-minute data: 7 days max
        'intraday': 60,  # Intraday: 60 days max
        'daily': 365     # Daily+: 365 days
    }
}

# Remove old timeframe preference order (no longer needed)
# TIMEFRAME_PREFERENCE_ORDER = [...]  # DELETED
```

### 5. Automated Sync Removal

**File**: `scripts/automated_data_sync.py`

**Action**: Delete entire file or comment out all schedule logic

```python
# ============================================================================
# THIS FILE IS DEPRECATED - OHLC sync now runs via daily import scheduler
# ============================================================================

# OLD CODE - REMOVED:
# schedule.every().hour.do(sync_recent_data)
# schedule.every().day.at("02:00").do(sync_daily_data)
# schedule.every().sunday.at("03:00").do(sync_historical_data)

# Manual sync capability retained via API endpoint:
# POST /api/sync/ohlc
```

## Database Schema

**Table**: `ohlc_data` (existing, no changes)

```sql
CREATE TABLE IF NOT EXISTS ohlc_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument, timeframe, timestamp)
);

CREATE INDEX idx_ohlc_instrument_timeframe ON ohlc_data(instrument, timeframe);
CREATE INDEX idx_ohlc_timestamp ON ohlc_data(timestamp);
```

## API Endpoints

### Manual OHLC Sync (Retained)

**Endpoint**: `POST /api/sync/ohlc`

**Request Body**:
```json
{
    "instruments": ["NQ=F", "ES=F"],  // Optional, defaults to all active
    "timeframes": ["1m", "5m", "1h"],  // Optional, defaults to all 18
    "reason": "manual"                 // Optional
}
```

**Response**:
```json
{
    "status": "success",
    "message": "OHLC sync completed",
    "stats": {
        "instruments_synced": 2,
        "timeframes_synced": 36,
        "total_candles_added": 8420,
        "api_calls": 36,
        "failures": 0,
        "duration_seconds": 145.2
    }
}
```

## Error Handling

### Critical Failures

**1. Import Fails → No OHLC Sync**
```python
try:
    self._import_csv(csv_file)
except Exception as e:
    logger.error(f"CSV import failed: {e}")
    # Do NOT trigger OHLC sync
    return
```

**2. All Instruments Fail**
```python
if stats['instruments_synced'] == 0:
    logger.critical("OHLC sync failed for ALL instruments")
    # Send alert to admin
    send_alert("OHLC sync total failure")
```

**3. Database Connection Fails**
```python
try:
    self._save_candles_to_db(candles)
except DatabaseError as e:
    logger.critical(f"Database connection failed: {e}")
    # Retry once after 5 seconds
    time.sleep(5)
    self._save_candles_to_db(candles)
```

### Partial Failures

**1. Some Instruments Fail**
```python
# Continue with other instruments
except Exception as e:
    logger.error(f"Failed to sync {instrument}: {e}")
    stats['failures'] += 1
    continue  # Move to next instrument
```

**2. Some Timeframes Fail**
```python
# Continue with other timeframes
except Exception as e:
    logger.error(f"Failed to sync {instrument} @ {timeframe}: {e}")
    continue  # Move to next timeframe
```

**3. API Rate Limit Hit**
```python
try:
    candles = yf.Ticker(instrument).history(...)
except Exception as e:
    if "rate limit" in str(e).lower():
        logger.warning("Rate limit hit, waiting 60 seconds")
        time.sleep(60)
        candles = yf.Ticker(instrument).history(...)  # Retry once
```

## Performance Considerations

### API Rate Limiting

**Yahoo Finance Limits** (unofficial):
- ~2000 requests/hour
- No official documentation, conservative approach recommended

**Our Strategy**:
- 100ms delay between API calls
- Maximum 600 calls in 10 minutes
- Well under 2000/hour limit even with 18 timeframes × 10 instruments

**Calculation**:
```
18 timeframes × 5 instruments = 90 API calls
At 100ms per call = 9 seconds
Well under 2000/hour limit (safe margin)
```

### Concurrent Processing

**Parallel Workers**:
```python
from concurrent.futures import ThreadPoolExecutor

def sync_instruments(self, instruments, timeframes):
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(self._sync_instrument, inst, timeframes)
            for inst in instruments
        ]

        for future in futures:
            try:
                result = future.result(timeout=600)  # 10 min per instrument
            except Exception as e:
                logger.error(f"Worker failed: {e}")
```

**Why 3 workers?**
- Balance between speed and API rate limits
- 3 instruments × 18 timeframes = 54 concurrent potential calls
- 100ms delay keeps us under rate limits

### Timeout Handling

**Per-Instrument Timeout**: 10 minutes
```python
result = future.result(timeout=600)
```

**Total Sync Timeout**: 30 minutes
```python
@timeout_decorator.timeout(1800)  # 30 minutes
def sync_instruments(self, instruments, timeframes):
    ...
```

## Testing Strategy

### Unit Tests

**Test**: `test_instrument_mapper.py`
```python
def test_extract_base_symbol():
    mapper = InstrumentMapper()
    assert mapper._extract_base_symbol("MNQ 12-24") == "MNQ"
    assert mapper._extract_base_symbol("MES") == "MES"

def test_map_to_yahoo():
    mapper = InstrumentMapper()
    result = mapper.map_to_yahoo(["MNQ 12-24", "MES 03-25"])
    assert "NQ=F" in result
    assert "ES=F" in result
```

**Test**: `test_ohlc_sync.py`
```python
def test_get_fetch_window():
    service = OHLCDataService()

    # 1m should return 7 days
    start, end = service._get_fetch_window('1m')
    assert (end - start).days == 7

    # 5m should return 60 days
    start, end = service._get_fetch_window('5m')
    assert (end - start).days == 60

    # 1d should return 365 days
    start, end = service._get_fetch_window('1d')
    assert (end - start).days == 365
```

### Integration Tests

**Test**: Full import-to-sync workflow
```python
def test_full_import_sync_workflow():
    # 1. Create test CSV file
    csv_file = create_test_csv([
        {"Instrument": "MNQ 12-24", "Action": "Buy", "Qty": 2},
        {"Instrument": "MES 12-24", "Action": "Sell", "Qty": 1}
    ])

    # 2. Run import
    scheduler = DailyImportScheduler()
    scheduler.run_daily_import()

    # 3. Verify OHLC data was synced
    assert ohlc_data_exists("NQ=F", "1m")
    assert ohlc_data_exists("ES=F", "5m")
    assert ohlc_data_exists("NQ=F", "1d")

    # 4. Verify all 18 timeframes synced
    for timeframe in ALL_YAHOO_TIMEFRAMES:
        assert ohlc_data_exists("NQ=F", timeframe)
```

### Performance Tests

**Test**: Sync time for various instrument counts
```python
@pytest.mark.performance
def test_sync_performance():
    instruments = ["NQ=F", "ES=F", "GC=F", "CL=F", "ZB=F"]

    start = time.time()
    service.sync_instruments(instruments, ALL_YAHOO_TIMEFRAMES)
    duration = time.time() - start

    # Should complete within 5 minutes for 5 instruments
    assert duration < 300
```

## Deployment Strategy

### Phase 1: Implementation (Week 1)
- Implement all new code
- Keep old sync schedules running
- Add feature flag: `OHLC_SYNC_ENABLED=false`
- Deploy to staging

### Phase 2: Testing (Week 2)
- Enable feature flag in staging
- Monitor for 1 week
- Compare data completeness with old syncs
- Verify no data gaps
- Fix any issues discovered

### Phase 3: Production Rollout (Week 3)
- Enable feature flag in production
- Run in parallel with old syncs for 1 week
- Monitor logs and performance
- Verify data quality

### Phase 4: Deprecation (Week 4)
- Disable old sync schedules
- Monitor for data gaps
- If successful, remove old sync code
- Update documentation

### Rollback Plan
- Disable feature flag: `OHLC_SYNC_ENABLED=false`
- Re-enable old sync schedules
- Investigate issues
- Fix and redeploy

## Monitoring and Alerts

### Metrics to Track
- Sync success rate (% of successful syncs)
- Average sync duration
- API call count per day
- Instruments synced per day
- Timeframes synced per day
- Failure rate by instrument
- Failure rate by timeframe

### Alerts
- **Critical**: All instruments failed to sync
- **Warning**: >50% of instruments failed
- **Warning**: Sync duration >15 minutes
- **Info**: Sync completed successfully

### Logging
```
2025-11-13 14:05:02 [INFO] Starting daily import at 2:05pm PT
2025-11-13 14:05:05 [INFO] Extracted 5 unique instruments
2025-11-13 14:05:05 [INFO] Mapped to Yahoo symbols: ['NQ=F', 'ES=F', 'GC=F', 'CL=F', 'ZB=F']
2025-11-13 14:05:05 [INFO] === OHLC Sync Started (reason: post_import) ===
2025-11-13 14:05:05 [INFO] Instruments: 5, Timeframes: 18
2025-11-13 14:05:10 [INFO] Syncing instrument: NQ=F
2025-11-13 14:05:45 [INFO] Completed NQ=F: 18 timeframes, 2450 candles, 18 API calls
...
2025-11-13 14:08:30 [INFO] === OHLC Sync Summary ===
2025-11-13 14:08:30 [INFO] Trigger: post_import
2025-11-13 14:08:30 [INFO] Instruments synced: 5
2025-11-13 14:08:30 [INFO] Timeframes synced: 90
2025-11-13 14:08:30 [INFO] Total candles added: 12,450
2025-11-13 14:08:30 [INFO] API calls made: 90
2025-11-13 14:08:30 [INFO] Failures: 0
2025-11-13 14:08:30 [INFO] Duration: 205.3s
2025-11-13 14:08:30 [INFO] ========================
```
