# Task Breakdown: Daily OHLC Import Fix

## Overview
Total Tasks: 4 major task groups with 23 sub-tasks

**Root Causes Being Fixed:**
1. Timezone Mismatch - Scheduler runs at 6:05 AM Pacific instead of 2:05 PM Pacific
2. Redis Connection - Wrong hostname preventing OHLC sync
3. Missing Historical Data - Need auto-backfill for last 365 days

**Files to Modify:**
- `services/daily_import_scheduler.py` (timezone-aware scheduling)
- `services/data_service.py` (auto-backfill logic)
- `.env` (Redis configuration)
- `docker-compose.dev.yml`, `docker-compose.yml`, `docker-compose.prod.yml` (documentation)
- `requirements.txt` (APScheduler dependency)

## Task List

### Configuration & Dependencies

#### Task Group 1: Environment Configuration & Dependency Setup
**Dependencies:** None

- [x] 1.0 Complete configuration and dependency setup
  - [x] 1.1 Write 2-4 focused tests for configuration validation
    - Test Redis connectivity validation at startup
    - Test timezone configuration validation (Pacific Time)
    - Test cache-enabled status check
    - Limit to 2-4 critical validation scenarios only
  - [x] 1.2 Update requirements.txt with APScheduler
    - Add `APScheduler==3.10.4` to requirements.txt
    - Add `pytz==2023.3` if not already present (verify existing version)
    - Position after `schedule==1.2.0` (which will be replaced)
    - Add inline comment: `# Timezone-aware scheduling for daily OHLC imports`
  - [x] 1.3 Fix .env file Redis configuration
    - Change `REDIS_URL=redis://localhost:6379/0` to `REDIS_URL=redis://redis:6379/0`
    - Change `CACHE_ENABLED=false` to `CACHE_ENABLED=true`
    - Add comment above REDIS_URL: `# Use Docker service name 'redis' for container networking`
    - Add comment above CACHE_ENABLED: `# Required for OHLC data sync functionality`
  - [x] 1.4 Add configuration validation to daily_import_scheduler.py
    - Add _validate_redis_connection() method to test Redis ping
    - Add _validate_timezone_config() method to verify Pacific Time setup
    - Call validation methods in __init__ after setting up timezone
    - Log warnings if CACHE_ENABLED=false with helpful troubleshooting message
    - Log Redis connection status (success/failure) at scheduler startup
  - [x] 1.5 Ensure configuration validation tests pass
    - Run ONLY the 2-4 tests written in 1.1
    - Verify Redis connectivity check works correctly
    - Verify timezone validation logic is sound
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- APScheduler added to requirements.txt
- .env file has correct Docker networking values (redis://redis:6379/0, CACHE_ENABLED=true)
- Validation logic detects Redis connectivity and timezone issues
- The 2-4 tests written in 1.1 pass
- Clear startup logging shows configuration status

### Scheduler Refactoring

#### Task Group 2: Replace Schedule Library with APScheduler
**Dependencies:** Task Group 1

- [x] 2.0 Complete scheduler refactoring to APScheduler
  - [x] 2.1 Write 2-6 focused tests for scheduler functionality
    - Test scheduler starts successfully with Pacific Time timezone
    - Test scheduled job runs at correct time (14:05 Pacific)
    - Test manual import trigger still works
    - Test scheduler stop/cleanup works correctly
    - Test status endpoint returns timezone information
    - Limit to 2-6 critical scheduler scenarios only
  - [x] 2.2 Refactor daily_import_scheduler.py imports and initialization
    - Replace `import schedule` with `from apscheduler.schedulers.background import BackgroundScheduler`
    - Add `from apscheduler.triggers.cron import CronTrigger`
    - Remove `import schedule` (line 23)
    - Add `self._scheduler: Optional[BackgroundScheduler] = None` to __init__
    - Keep existing pytz import and pacific_tz initialization
  - [x] 2.3 Replace schedule library usage in start() method
    - Remove `schedule.clear()` call
    - Create BackgroundScheduler instance: `self._scheduler = BackgroundScheduler(timezone=self.pacific_tz)`
    - Replace `schedule.every().day.at(self.IMPORT_TIME_PT).do(...)` with APScheduler CronTrigger
    - Use: `self._scheduler.add_job(self._scheduled_import_callback, CronTrigger(hour=14, minute=5, timezone=self.pacific_tz))`
    - Replace `self._scheduler_thread.start()` with `self._scheduler.start()`
    - Remove threading code (APScheduler handles its own threading)
  - [x] 2.4 Update stop() method for APScheduler
    - Replace `schedule.clear()` with `self._scheduler.shutdown(wait=True)`
    - Remove thread join logic (APScheduler handles cleanup)
    - Add null check: `if self._scheduler: self._scheduler.shutdown(wait=True)`
  - [x] 2.5 Remove _scheduler_loop method entirely
    - Delete _scheduler_loop method (lines 132-148)
    - APScheduler's BackgroundScheduler handles the event loop internally
    - Remove self._scheduler_thread and self._stop_event from __init__
  - [x] 2.6 Update _get_next_import_time() for APScheduler
    - Replace `schedule.next_run()` with APScheduler's job query
    - Use: `jobs = self._scheduler.get_jobs()` then `next_run = jobs[0].next_run_time if jobs else None`
    - Convert next_run_time to Pacific Time if not None
    - Return formatted string or None
  - [x] 2.7 Enhance logging with timezone information
    - Update all log messages to include both UTC and Pacific Time where relevant
    - Example: `logger.info(f"Scheduled for 14:05 PT (22:05 UTC) - Next run: {next_run_pt}")`
    - Add timezone info to _scheduled_import_callback logs
    - Include timezone in get_status() response
  - [x] 2.8 Ensure scheduler refactoring tests pass
    - Run ONLY the 2-6 tests written in 2.1
    - Verify scheduler starts and schedules jobs correctly
    - Verify timezone handling works (14:05 Pacific = 22:05 UTC)
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- schedule library completely replaced with APScheduler
- Scheduler runs at 14:05 Pacific Time (22:05 UTC) regardless of container timezone
- All existing scheduler methods (start, stop, manual_import, get_status) still work
- Logs include clear timezone information (both UTC and Pacific)
- The 2-6 tests written in 2.1 pass

### Auto-Backfill Logic

#### Task Group 3: Implement 365-Day OHLC Auto-Backfill
**Dependencies:** Task Group 2

- [x] 3.0 Complete auto-backfill implementation
  - [x] 3.1 Write 2-6 focused tests for backfill logic
    - Test zero-record detection triggers backfill
    - Test 365-day date calculation is correct
    - Test backfill respects Yahoo Finance historical limits per timeframe
    - Test normal sync (non-zero records) uses standard window
    - Test backfill logging messages are clear
    - Limit to 2-6 critical backfill scenarios only
  - [x] 3.2 Add zero-record detection to data_service.py
    - Locate `_sync_instrument` method in OHLCDataService class
    - Add check at beginning: `record_count = FuturesDB.get_ohlc_count(instrument, timeframe)`
    - Add conditional logic: `if record_count == 0: # trigger backfill`
    - Keep existing sync logic for non-zero record counts
  - [x] 3.3 Implement 365-day backfill date calculation
    - When zero records detected, calculate: `backfill_start = datetime.now() - timedelta(days=365)`
    - Apply Yahoo Finance historical limits per timeframe (respect HISTORICAL_LIMITS dict)
    - For 1m: min(365, 7 days), 5m-12h: min(365, 60 days), 1d+: 365 days
    - Use backfill_start as start_date instead of normal _get_fetch_window result
  - [x] 3.4 Add clear backfill logging
    - Log when zero records detected: `logger.info(f"Backfilling 365 days for {instrument} {timeframe} - zero records detected")`
    - Log backfill date range: `logger.info(f"Backfill window: {backfill_start} to {datetime.now()}")`
    - Log backfill completion: `logger.info(f"Backfill complete: {candles_added} candles added for {instrument} {timeframe}")`
    - Differentiate backfill logs from normal sync logs using clear markers
  - [x] 3.5 Integrate backfill into existing _sync_instrument flow
    - Ensure backfill uses existing rate limiting and circuit breaker logic
    - Ensure backfill respects existing batch insert optimization (insert_ohlc_batch)
    - Ensure backfill updates cache correctly via cache_service
    - No changes needed to sync_instruments orchestration method
  - [x] 3.6 Ensure auto-backfill tests pass
    - Run ONLY the 2-6 tests written in 3.1
    - Verify zero-record detection works
    - Verify 365-day calculation respects Yahoo Finance limits
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- Zero OHLC records trigger automatic 365-day backfill
- Backfill respects Yahoo Finance historical limits (7d for 1m, 60d for 5m-12h, 365d for 1d+)
- Backfill integrates seamlessly with existing sync flow (rate limiting, caching, batch insert)
- Clear logging distinguishes backfill from normal sync operations
- The 2-6 tests written in 3.1 pass

### Documentation

#### Task Group 4: Docker Compose Documentation
**Dependencies:** None (can be done in parallel with other groups)

- [x] 4.0 Complete Docker Compose documentation
  - [x] 4.1 Add header comments to docker-compose.dev.yml
    - Add comment block at top explaining this is for local development
    - Document Redis service inclusion: "Includes Redis container for local dev environment"
    - Document default values: "REDIS_URL defaults to redis://redis:6379/0 (Docker service name)"
    - Document .env override warning: "Note: .env file values will override these defaults"
    - Add comment above REDIS_URL environment variable explaining Docker networking
  - [x] 4.2 Add header comments to docker-compose.yml
    - Add comment block explaining: "Local build without Redis - for users without Docker networking"
    - Document: "Redis must be run separately or CACHE_ENABLED should be set to false"
    - Document: "This builds the image locally instead of pulling from GHCR"
    - Add comment explaining REDIS_URL should point to external Redis if used
  - [x] 4.3 Add header comments to docker-compose.prod.yml
    - Add comment block explaining: "Production deployment using pre-built GHCR image"
    - Document: "Uses ghcr.io/yourusername/futurestradinglog:latest from GitHub Container Registry"
    - Document Watchtower integration: "Includes Watchtower for automatic image updates"
    - Document Redis strategy: "Redis should be configured via .env to point to production instance"
    - Add comment explaining image pull and update strategy
  - [x] 4.4 Add troubleshooting notes to all docker-compose files
    - Add comment section: "Troubleshooting Redis connectivity"
    - Document localhost vs service name: "Use 'redis' for Docker networking, 'localhost' for external"
    - Document .env priority: ".env file values take precedence over docker-compose defaults"
    - Add comment about verifying container networking: "Ensure containers are on same Docker network"
  - [x] 4.5 Verify documentation clarity and accuracy
    - Review all added comments for clarity and usefulness
    - Ensure comments explain "why" not just "what"
    - Verify technical accuracy of Docker networking explanations
    - Ensure comments follow project commenting standards (concise, evergreen)

**Acceptance Criteria:**
- docker-compose.dev.yml has clear header explaining local dev setup with Redis
- docker-compose.yml has clear header explaining local build without Redis
- docker-compose.prod.yml has clear header explaining GHCR image and Watchtower
- All files have inline comments explaining REDIS_URL and Docker networking
- Troubleshooting notes help users understand .env override behavior
- Comments are concise, helpful, and evergreen (no temporary notes)

### Integration Testing

#### Task Group 5: End-to-End Integration Testing
**Dependencies:** Task Groups 1-3

- [x] 5.0 Verify complete system integration
  - [x] 5.1 Review and analyze existing tests
    - Review the 2-4 configuration tests from Task 1.1
    - Review the 2-6 scheduler tests from Task 2.1
    - Review the 2-6 backfill tests from Task 3.1
    - Total existing tests: approximately 6-16 tests
    - Identify any critical gaps in integration testing
  - [x] 5.2 Write up to 6 additional integration tests maximum
    - Test full flow: scheduler start -> Redis connect -> OHLC sync trigger -> backfill
    - Test scheduler runs at correct Pacific Time (mocked time check)
    - Test post-import OHLC sync with zero records triggers backfill
    - Test backfill completes successfully for multiple instruments
    - Test configuration validation prevents startup with bad Redis config
    - Focus on end-to-end workflows, not unit test gaps
    - Maximum 6 new integration tests to fill critical gaps only
  - [x] 5.3 Run all feature-specific tests
    - Run configuration tests (1.1): 2-4 tests
    - Run scheduler tests (2.1): 2-6 tests
    - Run backfill tests (3.1): 2-6 tests
    - Run integration tests (5.2): up to 6 tests
    - Expected total: approximately 12-22 tests maximum
    - Do NOT run entire application test suite
    - Focus only on tests related to this daily OHLC import fix
  - [x] 5.4 Manual verification in Docker dev environment
    - Start containers: `docker-compose -f docker-compose.dev.yml up -d`
    - Verify .env has correct values (redis://redis:6379/0, CACHE_ENABLED=true)
    - Check scheduler startup logs show Redis connection success
    - Check scheduler logs show correct Pacific Time scheduling (14:05 PT = 22:05 UTC)
    - Trigger manual import and verify OHLC sync runs
    - Verify zero-record instruments trigger 365-day backfill
    - Check logs for clear backfill vs normal sync differentiation
  - [x] 5.5 Verify timezone correctness
    - Check scheduler next run time is 14:05 Pacific (22:05 UTC)
    - Verify container running in UTC doesn't affect Pacific Time scheduling
    - Test across DST boundary if possible (Pacific Time vs Pacific Daylight Time)
    - Confirm logs show both UTC and Pacific Time for clarity
  - [x] 5.6 Verify Redis connectivity and caching
    - Verify Flask container can connect to Redis using service name
    - Test cache read/write operations work correctly
    - Verify OHLC sync succeeds with CACHE_ENABLED=true
    - Check Redis container is healthy: `docker exec futurestradinglog-redis-dev redis-cli ping`

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 12-22 tests total)
- Maximum 6 additional integration tests added when filling gaps
- Scheduler successfully starts in Docker dev environment
- Redis connectivity works using Docker service name (redis:6379)
- Scheduler schedules job at 14:05 Pacific Time (22:05 UTC)
- Zero-record instruments automatically backfill 365 days
- Logs clearly show timezone information and backfill operations
- Manual testing in Docker confirms all three root causes are fixed

## Execution Order

Recommended implementation sequence:
1. **Configuration & Dependencies (Task Group 1)** - Foundation for all other work
2. **Scheduler Refactoring (Task Group 2)** - Core timezone fix, depends on APScheduler from Group 1
3. **Auto-Backfill Logic (Task Group 3)** - Builds on scheduler fix to add backfill capability
4. **Documentation (Task Group 4)** - Can be done in parallel, no dependencies
5. **Integration Testing (Task Group 5)** - Final verification after all fixes complete

## Notes

**Testing Philosophy:**
- Each task group writes 2-6 focused tests maximum during development
- Tests cover only critical behaviors, not exhaustive coverage
- Each task group runs ONLY its own tests, not the entire suite
- Final integration testing adds maximum 6 tests to fill critical gaps
- Total expected tests: 12-22 tests for this entire feature

**Key Technical Decisions:**
- APScheduler's BackgroundScheduler handles threading internally (no manual thread management)
- CronTrigger with explicit timezone ensures Pacific Time scheduling regardless of container TZ
- Zero-record detection happens per instrument/timeframe in _sync_instrument method
- 365-day backfill respects Yahoo Finance historical limits (7d/60d/365d by timeframe)
- Existing rate limiting, circuit breaker, and caching logic applies to backfill

**Critical Files:**
- `services/daily_import_scheduler.py` - Main scheduler changes (~150 lines modified)
- `services/data_service.py` - Backfill logic in _sync_instrument method (~30 lines added)
- `.env` - Two critical line changes (REDIS_URL and CACHE_ENABLED)
- `requirements.txt` - One dependency addition (APScheduler)
- `docker-compose.*.yml` - Documentation comments only

**Validation Points:**
- Configuration validation at startup prevents silent failures
- Timezone logging (UTC + Pacific) makes debugging easier
- Backfill logging clearly differentiates from normal sync
- Docker Compose comments help users understand networking

**Success Metrics:**
- Daily import runs at 2:05 PM Pacific Time (not 6:05 AM Pacific)
- Flask successfully connects to Redis in Docker environment
- Zero OHLC records trigger automatic 365-day backfill
- All approximately 12-22 feature tests pass
