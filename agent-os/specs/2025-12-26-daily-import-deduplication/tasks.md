# Tasks: Daily Import Deduplication

> Spec: Daily Import Deduplication
> Created: 2025-12-26
> Implemented: 2025-12-26

## Overview

This tasks list addresses removing redundant automatic **trade import** processes while ensuring only the daily 2:05pm Pacific scheduled trade import runs when the market is closed. Background services for OHLC gap filling and cache maintenance should continue to run normally.

## Current State Analysis

The following automatic import processes currently exist in the application:

| Service | Decision | Location | Description |
|---------|----------|----------|-------------|
| **Daily Import Scheduler** | KEEP | `services/daily_import_scheduler.py` | Runs at 2:05pm PT daily - PRIMARY TRADE IMPORT |
| **File Watcher** | DEPRECATED | `services/file_watcher.py` | Polling-based CSV file monitoring - now disabled by default |
| **NinjaTrader Continuous Watcher** | ALREADY DISABLED | `services/ninjatrader_import_service.py` | Disabled via ENABLE_CONTINUOUS_WATCHER=false |
| **Automated Data Sync** | DEPRECATED | `scripts/automated_data_sync.py` | No longer started automatically |
| **Background Gap Filling** | KEEP | `services/background_services.py` | OHLC data gap filling and cache maintenance - NOT trade imports |
| **Background Data Manager** | KEEP | `services/background_data_manager.py` | Enhanced background data management - NOT trade imports |

---

## Task Group 1: Remove File Watcher Auto-Import

**Goal**: Disable the file watcher service that runs continuous polling for new CSV trade files.
**Status**: COMPLETED

### Tasks

- [x] **1.1** Update `app.py` to NOT start file_watcher on application startup
  - Added deprecation warning when file watcher is enabled
  - File watcher only starts if AUTO_IMPORT_ENABLED=true (not recommended)

- [x] **1.2** Set `AUTO_IMPORT_ENABLED=false` as the default configuration
  - Updated `.env.development` to set AUTO_IMPORT_ENABLED=false
  - Added deprecation comment explaining the change

- [x] **1.3** Update health check endpoints to not require file watcher to be running
  - Updated both `/health` and `/health/detailed` endpoints
  - File watcher now marked as deprecated in health status

---

## Task Group 2: Clean Up Automated Data Sync Startup

**Goal**: The AutomatedDataSyncer is already deprecated but still starts at app startup. Remove this startup call since OHLC sync is now triggered after daily imports.
**Status**: COMPLETED

### Tasks

- [x] **2.1** Remove `start_automated_data_sync()` call from `app.py`
  - Replaced with log message explaining OHLC sync is now handled by Daily Import Scheduler

- [x] **2.2** Remove `stop_automated_data_sync` from atexit handlers
  - Removed from cleanup handlers

- [x] **2.3** Update health endpoints to reflect AutomatedDataSyncer is not running
  - Both `/health` and `/health/detailed` now show deprecated status with explanation

---

## Task Group 3: Implement Redis-Based Deduplication for Daily Import

**Goal**: Ensure the daily trade import at 2:05pm PT runs only once per trading day, even if the container restarts.
**Status**: COMPLETED

### Tasks

- [x] **3.1** Add `_should_run_scheduled_import()` method to DailyImportScheduler
  - Checks if weekend (Saturday/Sunday)
  - Checks Redis key for today's date to see if already ran
  - Returns (should_run: bool, reason: str)

- [x] **3.2** Add `_record_scheduled_import_complete()` method
  - Writes to Redis key `daily_import:last_scheduled:{YYYYMMDD}`
  - Stores timestamp, success status, executions imported, files processed
  - Sets 7-day TTL for automatic cleanup

- [x] **3.3** Integrate deduplication check into `_scheduled_import_callback()`
  - Calls `_should_run_scheduled_import()` before proceeding
  - Logs skip reason if not running
  - Calls `_record_scheduled_import_complete()` after successful import

