# Final Requirements - User Answers

## OHLC Data Backfill Configuration

### Question 1: How far back should OHLC backfill go?
**Answer: Option B - Last 365 days (1 year)**

When the system successfully syncs for the first time and detects zero OHLC data, it should download historical data for the last 365 days for all instruments that have trades.

### Question 2: Backfill Trigger - Automatic or Manual?
**Answer: Option A - Automatically on first successful sync after fix**

The system should detect when an instrument has 0 OHLC records and automatically trigger a backfill for the last 365 days. No manual intervention required.

---

## Complete Requirements Summary

### Scope of Work
1. ✅ Fix timezone configuration so daily import runs at 2:05 PM Pacific
   - Use timezone-aware scheduling library (APScheduler or similar)
   - Container may run in UTC, but scheduler should handle Pacific Time correctly

2. ✅ Fix Redis connectivity so OHLC sync works
   - Update .env file: `REDIS_URL=redis://redis:6379/0`
   - Update .env file: `CACHE_ENABLED=true`
   - Ensure docker-compose.dev.yml has correct Redis service configuration

3. ✅ Initial OHLC data backfill
   - Automatically backfill last 365 days on first successful sync
   - Trigger when instrument has 0 OHLC records
   - All 18 Yahoo Finance timeframes

4. ✅ Better logging/monitoring for troubleshooting
   - Log scheduled import attempts (success/failure)
   - Log OHLC sync status per instrument/timeframe
   - Make debugging easier for future issues

5. ✅ Documentation on proper deployment configuration
   - Add comments to all docker-compose files explaining differences
   - Document dev vs prod configuration
   - Clear setup instructions

### Files to Modify
- `docker-compose.dev.yml` (primary target for fixes)
- `docker-compose.yml` (add explanatory comments)
- `docker-compose.prod.yml` (add explanatory comments)
- `.env` (fix REDIS_URL and CACHE_ENABLED)
- `services/daily_import_scheduler.py` (timezone-aware scheduling)
- `services/data_service.py` or `services/automated_data_sync.py` (auto-backfill logic)

### Root Causes Being Fixed
1. **Timezone Mismatch**: Scheduler runs at 14:05 UTC (6:05 AM Pacific) instead of 14:05 Pacific (22:05 UTC)
2. **Redis Connection**: Wrong hostname `localhost:6379` instead of `redis:6379`
3. **Configuration Overrides**: .env file has incorrect values that break Docker networking
