# Task Breakdown: Daily OHLC Sync with Import Process

## Overview
Total Tasks: 4 major task groups
Language: Python 3.9+
Estimated Duration: 1-2 weeks

## Task List

### Task Group 1: Instrument Mapping Component

**Dependencies:** None

- [ ] 1.0 Create instrument mapping component
  - [ ] 1.1 Create `services/instrument_mapper.py` file
    - Define `InstrumentMapper` class
    - Implement `__init__` with config path parameter
    - Load mappings from `data/config/instrument_multipliers.json`
  - [ ] 1.2 Implement base symbol extraction
    - Create `_extract_base_symbol()` method
    - Handle space-separated format ("MNQ 12-24" → "MNQ")
    - Handle symbols without spaces ("MES" → "MES")
  - [ ] 1.3 Implement Yahoo Finance symbol lookup
    - Create `_lookup_yahoo_symbol()` method
    - Look up base symbol in mappings dictionary
    - Return `yahoo_symbol` field from mapping
    - Return None if not found
  - [ ] 1.4 Implement batch mapping method
    - Create `map_to_yahoo()` method
    - Accept list of NinjaTrader instrument names
    - Map each to Yahoo Finance symbol
    - Remove duplicates from result
    - Log warnings for unmapped instruments
  - [ ] 1.5 Add error handling
    - Handle missing config file gracefully
    - Handle malformed JSON gracefully
    - Log errors without crashing
  - [ ] 1.6 Write unit tests
    - Test `_extract_base_symbol()` with various formats
    - Test `_lookup_yahoo_symbol()` with known mappings
    - Test `map_to_yahoo()` batch mapping
    - Test error handling for missing mappings
    - Test error handling for missing config file

**Acceptance Criteria:**
- InstrumentMapper successfully loads config file
- Base symbol extraction handles all formats correctly
- Yahoo Finance symbol lookup returns correct symbols
- Batch mapping removes duplicates
- Warnings logged for unmapped instruments
- All unit tests pass

---

### Task Group 2: Daily Import Scheduler Integration

**Dependencies:** Task Group 1

- [ ] 2.0 Integrate OHLC sync with daily import scheduler
  - [ ] 2.1 Enhance daily import scheduler initialization
    - Import `OHLCDataService` and `InstrumentMapper`
    - Initialize services in `__init__` method
    - Store references as instance variables
  - [ ] 2.2 Implement CSV instrument extraction
    - Create `_extract_instruments_from_csv()` method
    - Parse CSV file using pandas
    - Extract unique values from 'Instrument' column
    - Filter out null/empty values
    - Return list of instrument names
  - [ ] 2.3 Modify `_import_csv()` method
    - Add instrument extraction after successful import
    - Return list of extracted instruments
    - Log number of unique instruments found
  - [ ] 2.4 Implement OHLC sync trigger
    - Create `_trigger_ohlc_sync()` method
    - Accept list of NinjaTrader instrument names
    - Map instruments to Yahoo Finance symbols using InstrumentMapper
    - Get all 18 Yahoo Finance timeframes from OHLCDataService
    - Call `OHLCDataService.sync_instruments()` with mapped symbols
    - Pass reason="post_import" parameter
  - [ ] 2.5 Integrate trigger into `run_daily_import()`
    - Call `_trigger_ohlc_sync()` after successful CSV import
    - Only trigger if instruments were found
    - Do NOT trigger if import failed
    - Add try-catch around OHLC sync to prevent import rollback
  - [ ] 2.6 Add logging
    - Log when OHLC sync is triggered
    - Log number of instruments being synced
    - Log mapped Yahoo Finance symbols
    - Log if OHLC sync is skipped (no instruments or import failed)
  - [ ] 2.7 Write integration tests
    - Test full workflow: CSV import → instrument extraction → OHLC sync
    - Test with CSV containing multiple instruments
    - Test with CSV containing duplicate instruments
    - Test that import failure prevents OHLC sync
    - Test that OHLC sync failure doesn't rollback import