- [x] **3.4** Add Redis client access to DailyImportScheduler
  - Added `_init_redis_client()` method
  - Handles graceful degradation if Redis unavailable

---

## Task Group 4: Manual Import Bypass

**Goal**: Allow manual trade imports to run regardless of the daily deduplication state.
**Status**: COMPLETED

### Tasks

- [x] **4.1** Ensure `manual_import()` method does NOT check deduplication
  - Verified: manual_import() does not call _should_run_scheduled_import()
  - Does NOT update the Redis scheduled import key

- [x] **4.2** Add clear logging to distinguish manual vs scheduled imports
  - Updated log message to "MANUAL IMPORT TRIGGERED (bypasses deduplication)"
  - Updated docstring to explain bypass behavior

---

## Task Group 5: Weekend Skip Logic

**Goal**: Skip scheduled trade imports on weekends when futures markets are closed.
**Status**: COMPLETED

### Tasks

- [x] **5.1** Implement weekend detection in `_should_run_scheduled_import()`
  - Checks `datetime.weekday()` for Saturday (5) and Sunday (6)
  - Returns appropriate message: "market closed (Saturday)" or "market closed (Sunday)"

---

## Task Group 6: Testing & Verification

**Goal**: Verify the deduplication and cleanup works correctly.
**Status**: PARTIAL - Code verified, manual testing recommended

### Tasks

- [x] **6.1** Syntax verification
  - `daily_import_scheduler.py` imports successfully
  - `app.py` syntax verified

- [ ] **6.2** Test container restart scenario (manual test)
  - Start container, trigger 2:05pm import
  - Restart container
  - Verify import does NOT run again for same day

- [ ] **6.3** Test weekend skip behavior (manual test)
  - Wait for Saturday/Sunday
  - Verify scheduled import is skipped with appropriate log

- [ ] **6.4** Test manual import bypass (manual test)
  - After daily import has run
  - Trigger manual import via API
  - Verify it proceeds successfully

- [ ] **6.5** Test Redis unavailable fallback (manual test)
  - Disable Redis connection
  - Verify scheduled import still runs (with warning log)

- [x] **6.6** Verify background services configuration
  - BackgroundGapFillingService still configured to run
  - BackgroundDataManager still configured to run
  - These are NOT affected by trade import changes

---

## Implementation Summary

### Files Modified

1. **`services/daily_import_scheduler.py`**
   - Added `import json` and `import redis`
   - Added `_redis_client` attribute
   - Added `_init_redis_client()` method
   - Added `_should_run_scheduled_import()` method (weekend + Redis deduplication)
   - Added `_record_scheduled_import_complete()` method
   - Updated `_scheduled_import_callback()` to use deduplication
   - Updated `manual_import()` docstring and logging

2. **`app.py`**
   - Updated file watcher startup to show deprecation warning
   - Removed `start_automated_data_sync()` call
   - Removed `stop_automated_data_sync` from atexit handlers
   - Updated `/health` endpoint to show deprecated services
   - Updated `/health/detailed` endpoint to show deprecated services

3. **`.env.development`**
   - Set `AUTO_IMPORT_ENABLED=false`
   - Added deprecation comment

---

## Services NOT Affected (Continue Running)

These services continue to operate normally:

1. **BackgroundGapFillingService** (`services/background_services.py`)
   - Fills gaps in OHLC data every 15 minutes
   - Extended gap filling every 4 hours
   - Cache maintenance daily at 2am
   - Warms popular instruments at 3am

2. **BackgroundDataManager** (`services/background_data_manager.py`)
   - Enhanced background data processing
   - Cache management for charts

3. **Legacy Background Services** (`services/background_services.py`)
   - Gap-filling
   - Cache maintenance

---

## Dependencies

- Redis must be available for reliable deduplication (graceful fallback if not)
- APScheduler already configured for 2:05pm PT in DailyImportScheduler
- Pacific timezone handling already implemented

## Out of Scope

- Market holiday calendar (future enhancement)
- Multi-timezone support
- Historical backfill of missed imports
- Changes to OHLC gap filling schedules
