# NinjaTrader Export Setup Guide

## Table of Contents
- [Overview](#overview)
- [Session Date Logic](#session-date-logic)
- [Timezone Conversion](#timezone-conversion)
- [Configuration Instructions](#configuration-instructions)
- [Parameter Reference](#parameter-reference)
- [Daily Import Strategy](#daily-import-strategy)
- [Testing Procedures](#testing-procedures)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Log File Analysis](#log-file-analysis)

## Overview

The ExecutionExporter indicator automatically exports trade executions from NinjaTrader to CSV files compatible with the FuturesTradingLog application. The key feature is **session-based date logic** that ensures executions are exported with the correct trading session closing date rather than the current date.

### Why Session Date Logic Matters

Futures markets trade in 23-hour sessions:
- **Sunday:** 3pm PT (open) to Monday 2pm PT (close)
- **Monday:** 3pm PT (open) to Tuesday 2pm PT (close)
- **Tuesday:** 3pm PT (open) to Wednesday 2pm PT (close)
- **Wednesday:** 3pm PT (open) to Thursday 2pm PT (close)
- **Thursday:** 3pm PT (open) to Friday 2pm PT (close)

Without session date logic, a trade executed Sunday at 4pm PT would export as "Sunday.csv" when it should be "Monday.csv" (because the session closes on Monday). This causes import failures in FuturesTradingLog.

## Session Date Logic

### How It Works

The indicator uses **Pacific Time** (America/Los_Angeles) as the reference timezone and applies this logic:

```
IF current_time_PT >= 3pm (15:00)
    THEN use NEXT day's date
ELSE
    use CURRENT day's date
```

### Examples

| Server Time | Pacific Time | Session Close Date | Export Filename |
|-------------|--------------|-------------------|-----------------|
| Sun 4pm PT | Sun 4pm PT | Monday | NinjaTrader_Executions_20251111.csv |
| Sun 7pm ET | Sun 4pm PT | Monday | NinjaTrader_Executions_20251111.csv |
| Mon 1pm PT | Mon 1pm PT | Monday | NinjaTrader_Executions_20251111.csv |
| Mon 4pm PT | Mon 4pm PT | Tuesday | NinjaTrader_Executions_20251112.csv |
| Tue 2am CT | Mon 12am PT | Monday | NinjaTrader_Executions_20251111.csv |

### Weekend Handling

The logic continues to work during weekends, though markets are closed:
- **Friday 3pm+ PT:** Exports would use Saturday (market closed)
- **Saturday any time:** Exports would use Sunday (market closed)
- **Sunday before 3pm PT:** Exports would use Sunday (market opening soon)
- **Sunday 3pm+ PT:** Exports would use Monday (market open)

## Timezone Conversion

### Why Pacific Time?

Futures markets use Pacific Time for session start/end times. The indicator must convert server time to Pacific Time before calculating the session date to ensure consistency regardless of where NinjaTrader is running.

### Supported Server Timezones

The indicator automatically converts from any timezone to Pacific Time:
- **Eastern Time (ET):** 3pm PT = 6pm ET
- **Central Time (CT):** 3pm PT = 5pm CT
- **Mountain Time (MT):** 3pm PT = 4pm PT
- **UTC/GMT:** 3pm PT = 11pm UTC (or 10pm during DST)
- **Any other timezone:** Automatic conversion

### Daylight Saving Time

The indicator uses `TimeZoneInfo` which automatically handles DST transitions:
- **Pacific Standard Time (PST):** Winter (UTC-8)
- **Pacific Daylight Time (PDT):** Summer (UTC-7)

No manual adjustment needed during DST transitions.

### Fallback Behavior

If Pacific timezone conversion fails (missing timezone data on server):
1. Logs error message to execution_export.log
2. Falls back to server time for date calculation
3. Uses server time with same 3pm logic (best effort)
4. Alert user to check timezone configuration

## Configuration Instructions

### Step 1: Install the Indicator

1. Copy `ExecutionExporter.cs` to NinjaTrader's indicator folder:
   - Default location: `C:\Users\[Username]\Documents\NinjaTrader 8\bin\Custom\Indicators\`
2. In NinjaTrader, go to **Tools > Edit NinjaScript > Indicator**
3. Compile the script (F5 or click Compile)
4. Restart NinjaTrader if needed

### Step 2: Add Indicator to Chart

1. Open any chart in NinjaTrader
2. Right-click chart > **Indicators**
3. Search for "ExecutionExporter"
4. Click **Add**
5. Configure parameters (see below)
6. Click **OK**

### Step 3: Configure Export Path

**Recommended Setup:**
- Export Path: `C:\Program Files\FuturesTradingLog\data\`
- This should match your FuturesTradingLog installation directory

**Alternative Setup:**
- Export Path: `C:\Users\[Username]\Documents\FuturesTradingLog\data\`
- Cross-platform compatible location

**Important:** The directory will be created automatically if it doesn't exist.

### Step 4: Configure Session Settings

**Recommended Settings:**
- **Use Session Close Date:** `true` (ENABLED)
- **Session Start Hour (PT):** `15` (3pm Pacific Time)
- **Create Daily Files:** `true` (ENABLED)
- **Enable Logging:** `true` (for initial setup and troubleshooting)

### Step 5: Verify Configuration

1. Execute a test trade (sim account recommended)
2. Check export directory for CSV file
3. Verify filename uses correct session date
4. Review log file for timezone conversion messages

## Parameter Reference

### Export Path
- **Type:** String (directory path)
- **Default:** `[Documents]\FuturesTradingLog\data\`
- **Description:** Directory where CSV files will be exported
- **Validation:** Directory is created automatically if missing
- **Notes:** Must be writable by NinjaTrader process

### Create Daily Files
- **Type:** Boolean (true/false)
- **Default:** `true`
- **Description:** Create one CSV file per trading session
- **Recommended:** `true` for FuturesTradingLog integration
- **When false:** Files rotate based on size limit with timestamp naming

### Max File Size (MB)
- **Type:** Integer
- **Default:** `10`
- **Range:** 1-100 MB
- **Description:** Maximum file size before rotation (only when Create Daily Files = false)
- **Notes:** Daily files can exceed this limit without rotation

### Enable Logging
- **Type:** Boolean (true/false)
- **Default:** `true`
- **Description:** Enable detailed logging to execution_export.log
- **Recommended:** `true` for setup and troubleshooting, can disable in production
- **Log Location:** `[ExportPath]\logs\execution_export.log`

### Use Session Close Date
- **Type:** Boolean (true/false)
- **Default:** `true`
- **Description:** Enable session close date logic for file naming
- **Recommended:** `true` for correct session alignment
- **When false:** Uses legacy current date logic (backward compatibility)

**Examples:**
- `true` (recommended): Sunday 4pm PT exports to Monday file
- `false` (legacy): Sunday 4pm PT exports to Sunday file

### Session Start Hour (PT)
- **Type:** Integer
- **Default:** `15` (3pm)
- **Range:** 0-23 (24-hour format)
- **Description:** Hour when new trading session begins in Pacific Time
- **Customization:** Can adjust for different market schedules

**How it works:**
- If current PT hour >= this value: Use next day's date
- If current PT hour < this value: Use current day's date

## Daily Import Strategy

The FuturesTradingLog application uses a **once-daily import strategy** to simplify data management and avoid issues with open positions and continuous re-importing.

### Import Schedule

- **Automatic Import Time**: 2:05pm Pacific Time (5:05pm Eastern Time)
- **Manual Import**: Available via "Import Now" button on the dashboard
- **Market Hours**: Futures market is open 23 hours/day, 5 days/week
  - Sunday 3pm PT → Monday 2pm PT
  - Monday 3pm PT → Tuesday 2pm PT
  - Tuesday 3pm PT → Wednesday 2pm PT
  - Wednesday 3pm PT → Thursday 2pm PT
  - Thursday 3pm PT → Friday 2pm PT

### Key Requirement: Export with CLOSING Date

**CRITICAL**: NinjaTrader must be configured to export data with the **CLOSING date**, not the current or opening date.

For example:
- Trading session: Monday 3pm PT → Tuesday 2pm PT
- Export date: **Tuesday** (the closing date)
- File name: `NinjaTrader_Executions_20251112.csv` (if Tuesday is November 12, 2025)

This ensures:
1. All positions are closed by the time of import
2. No partial/open position data is imported
3. Clean position boundaries (0 → +/- → 0)
4. No position ID churn or data conflicts

### Import Process

#### Automatic Import (2:05pm PT)

The application automatically checks for and imports the current day's CSV file at 2:05pm PT if the app is running.

**Process:**
1. At 2:05pm PT, scheduler wakes up
2. Looks for file: `NinjaTrader_Executions_YYYYMMDD.csv` (today's date)
3. Validates:
   - File exists
   - File is not empty
   - Filename date matches expected date
4. Imports all executions
5. Rebuilds positions for affected accounts
6. Invalidates cache for updated data

#### Manual Import

You can trigger a manual import at any time using the "Import Now" button on the dashboard.

**When to use manual import:**
- Testing new executions
- Re-importing after data corrections
- Importing historical data
- Missed automatic import (app was not running at 2:05pm)

### File Validation

The import process validates the following before importing:

1. **Filename Date Match**
   - Filename must match target date format: `NinjaTrader_Executions_YYYYMMDD.csv`
   - Date in filename must match expected date

2. **File Not Empty**
   - File must contain data (not 0 bytes)

3. **All Positions Closed**
   - No validation yet implemented, but recommended
   - Future enhancement: Reject files with open positions

### API Endpoints

#### Get Import Status
```bash
GET /api/csv/daily-import/status
```

Returns scheduler status, next import time, and import history.

#### Manual Import
```bash
POST /api/csv/daily-import/manual
Content-Type: application/json

{
  "date": "20251112"  // Optional: specific date to import
}
```

#### Start/Stop Scheduler
```bash
POST /api/csv/daily-import/start
POST /api/csv/daily-import/stop
```

#### Import History
```bash
GET /api/csv/daily-import/history
```

Returns last 100 imports with results.

## Testing Procedures

### Test 1: Verify Session Date Calculation

**Objective:** Confirm executions export with correct session closing date

**Steps:**
1. Enable logging (`Enable Logging = true`)
2. Note current Pacific Time
3. Execute a test trade
4. Check exported CSV filename
5. Review log messages

**Expected Results:**

If current time is **Sunday 4pm PT:**
- Filename: `NinjaTrader_Executions_[Monday-date].csv`
- Log shows: "Pacific time: [Sunday date] 16:00:00"
- Log shows: "Session Close Date: [Monday date]"

If current time is **Monday 1pm PT:**
- Filename: `NinjaTrader_Executions_[Monday-date].csv`
- Log shows: "Pacific time: [Monday date] 13:00:00"
- Log shows: "Session Close Date: [Monday date]"

### Test 2: Verify Timezone Conversion

**Objective:** Confirm server time converts correctly to Pacific Time

**Steps:**
1. Identify your server's timezone (check Windows date/time settings)
2. Enable logging
3. Execute test trade
4. Review log file for timezone conversion messages

**Expected Log Output:**
```
2025-11-12 18:00:00 - INFO - Server time: 2025-11-12 18:00:00 (Eastern Standard Time)
2025-11-12 18:00:00 - INFO - Pacific time: 2025-11-12 15:00:00
2025-11-12 18:00:00 - INFO - Session date calculation - Pacific Time: 2025-11-12 15:00:00, Session Close Date: 2025-11-13
```

**Verify:**
- Server time matches your system clock
- Pacific time is correctly offset from server time
- Session close date follows the >= 3pm rule

### Test 3: Verify File Naming Across Session Boundary

**Objective:** Confirm file changes at session boundary (3pm PT)

**Steps:**
1. Wait until approximately 2:55pm Pacific Time
2. Execute test trade (should export to today's file)
3. Wait until 3:05pm Pacific Time
4. Execute another test trade (should export to tomorrow's file)
5. Check export directory for two different files

**Expected Results:**
- Before 3pm PT: File dated with current day
- After 3pm PT: File dated with next day
- Both files exist in export directory

### Test 4: Test Backward Compatibility Mode

**Objective:** Verify legacy date logic still works

**Steps:**
1. Set `Use Session Close Date = false`
2. Restart indicator
3. Execute test trade
4. Check filename uses current date (not session date)

**Expected Results:**
- Filename uses current date regardless of time
- Log shows: "Using legacy date logic (UseSessionCloseDate=false)"

### Test 5: Verify Integration with FuturesTradingLog

**Objective:** Confirm exported files import successfully

**Steps:**
1. Ensure `Use Session Close Date = true`
2. Execute several test trades throughout the day
3. Run FuturesTradingLog daily import scheduler
4. Verify import finds correct file
5. Check for date mismatch validation errors (should be none)

**Expected Results:**
- Import finds CSV file with expected session date
- No "date mismatch" errors in import log
- Positions created correctly in FuturesTradingLog

## Troubleshooting Guide

### Issue: Wrong Timezone on Server

**Symptoms:**
- Exported files use incorrect dates
- Log shows timezone conversion errors
- "Pacific timezone not initialized" error

**Diagnosis:**
1. Check log file: `[ExportPath]\logs\execution_export.log`
2. Look for message: "Failed to initialize Pacific timezone"
3. Check Windows timezone database

**Solution:**
```
Option 1: Update Windows Timezone Database
1. Open Windows Settings > Time & Language > Date & Time
2. Ensure timezone data is up to date
3. Restart NinjaTrader

Option 2: Use Server Time Fallback
1. Verify server is set to Pacific Time
2. Leave Use Session Close Date = true
3. Indicator will use server time as fallback
4. Note: Only works if server is actually in Pacific timezone
```

### Issue: Executions Exporting to Wrong Date File

**Symptoms:**
- Sunday trades export to Sunday file (should be Monday)
- Session boundary at wrong time

**Diagnosis:**
1. Check log: "Session date calculation - Pacific Time: [timestamp]"
2. Verify Pacific Time conversion is working
3. Check Session Start Hour (PT) parameter

**Solution:**
```
Step 1: Verify Session Start Hour
- Should be 15 (for 3pm PT)
- If different, adjust parameter

Step 2: Verify Use Session Close Date Enabled
- Set to true
- Restart indicator

Step 3: Check Timezone Conversion
- Review log for "Server time" and "Pacific time" messages
- Ensure conversion is working correctly
- Offset should match timezone difference
```

### Issue: File Permission Errors

**Symptoms:**
- Log shows: "File write failed (SecurityException)"
- Log shows: "Permission denied for path"
- Executions not saving

**Diagnosis:**
1. Check log for specific error message
2. Verify export path exists
3. Check folder permissions

**Solution:**
```
Step 1: Check Folder Permissions
1. Navigate to export directory
2. Right-click > Properties > Security
3. Ensure user account has "Write" permission

Step 2: Run NinjaTrader as Administrator (temporary test)
1. Right-click NinjaTrader shortcut
2. Select "Run as administrator"
3. If this fixes it, permissions are the issue

Step 3: Move Export Directory
1. Change Export Path to user's Documents folder
2. Example: C:\Users\[Username]\Documents\FuturesTradingLog\data\
3. This location typically has full user permissions
```

### Issue: Multiple Files for Same Session

**Symptoms:**
- Several files with same date
- Files have timestamps in name

**Diagnosis:**
- Check `Create Daily Files` parameter

**Solution:**
```
Set Create Daily Files = true
- This ensures one file per session
- Files append rather than rotate
- Matches FuturesTradingLog import expectations
```

### Issue: Import Failed - "CSV file not found"

**Cause**: The expected CSV file does not exist in the data directory.

**Solution**:
1. Check NinjaTrader export path matches: `C:\Program Files\FuturesTradingLog\data\`
2. Verify export indicator is running
3. Confirm session date logic is enabled (`Use Session Close Date = true`)
4. Check file naming pattern: `NinjaTrader_Executions_YYYYMMDD.csv`

### Issue: Import Failed - "Filename date mismatch"

**Cause**: The date in the filename does not match the expected date.

**Solution**:
1. Verify NinjaTrader is using **session close date** logic (`Use Session Close Date = true`)
2. Check system clock is correct
3. Review log to verify Pacific Time conversion is working
4. Manually specify date when importing via API if needed

### Issue: Import Failed - "File is empty"

**Cause**: The CSV file exists but contains no data.

**Solution**:
1. Check if there were any trades during the session
2. Verify ExecutionExporter indicator is capturing all executions
3. Check indicator settings for any filters that might exclude trades

### Issue: Positions Look Wrong After Import

**Cause**: Possible causes include:
- Wrong date in filename (using opening date instead of closing date)
- Open positions were imported (session not yet closed)
- Multiple imports of the same file

**Solution**:
1. Verify NinjaTrader export uses closing date (`Use Session Close Date = true`)
2. Only import after market close (2pm PT)
3. Check import history via API: `/api/csv/daily-import/history`
4. Consider rebuilding all positions: See position boundary detection documentation

### Issue: DST Transition Date Issues

**Symptoms:**
- Wrong dates during spring forward or fall back weekend
- Session boundary off by 1 hour during DST transition

**Diagnosis:**
1. Check if issue occurs during DST transition weekend
2. Review log for Pacific Time values
3. Verify Windows has correct DST rules

**Solution:**
```
This should be handled automatically, but if issues occur:

Step 1: Verify Windows DST Settings
1. Windows Settings > Time & Language > Date & Time
2. Ensure "Set time zone automatically" is enabled
3. Check "Adjust for daylight saving time automatically"

Step 2: Update Windows
- DST rule changes require Windows updates
- Install latest Windows updates

Step 3: Restart After DST Transition
- Restart NinjaTrader after DST transition occurs
- Reloads timezone data with correct DST offset
```

## Log File Analysis

### Log File Location

```
[Export Path]\logs\execution_export.log
```

Example: `C:\Program Files\FuturesTradingLog\data\logs\execution_export.log`

### Log Message Types

**INFO Messages:** Normal operation
- Timezone initialization
- Session date calculation
- File creation/rotation
- Execution exports

**ERROR Messages:** Issues requiring attention
- Timezone conversion failures
- File write errors
- Date validation warnings
- Permission errors

### Sample Log Output (Successful Operation)

```
2025-11-12 16:00:00 - INFO - Pacific timezone initialized successfully
2025-11-12 16:00:00 - INFO - Created export directory: C:\Program Files\FuturesTradingLog\data\
2025-11-12 16:00:00 - INFO - Created new export file: NinjaTrader_Executions_20251113.csv
2025-11-12 16:05:30 - INFO - Server time: 2025-11-12 16:05:30 (Pacific Standard Time)
2025-11-12 16:05:30 - INFO - Pacific time: 2025-11-12 16:05:30
2025-11-12 16:05:30 - INFO - Session date calculation - Pacific Time: 2025-11-12 16:05:30, Session Close Date: 2025-11-13
2025-11-12 16:05:30 - INFO - Export filename: NinjaTrader_Executions_20251113.csv
2025-11-12 16:05:30 - INFO - Exported execution: [Sim101] MES 12-24 Entry 1@5995.25 - Position: 1
```

**Analysis:**
- Timezone initialized successfully
- Server time is Pacific (no conversion needed)
- Current time 4:05pm PT (hour 16)
- Since 16 >= 15, uses next day (Nov 13)
- Export filename correct: 20251113

### Sample Log Output (Timezone Conversion)

```
2025-11-12 19:00:00 - INFO - Pacific timezone initialized successfully
2025-11-12 19:00:00 - INFO - Server time: 2025-11-12 19:00:00 (Eastern Standard Time)
2025-11-12 19:00:00 - INFO - Pacific time: 2025-11-12 16:00:00
2025-11-12 19:00:00 - INFO - Session date calculation - Pacific Time: 2025-11-12 16:00:00, Session Close Date: 2025-11-13
```

**Analysis:**
- Server in Eastern Time (3 hours ahead)
- 7pm ET converts to 4pm PT
- Since 16 >= 15, uses next day
- Timezone conversion working correctly

### Sample Log Output (Error - Timezone Failure)

```
2025-11-12 16:00:00 - ERROR - Failed to initialize Pacific timezone: TimeZoneNotFoundException: The time zone ID 'Pacific Standard Time' was not found. Will use server time as fallback.
2025-11-12 16:05:30 - ERROR - Pacific timezone not initialized. Using server time fallback due to timezone conversion error.
```

**Analysis:**
- Timezone database missing or corrupted
- Indicator falling back to server time
- **Action Required:** Update Windows timezone database or ensure server is in Pacific Time

### Sample Log Output (Date Validation Warning)

```
2025-11-12 16:00:00 - ERROR - Date validation warning: Calculated date 2025-11-09 is 3 days in the past (Pacific Now: 2025-11-12 16:00:00)
```

**Analysis:**
- Calculated date seems incorrect (3 days old)
- Timezone conversion may be failing
- System clock may be wrong
- **Action Required:** Check timezone configuration and system clock

## Best Practices

### For Initial Setup

1. Enable logging during setup
2. Execute test trades in sim account
3. Verify log messages show correct timezone conversion
4. Verify filenames match expected session dates
5. Test integration with FuturesTradingLog import

### For Production Use

1. Keep logging enabled initially to catch any issues
2. Monitor log file for errors during first week
3. After verification, can disable logging if desired
4. Periodically check log file for errors
5. Re-enable logging when troubleshooting

### For Different Market Schedules

If your market uses different session times:

1. Adjust `Session Start Hour (PT)` parameter
2. Example: For 4pm PT session start, set to 16
3. Test thoroughly with new setting
4. Document your custom configuration

### For Multi-Account Trading

The indicator automatically handles multiple accounts:
- Each account's executions export to same daily file
- Position tracking is account-specific
- No special configuration needed

## CSV Format

The CSV must include the following columns:
```
Instrument, Action, Quantity, Price, Time, ID, E/X, Position, Order ID, Name, Commission, Rate, Account, Connection
```

The ExecutionExporter indicator automatically generates this format.

## Configuration

### Environment Variables

- `ENABLE_CONTINUOUS_WATCHER=false`: Disables continuous file watcher (recommended)
- `DATA_DIR=C:\Program Files\FuturesTradingLog\data\`: Data directory path

### Scheduler Configuration

Located in `services/daily_import_scheduler.py`:
```python
IMPORT_TIME_PT = "14:05"  # 2:05pm Pacific Time
```

To change the import time, modify this constant and restart the application.

## Migration from Continuous Import

If you were previously using the continuous file watcher:

1. **Disable the continuous watcher** (already done)
   - Set `ENABLE_CONTINUOUS_WATCHER=false`
   - Or simply restart the app (it's disabled by default now)

2. **Update NinjaTrader export**
   - Enable `Use Session Close Date = true`
   - Use session end date in filename

3. **Test the new workflow**
   - Manual import: Use "Import Now" button
   - Verify automatic import works at 2:05pm PT

## Benefits of Daily Import Strategy

1. **Clean Position Boundaries**: All positions are closed before import
2. **No Position ID Churn**: Positions retain their IDs (no rebuilding during trading)
3. **Simplified Logic**: No need to handle open positions or partial data
4. **Predictable Imports**: One import per day at a known time
5. **Better Data Integrity**: Reduced risk of duplicate or conflicting data
6. **Correct Session Alignment**: Files use session closing date for proper organization

## Support and Further Information

For issues not covered in this guide:

1. Review full specification: `agent-os/specs/2025-11-12-ninjatrader-session-date-export/spec.md`
2. Check FuturesTradingLog import logs: `data/logs/app.log`
3. Review import history: Dashboard → Import Status Card
4. Check scheduler status: `/api/csv/daily-import/status`
5. See position boundary detection spec: `agent-os/specs/2025-11-03-position-boundary-detection/`

## Version History

- **v2.0** (2025-11-12): Added session date logic
  - Pacific Time timezone conversion
  - Session-based file naming
  - Backward compatibility mode
  - Comprehensive logging
  - Detailed parameter documentation
- **v1.0** (2025-11-03): Initial daily import strategy
  - Once-daily import at 2:05pm PT
  - Manual import capability
  - Basic file validation