**Acceptance Criteria:**
- CSV import successfully extracts instruments
- Instruments are mapped to Yahoo Finance symbols
- OHLC sync is triggered after successful import
- OHLC sync is NOT triggered if import fails
- OHLC sync failure doesn't affect import success
- Integration tests pass

---

### Task Group 3: OHLC Service Expansion

**Dependencies:** None (can be done in parallel with Groups 1-2)

- [ ] 3.0 Expand OHLC service to support all 18 Yahoo Finance timeframes
  - [ ] 3.1 Update timeframe constants
    - Define `ALL_YAHOO_TIMEFRAMES` list with all 18 timeframes
    - Define `HISTORICAL_LIMITS` dictionary with data retention limits
    - Update `config/config.py` with new `SUPPORTED_TIMEFRAMES` list
  - [ ] 3.2 Implement `get_all_yahoo_timeframes()` method
    - Return copy of `ALL_YAHOO_TIMEFRAMES` list
    - Add to `OHLCDataService` class
  - [ ] 3.3 Implement `_get_fetch_window()` method
    - Accept timeframe parameter
    - Return (start_date, end_date) tuple
    - Apply 7-day limit for '1m' timeframe
    - Apply 60-day limit for intraday timeframes (2m-90m, 1h-12h)
    - Apply 365-day limit for daily+ timeframes (1d-3mo)
  - [ ] 3.4 Implement `_sync_instrument()` method
    - Accept instrument symbol and timeframes list
    - Loop through all timeframes
    - Call `_get_fetch_window()` for each timeframe
    - Call `fetch_ohlc_data()` with appropriate date range
    - Add 100ms delay between API calls (rate limiting)
    - Track statistics (candles added, API calls, timeframes synced)
    - Handle exceptions gracefully (continue with other timeframes)
    - Return statistics dictionary
  - [ ] 3.5 Implement `sync_instruments()` method
    - Accept instruments list, timeframes list, and reason parameter
    - Log sync start with parameters
    - Initialize statistics dictionary
    - Loop through all instruments
    - Call `_sync_instrument()` for each
    - Aggregate statistics
    - Calculate total duration
    - Log comprehensive summary
    - Return statistics dictionary
  - [ ] 3.6 Implement `_log_sync_summary()` method
    - Accept statistics dictionary and reason
    - Log formatted summary with all metrics
    - Include: instruments synced, timeframes synced, candles added, API calls, failures, duration
  - [ ] 3.7 Add error handling
    - Catch exceptions per instrument (continue with others)
    - Catch exceptions per timeframe (continue with others)
    - Detect and handle API rate limit errors (wait 60s, retry once)
    - Log all errors with context
  - [ ] 3.8 Write unit tests
    - Test `_get_fetch_window()` for all timeframe categories
    - Test `_sync_instrument()` with mock API calls
    - Test `sync_instruments()` aggregates statistics correctly
    - Test error handling for failed instruments
    - Test error handling for failed timeframes
    - Test rate limit handling

**Acceptance Criteria:**
- All 18 Yahoo Finance timeframes are supported
- Fetch windows are correctly calculated based on timeframe
- API rate limiting prevents exceeding limits (100ms delay)
- Partial failures don't stop entire sync
- Statistics are accurately tracked and logged
- Error handling is robust
- Unit tests pass

---

### Task Group 4: Sync Schedule Cleanup and Configuration

**Dependencies:** Task Groups 1-3

