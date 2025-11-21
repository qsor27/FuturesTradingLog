# Spec Requirements: Daily OHLC Import Fix

## Initial Description
Daily OHLC candle import and data download system - Review the last two implemented specs to understand why we still aren't achieving our daily import and data download of OHLC candles, then create a spec to fix this.

## Requirements Discussion

### First Round Questions

**Q1: Which docker-compose file to fix?**
**Answer:** Fix it for dev use. Make notes or comments in all relevant docker-compose files showing the differences between each and why.

**Q2: Timezone Strategy**
**Answer:** Option C - Use timezone-aware scheduling library

**Q3: .env File Usage**
**Answer:** Option B - Fix values in .env to work with Docker networking

**Q4: Scope of Fix**
**Answer:** All of the above (implied yes to all checkboxes):
- Fix timezone configuration so daily import runs at 2:05 PM Pacific
- Fix Redis connectivity so OHLC sync works
- Initial OHLC data backfill (need to clarify how far back)
- Better logging/monitoring for troubleshooting
- Documentation on proper deployment configuration

### Root Causes Identified

Through investigation, the following root causes were identified:

**1. Timezone Mismatch**
- Container runs in UTC
- Scheduler interprets "14:05" as 14:05 UTC (6:05 AM Pacific) instead of 14:05 Pacific (22:05 UTC)
- The Python `schedule` library doesn't support timezone-aware scheduling natively
- **Impact:** Daily import runs at wrong time (6:05 AM Pacific instead of 2:05 PM Pacific)

**2. Redis Connection String**
- Running container has `REDIS_URL=redis://localhost:6379/0`
- Should be `REDIS_URL=redis://redis:6379/0` (using Docker service name)
- Redis container is running and healthy
- Flask can't connect due to incorrect hostname
- **Impact:** OHLC sync operations fail completely

**3. .env Overrides**
- The .env file has `REDIS_URL=redis://localhost:6379/0` and `CACHE_ENABLED=false`
- These values override the correct defaults in docker-compose.dev.yml
- **Impact:** Prevents Docker networking from working correctly

### Current State

**What's Working:**
- CSV files ARE in correct location: C:\Projects\FuturesTradingLog\data\
- Volume mounting is working correctly
- docker-compose.dev.yml is currently being used (based on container names)
- Redis container exists and is healthy: futurestradinglog-redis-dev
- Both containers on same Docker network

**What's Not Working:**
- Zero OHLC data in database (all timeframes show 0 records)
- Last sync attempt on 2025-11-14 failed (all timeframes returned False)
- Scheduler running at wrong time due to timezone issues
- Redis connectivity failing due to incorrect connection string

### Existing Code to Reference

**Similar Features Identified:**
- N/A - User did not provide specific similar features to reference

### Follow-up Questions

**Follow-up 1:** How far back should OHLC data backfill go? (90 days? 1 year? All time?)
**Answer:** PENDING - Not yet answered

**Follow-up 2:** Should the backfill happen automatically on first successful sync, or require manual trigger?
**Answer:** PENDING - Not yet answered

## Visual Assets

### Files Provided:
No visual assets provided.

### Visual Insights:
N/A - No visual files found in the visuals folder.

## Requirements Summary

### Functional Requirements

**Primary Objective:**
Fix the daily OHLC import system so it:
1. Runs at the correct time (2:05 PM Pacific)
2. Successfully connects to Redis for caching
3. Downloads and stores OHLC data for all required timeframes
4. Provides visibility into what's working and what's not

**Core Functionality:**
- Timezone-aware scheduling that respects Pacific Time regardless of container timezone
- Redis connectivity using proper Docker service names
- Initial backfill of historical OHLC data (timeframe TBD)
- Enhanced logging for monitoring and troubleshooting
- Proper configuration management between dev, staging, and production environments

**Data Requirements:**
- OHLC data for multiple timeframes (1min, 5min, 15min, 30min, 1hour, 4hour, daily)
- Historical data backfill (range to be determined)
- Real-time daily updates at 2:05 PM Pacific

### Technical Considerations

**Files to be Modified:**
1. `docker-compose.dev.yml` - Primary target for dev environment fixes
2. `docker-compose.yml` - Add comments explaining differences
3. `docker-compose.prod.yml` - Add comments explaining differences
4. `.env` - Fix REDIS_URL to use `redis://redis:6379/0` and set `CACHE_ENABLED=true`
5. `services/daily_import_scheduler.py` - Implement timezone-aware scheduling
6. Documentation on deployment configuration (new file or update existing)

**Technology Stack Alignment:**
- Use existing Flask 3.0.0 framework
- Leverage Redis 5.0.1 for caching (already in tech stack)
- Work with existing SQLite database with WAL mode
- Integrate with existing Celery 5.3.4 background job system if needed
- Use yfinance 0.2.28 for market data (already in tech stack)

**Integration Points:**
- Existing OHLC sync functionality (needs fixing, not replacement)
- Redis caching layer (14-day retention as per tech stack)
- Docker containerization with existing infrastructure
- Background processing system

**Configuration Management:**
- Environment-specific .env files
- Docker Compose override patterns for dev/prod
- Clear documentation on which settings belong where
- Comments in docker-compose files explaining environment differences

### Scope Boundaries

**In Scope:**
- Fix timezone configuration for Pacific Time scheduling
- Fix Redis connectivity using Docker service names
- Update .env file with correct Docker networking values
- Add timezone-aware scheduling library or implementation
- Initial OHLC data backfill (pending timeframe decision)
- Enhanced logging for monitoring and troubleshooting
- Documentation on proper deployment configuration
- Comments in all docker-compose files explaining differences

**Out of Scope:**
- Replacing the entire OHLC import system architecture
- Changing the Redis caching strategy or retention policy
- Modifying the data model for OHLC storage
- Adding new timeframes beyond existing ones
- Creating a UI for manual OHLC sync (unless user requests later)
- Performance optimization beyond fixing the core issues

**Future Enhancements Mentioned:**
- None explicitly mentioned, but potential considerations:
  - Manual trigger UI for OHLC backfill
  - More sophisticated retry logic for failed downloads
  - Alerting system for failed syncs

### Reusability Opportunities

**Components to Reference:**
- Existing OHLC sync service implementation
- Current Redis caching patterns used in the application
- Existing Docker Compose configuration patterns
- Current logging and monitoring infrastructure
- Background job scheduling patterns (Celery integration)

**Patterns to Follow:**
- Existing Docker networking setup
- Current environment variable management approach
- Redis caching TTL patterns (15-50ms chart load times benchmark)
- Background processing architecture with Celery

### Open Questions

1. **OHLC Backfill Timeframe:** How far back should the initial backfill go?
   - Options: 90 days, 1 year, all time since first trade
   - Consideration: Yahoo Finance API rate limits and reliability

2. **Backfill Trigger:** Should backfill happen automatically or manually?
   - Automatic: On first successful sync after fix
   - Manual: Require explicit trigger (safer, more control)
   - Hybrid: Automatic with configurable flag to disable

## Next Steps

1. User needs to answer the two follow-up questions above
2. Spec writer should create detailed technical specification
3. Implementation should focus on docker-compose.dev.yml as primary target
4. Testing should verify:
   - Scheduler runs at 2:05 PM Pacific Time
   - Redis connectivity works from Flask container
   - OHLC data is successfully downloaded and stored
   - Backfill completes for the agreed-upon timeframe
   - Logging provides clear visibility into the process
