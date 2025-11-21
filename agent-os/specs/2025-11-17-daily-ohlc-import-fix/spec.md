# Specification: Daily OHLC Import Fix

## Goal
Fix the daily OHLC candle import system to successfully run at 2:05 PM Pacific Time, connect to Redis properly in Docker environments, and automatically backfill 365 days of historical data when instruments have zero OHLC records.

## User Stories
- As a trader, I want the system to automatically download daily OHLC data at market close so I have up-to-date charts without manual intervention
- As a developer, I want clear logging and proper timezone handling so I can troubleshoot issues and verify the scheduler is working correctly

## Specific Requirements

**Timezone-Aware Scheduling with APScheduler**
- Replace Python `schedule` library with `APScheduler` for timezone-aware scheduling in `services/daily_import_scheduler.py`
- Configure scheduler to run at 14:05 Pacific Time (22:05 UTC) regardless of container timezone
- Use `pytz.timezone('America/Los_Angeles')` to ensure Pacific Time scheduling
- APScheduler's `CronTrigger` or `IntervalTrigger` should be used with explicit timezone parameter
- Maintain existing scheduler interface (start, stop, manual_import, get_status methods)
- Log scheduled run times in both UTC and Pacific Time for clarity

**Fix Redis Connection for Docker Networking**
- Update `.env` file to use `REDIS_URL=redis://redis:6379/0` instead of `redis://localhost:6379/0`
- Set `CACHE_ENABLED=true` in `.env` file to enable caching required for OHLC sync
- Ensure docker-compose.dev.yml already has correct defaults (redis://redis:6379/0) which will work when .env is fixed
- Verify Redis service name "redis" matches docker-compose.dev.yml service definition
- No changes needed to docker-compose.dev.yml - just fix .env file overrides

**Automatic 365-Day OHLC Backfill**
- Implement auto-backfill logic in `services/data_service.py` within `_sync_instrument` method
- Before syncing each instrument/timeframe, check if OHLC record count is zero using `FuturesDB.get_ohlc_count(instrument, timeframe)`
- If zero records detected, fetch 365 days of historical data instead of normal window
- Use `datetime.now() - timedelta(days=365)` as start_date for backfill
- Respect Yahoo Finance historical limits per timeframe (7 days for 1m, 60 days for 5m-12h, 365 days for 1d+)
- Log backfill operations clearly: "Backfilling 365 days for [instrument] [timeframe] - zero records detected"
- No manual trigger needed - automatic on first successful sync after fix

**Enhanced Logging for Troubleshooting**
- Add timezone information to all scheduler log messages (both UTC and Pacific Time)
- Log Redis connection attempts and success/failure at scheduler startup
- Log OHLC sync trigger events from daily_import_scheduler with instrument counts
- Add clear markers for backfill vs normal sync operations in data_service logs
- Log scheduled import time calculations showing next run in Pacific Time
- Include cache status (enabled/disabled, connection success) in scheduler status endpoint

**Docker Compose Documentation**
- Add explanatory comments to docker-compose.dev.yml header explaining this is for local development
- Add comments to docker-compose.yml header explaining this builds locally and lacks Redis (for users without Docker networking)
- Add comments to docker-compose.prod.yml header explaining this uses pre-built image from GHCR and includes Watchtower
- Document Redis service differences: dev has dedicated Redis container, others rely on external Redis or cache disabled
- Add comment above REDIS_URL in each file explaining Docker service name vs localhost differences
- Include troubleshooting note about .env file overriding docker-compose defaults

**Configuration Validation at Startup**
- Add validation in daily_import_scheduler startup that checks Redis connectivity before starting scheduler
- Log warning if CACHE_ENABLED=false but display helpful message about OHLC sync requiring cache
- Validate timezone configuration is using Pacific Time correctly
- Test Redis connection using ping command during scheduler initialization

**APScheduler Integration Details**
- Install APScheduler package (add to requirements.txt if not present)
- Use `BackgroundScheduler` for compatibility with Flask threading model
- Configure with timezone-aware trigger: `CronTrigger(hour=14, minute=5, timezone=pytz.timezone('America/Los_Angeles'))`
- Replace schedule.every().day.at() with APScheduler equivalent
- Update _scheduler_loop to use APScheduler's blocking or non-blocking execution
- Maintain compatibility with existing start/stop/status methods

## Visual Design
No visual assets provided.

## Existing Code to Leverage

**daily_import_scheduler.py - Scheduler Framework**
- Existing DailyImportScheduler class structure with start/stop/manual_import methods can be preserved
- _trigger_ohlc_sync method already handles instrument mapping and calls ohlc_service.sync_instruments correctly
- Import history tracking and status reporting infrastructure already in place
- Timezone awareness already partially implemented with pytz.timezone('America/Los_Angeles')
- Just needs schedule library replaced with APScheduler for proper timezone support

**data_service.py - OHLC Sync Logic**
- sync_instruments method orchestrates syncing multiple instruments across timeframes
- _sync_instrument method handles individual instrument syncing - ideal place to add zero-record check
- FuturesDB.get_ohlc_count(instrument, timeframe) method available for checking record counts
- _get_fetch_window method already calculates date ranges respecting Yahoo Finance limits
- Rate limiting and circuit breaker logic already implemented for API reliability

**config.py - Redis Configuration**
- redis_url property reads from REDIS_URL environment variable with default
- cache_enabled property reads from CACHE_ENABLED with default true
- Configuration system already in place, just needs .env file corrected
- YAHOO_FINANCE_CONFIG defines historical limits per timeframe
- HISTORICAL_LIMITS dictionary in data_service.py maps timeframes to day limits

**docker-compose.dev.yml - Redis Service**
- Redis service already defined with correct service name "redis"
- Web service depends_on redis and has correct default REDIS_URL=redis://redis:6379/0
- CACHE_ENABLED defaults to true in docker-compose
- Volume mounting and networking already configured correctly
- Just needs .env file to stop overriding with incorrect localhost values

**TradingLog_db.py - Database Methods**
- get_ohlc_count(instrument, timeframe) returns count of existing records
- insert_ohlc_batch(records) handles bulk insert for backfill efficiency
- get_latest_ohlc_timestamp(instrument, timeframe) useful for logging backfill status
- find_ohlc_gaps method available if gap detection needed beyond zero-record check
- Database connection handling and error management already robust

## Out of Scope
- Replacing the entire OHLC import system architecture beyond fixing the identified issues
- Changing Redis caching strategy or retention policy (keeping existing 14-day TTL)
- Modifying OHLC data model or database schema
- Adding new timeframes beyond existing 18 Yahoo Finance timeframes
- Creating UI for manual OHLC sync or backfill trigger
- Performance optimization beyond fixing core scheduler and connection issues
- Implementing email or push notification alerts for failed syncs
- Adding retry logic beyond existing circuit breaker and rate limiter
- Supporting multiple timezone configurations (Pacific Time only)
- Modifying NinjaTrader CSV export timing or format