- [ ] 4.0 Remove old sync schedules and update configuration
  - [ ] 4.1 Update `config/config.py`
    - Replace `SUPPORTED_TIMEFRAMES` with all 18 timeframes
    - Remove old `TIMEFRAME_PREFERENCE_ORDER` (no longer needed)
    - Add `OHLC_SYNC_CONFIG` dictionary with all settings
    - Document each configuration option
  - [ ] 4.2 Remove old automated sync schedules
    - Open `scripts/automated_data_sync.py`
    - Remove or comment out all `schedule.every()` calls
    - Remove hourly sync function
    - Remove daily 2am UTC sync function
    - Remove weekly Sunday 3am UTC sync function
    - Add deprecation notice in file header
    - Note that manual sync capability retained via API
  - [ ] 4.3 Add feature flag support
    - Add `OHLC_SYNC_ENABLED` environment variable
    - Check flag in `run_daily_import()` before triggering sync
    - Log when sync is disabled via feature flag
  - [ ] 4.4 Update instrument multipliers config
    - Ensure `data/config/instrument_multipliers.json` has `yahoo_symbol` field
    - Add Yahoo Finance symbols for all common instruments
    - Examples: MNQ → NQ=F, MES → ES=F, MGC → GC=F, etc.
  - [ ] 4.5 Add admin API endpoint for manual sync
    - Create `POST /api/sync/ohlc` endpoint
    - Accept optional instruments list
    - Accept optional timeframes list
    - Accept optional reason parameter
    - Call `OHLCDataService.sync_instruments()`
    - Return statistics in JSON response
  - [ ] 4.6 Write documentation
    - Document new OHLC sync behavior in README
    - Document all 18 supported timeframes with limits
    - Document post-import trigger mechanism
    - Document instrument mapping configuration
    - Document manual sync API endpoint
    - Add troubleshooting guide for sync failures

**Acceptance Criteria:**
- Configuration updated with all 18 timeframes
- Old sync schedules are removed/disabled
- Feature flag controls sync enable/disable
- Instrument multipliers config has Yahoo Finance symbols
- Manual sync API endpoint works correctly
- Documentation is complete and accurate

---

### Task Group 5: Testing and Validation

**Dependencies:** Task Groups 1-4

- [ ] 5.0 Comprehensive testing and validation
  - [ ] 5.1 Performance testing
    - Benchmark sync time for 1 instrument (all 18 timeframes)
    - Benchmark sync time for 5 instruments (typical case)
    - Benchmark sync time for 10 instruments (worst case)
    - Verify stays under 5 minutes for 3-5 instruments
    - Verify API calls stay under 2000/hour limit
  - [ ] 5.2 Integration testing with real CSV files
    - Create test CSV with 3 different instruments
    - Run daily import at 2:05pm PT (use test scheduler)
    - Verify OHLC sync triggers automatically
    - Verify all 18 timeframes are downloaded for each instrument
    - Verify data appears in database correctly
    - Check logs for expected behavior
  - [ ] 5.3 Error scenario testing
    - Test import failure prevents OHLC sync
    - Test OHLC sync failure doesn't affect import
    - Test partial instrument failures (some succeed, some fail)
    - Test API rate limit handling
    - Test missing instrument mapping handling
    - Test database connection failure handling
  - [ ] 5.4 Data validation
    - Verify OHLC data for all 18 timeframes in database
    - Compare data completeness with old sync method
    - Verify no duplicate candles (unique constraint works)
    - Verify timestamps are correct for each timeframe
    - Verify OHLC values are reasonable (no zero/negative prices)
  - [ ] 5.5 Staging deployment
    - Deploy to staging environment
    - Enable feature flag: `OHLC_SYNC_ENABLED=true`
    - Monitor for 1 week
    - Compare data with production (old sync method)
    - Fix any issues discovered
  - [ ] 5.6 Production rollout
    - Deploy to production (feature flag OFF initially)
    - Enable feature flag in production
    - Run in parallel with old syncs for 1 week
    - Monitor logs, performance, and data quality
    - Verify no data gaps compared to old syncs
  - [ ] 5.7 Deprecate old syncs
    - Disable old sync schedules
    - Monitor for 1 week to ensure no data gaps
    - Permanently remove old sync code if successful
    - Update documentation with new approach

**Acceptance Criteria:**
- Performance benchmarks meet targets (<5 min for typical case)
- Integration tests pass with real CSV files
- Error scenarios handled gracefully
- Data validation confirms completeness and accuracy
- Staging deployment successful for 1 week
- Production rollout successful with no data gaps
- Old sync schedules successfully deprecated

---

## Execution Order

Recommended implementation sequence:

1. **Task Group 1: Instrument Mapping Component** (1-2 days)
   - Standalone component, no dependencies
   - Can be tested independently

2. **Task Group 3: OHLC Service Expansion** (2-3 days)
   - Can be done in parallel with Group 1
   - Expands existing service with new timeframes

3. **Task Group 2: Daily Import Scheduler Integration** (2-3 days)
   - Requires Groups 1 and 3 complete
   - Integrates all components

4. **Task Group 4: Sync Schedule Cleanup** (1 day)
   - Requires Groups 1-3 complete
   - Configuration and documentation

5. **Task Group 5: Testing and Validation** (1 week)
   - Requires all previous groups complete
   - Comprehensive testing and rollout

**Total Estimated Time:** 1-2 weeks

---

## Important Notes

### API Rate Limiting
- Yahoo Finance unofficial limit: ~2000 requests/hour
- Our approach: 100ms delay between calls
- 18 timeframes × 5 instruments = 90 API calls
- At 100ms per call = 9 seconds total
- Well under 2000/hour limit (safe margin)

### Data Retention Limits
- **1m timeframe**: Yahoo Finance only provides last 7 days
- **Intraday (2m-12h)**: Yahoo Finance provides up to 60 days
- **Daily+ (1d-3mo)**: No Yahoo Finance limit, we use 365 days

### Instrument Mapping
- NinjaTrader format: "MNQ 12-24" (symbol + expiration)
- Yahoo Finance format: "NQ=F" (continuous futures contract)
- Mapping config: `data/config/instrument_multipliers.json`
- Must have `yahoo_symbol` field for each instrument

### Error Handling Strategy
- **Critical**: Import fails → No OHLC sync
- **Partial**: Some instruments fail → Continue with others
- **Partial**: Some timeframes fail → Continue with others
- **Recoverable**: Rate limit hit → Wait 60s, retry once

### Logging Requirements
- Log sync start with trigger reason
- Log each instrument being synced
- Log API call counts and timing
- Log success/failure per instrument/timeframe
- Log comprehensive summary at end

### Testing Strategy
- Unit tests for each method
- Integration tests for full workflow
- Performance tests for various instrument counts
- Error scenario tests for robustness
- Staging deployment for 1 week validation
- Production parallel run for 1 week

### Rollback Plan
- Disable feature flag: `OHLC_SYNC_ENABLED=false`
- Re-enable old sync schedules if needed
- Investigate and fix issues
- Retry deployment after validation

---

## Success Metrics

- ✅ OHLC sync runs immediately after CSV import (within 1 minute)
- ✅ All 18 Yahoo Finance timeframes downloaded
- ✅ Only instruments from CSV are synced
- ✅ Sync completes within 5 minutes for typical 3-5 instruments
- ✅ API calls stay under 2000/hour limit
- ✅ Partial failures don't stop entire sync
- ✅ No data gaps compared to old sync method
- ✅ Old sync schedules successfully removed
- ✅ Manual sync API endpoint works for admin use
- ✅ Comprehensive documentation complete

---

## Dependencies

- Python 3.9+
- `yfinance` library version 0.2.28+
- `pandas` library for CSV parsing
- SQLite database with `ohlc_data` table
- `data/config/instrument_multipliers.json` with Yahoo Finance mappings
- Daily import scheduler running at 2:05pm PT

---

## Related Specifications

- [2025-11-12 NinjaTrader Session Date Export](../2025-11-12-ninjatrader-session-date-export/) - CSV file naming with session dates
- [2025-11-03 Position Boundary Detection](../2025-11-03-position-boundary-detection/) - Daily import scheduler
- [2025-10-31 NinjaTrader CSV Import Fix](../2025-10-31-ninjatrader-csv-import-fix/) - CSV import service
