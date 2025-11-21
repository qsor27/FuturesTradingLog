# Manual Test Plan: NinjaTrader Simulator Testing

## Overview
This document provides step-by-step procedures for manually testing the ExecutionExporter indicator in NinjaTrader 8 simulator environment.

**Test Objective:** Verify that the ExecutionExporter indicator correctly exports executions with session closing dates based on Pacific Time timezone conversion.

**Prerequisites:**
- NinjaTrader 8 installed and configured
- ExecutionExporter.cs compiled and installed as an indicator
- Simulator account configured and active
- Access to NinjaTrader Output window for log messages

---

## Test Setup

### 1. Install Indicator
1. Copy `ExecutionExporter.cs` to NinjaTrader scripts folder:
   - Typical location: `Documents\NinjaTrader 8\bin\Custom\Indicators\`
2. Open NinjaTrader 8
3. Open NinjaScript Editor (Tools > Edit NinjaScript > Indicator)
4. Compile the indicator (F5 or Compile button)
5. Verify no compilation errors

### 2. Configure Indicator
1. Open a chart (any instrument, e.g., ES 12-25)
2. Add ExecutionExporter indicator to chart:
   - Right-click chart > Indicators > ExecutionExporter
3. Configure parameters:
   - **Export Path:** `C:\Projects\FuturesTradingLog\data\`
   - **Create Daily Files:** `true`
   - **Enable Logging:** `true`
   - **Use Session Close Date:** `true`
   - **Session Start Hour (PT):** `15` (3pm Pacific)
4. Apply and close

### 3. Monitor Logs
- Open NinjaTrader Output window: New > Output
- Watch for ExecutionExporter initialization messages
- Expected log: "Session date mode: ENABLED - Using session close date logic"

---

## Test Case 1: Sunday Evening Session (After 3pm PT)

**Test Objective:** Verify Sunday 4pm PT execution exports to Monday file

**Test Date:** Any Sunday after 3pm PT / 6pm ET

**Steps:**
1. Set system clock to Sunday 4:00 PM Pacific Time (or 7:00 PM Eastern Time)
   - Alternatively, run test during actual Sunday evening session
2. Open simulator account
3. Place and execute a test trade (e.g., Buy 1 ES contract)
4. Check NinjaTrader Output window for log messages:
   - Look for: "Pacific time: [Sunday date] 16:00:00"
   - Look for: "Session Close Date: [Monday date]"
   - Look for: "Export filename: NinjaTrader_Executions_[Monday YYYYMMDD].csv"
5. Navigate to export directory: `C:\Projects\FuturesTradingLog\data\`
6. Verify file exists with Monday's date in filename

**Expected Results:**
- File created: `NinjaTrader_Executions_[Monday].csv`
- File contains execution from Sunday evening
- Log shows correct timezone conversion: Sunday 4pm PT
- Log shows correct session close date: Monday

---

## Test Case 2: Monday Morning Session (Before 3pm PT)

**Test Objective:** Verify Monday 1pm PT execution uses Monday file (same session as Sunday)

**Test Date:** Any Monday before 3pm PT / 6pm ET

**Steps:**
1. Set system clock to Monday 1:00 PM Pacific Time (or 4:00 PM Eastern Time)
2. Open simulator account
3. Place and execute a test trade
4. Check NinjaTrader Output window for log messages:
   - Look for: "Pacific time: [Monday date] 13:00:00"
   - Look for: "Session Close Date: [Monday date]"
   - Look for: "Export filename: NinjaTrader_Executions_[Monday YYYYMMDD].csv"
5. Verify export file uses Monday's date (same as Sunday session)

**Expected Results:**
- File used: `NinjaTrader_Executions_[Monday].csv` (same file as Sunday session)
- Execution appended to existing Monday file
- Log shows correct session close date: Monday

---

## Test Case 3: Monday Afternoon Session (After 3pm PT)

**Test Objective:** Verify Monday 4pm PT execution creates Tuesday file (new session)

**Test Date:** Any Monday after 3pm PT / 6pm ET

**Steps:**
1. Set system clock to Monday 4:00 PM Pacific Time (or 7:00 PM Eastern Time)
2. Open simulator account
3. Place and execute a test trade
4. Check NinjaTrader Output window for log messages:
   - Look for: "Pacific time: [Monday date] 16:00:00"
   - Look for: "Session Close Date: [Tuesday date]"
   - Look for: "Export filename: NinjaTrader_Executions_[Tuesday YYYYMMDD].csv"
5. Verify new file created with Tuesday's date

**Expected Results:**
- New file created: `NinjaTrader_Executions_[Tuesday].csv`
- File is separate from Monday file
- Log shows correct session close date: Tuesday

---

## Test Case 4: Friday Afternoon Session (After 2pm PT)

**Test Objective:** Verify Friday 2:30pm PT execution uses Friday file

**Test Date:** Any Friday between 2pm-3pm PT

**Steps:**
1. Set system clock to Friday 2:30 PM Pacific Time
2. Open simulator account
3. Place and execute a test trade
4. Check logs for session close date: Friday

**Expected Results:**
- File used: `NinjaTrader_Executions_[Friday].csv`
- Session closes Friday 2pm PT, but before 3pm cutoff uses Friday date

---

## Test Case 5: Friday Evening (After 3pm PT - Market Closed)

**Test Objective:** Verify Friday 3:30pm PT execution uses Saturday file (non-trading)

**Test Date:** Any Friday after 3pm PT

**Steps:**
1. Set system clock to Friday 3:30 PM Pacific Time
2. If market is closed, note that this tests the logic but no actual trading
3. Verify logic in logs shows Saturday session close date

**Expected Results:**
- Expected file: `NinjaTrader_Executions_[Saturday].csv`
- Note: Actual file may not be created if market is closed

---

## Edge Case Testing

### Test Case 6: DST Spring Forward (March 2025)

**Test Date:** Sunday, March 9, 2025 after 3am PDT (DST transition)

**Steps:**
1. Set system clock to March 9, 2025 at 4:00 PM PDT
2. Execute test trade
3. Verify session close date: Monday, March 10, 2025
4. Verify filename: `NinjaTrader_Executions_20250310.csv`

**Expected Results:**
- Correct date despite DST transition
- Timezone conversion handles PDT correctly

### Test Case 7: DST Fall Back (November 2025)

**Test Date:** Sunday, November 2, 2025 after 2am PST (DST transition)

**Steps:**
1. Set system clock to November 2, 2025 at 4:00 PM PST
2. Execute test trade
3. Verify session close date: Monday, November 3, 2025
4. Verify filename: `NinjaTrader_Executions_20251103.csv`

**Expected Results:**
- Correct date despite DST transition
- Timezone conversion handles PST correctly

### Test Case 8: Leap Year (February 29)

**Test Date:** Thursday, February 29, 2024 (next leap year)

**Steps:**
1. Set system clock to February 29, 2024 at 4:00 PM PT
2. Execute test trade
3. Verify session close date: Friday, March 1, 2024
4. Verify filename: `NinjaTrader_Executions_20240301.csv`

**Expected Results:**
- Correctly calculates next day from leap year date
- No date calculation errors

### Test Case 9: New Year's Eve / New Year's Day

**Test Date:** Tuesday, December 31, 2024 at 4:00 PM PT

**Steps:**
1. Execute test trade on New Year's Eve evening
2. Verify session close date: Wednesday, January 1, 2025
3. Verify filename: `NinjaTrader_Executions_20250101.csv`

**Expected Results:**
- Correctly transitions to new year
- No date rollover errors

### Test Case 10: NinjaTrader Restart During Active Session

**Test Date:** Any active trading session

**Steps:**
1. Execute trades and verify file creation
2. Close NinjaTrader completely
3. Reopen NinjaTrader and indicator
4. Execute more trades in same session
5. Verify trades append to existing session file

**Expected Results:**
- Indicator reopens existing file for current session
- No duplicate file creation
- Executions append correctly

---

## Timezone Variation Testing

### Test Case 11: Eastern Time Server

**Test Objective:** Verify Pacific conversion when server is in Eastern timezone

**Steps:**
1. Set Windows timezone to Eastern Time
2. Restart NinjaTrader
3. Execute trade at 6:05 PM ET (should be 3:05 PM PT)
4. Verify logs show:
   - Server time: 18:05:00 (Eastern)
   - Pacific time: 15:05:00 (Pacific)
   - Session close date: Next day

**Expected Results:**
- Correct timezone conversion from Eastern to Pacific
- Log shows both server time and Pacific time
- Session date calculation uses Pacific time

### Test Case 12: Central Time Server

**Test Objective:** Verify Pacific conversion when server is in Central timezone

**Steps:**
1. Set Windows timezone to Central Time
2. Restart NinjaTrader
3. Execute trade at 5:05 PM CT (should be 3:05 PM PT)
4. Verify correct timezone conversion

**Expected Results:**
- Correct timezone conversion from Central to Pacific
- Session date calculation uses Pacific time

---

## Configuration Testing

### Test Case 13: UseSessionCloseDate Disabled

**Test Objective:** Verify legacy mode when UseSessionCloseDate = false

**Steps:**
1. Configure indicator: Set **Use Session Close Date** to `false`
2. Execute trade on Sunday at 4:00 PM PT
3. Verify file uses current date (Sunday) instead of session close date (Monday)

**Expected Results:**
- Legacy mode: File uses current date
- Filename: `NinjaTrader_Executions_[Sunday].csv`
- Log shows: "Using legacy date logic (UseSessionCloseDate=false)"

### Test Case 14: Custom Session Start Hour

**Test Objective:** Verify configurable session start hour

**Steps:**
1. Configure indicator: Set **Session Start Hour (PT)** to `16` (4pm instead of 3pm)
2. Execute trade at 3:30 PM PT
3. Verify file uses current day (before 4pm cutoff)
4. Execute trade at 4:05 PM PT
5. Verify file uses next day (after 4pm cutoff)

**Expected Results:**
- Custom session start hour works correctly
- Date calculation respects configured hour

---

## Logging Verification

### Test Case 15: Logging Enabled

**Steps:**
1. Ensure **Enable Logging** = `true`
2. Execute trades
3. Check NinjaTrader Output window for detailed logs
4. Check log file: `C:\Projects\FuturesTradingLog\data\logs\execution_export.log`

**Expected Log Contents:**
```
[timestamp] - INFO - Server time: [server date/time] ([timezone])
[timestamp] - INFO - Pacific time: [pacific date/time]
[timestamp] - INFO - Session date calculation - Pacific Time: [time], Session Close Date: [date]
[timestamp] - INFO - Export filename: NinjaTrader_Executions_[date].csv
[timestamp] - INFO - Exported execution: [account] [instrument] [action] [qty]@[price] - Position: [pos]
```

### Test Case 16: Logging Disabled

**Steps:**
1. Set **Enable Logging** = `false`
2. Execute trades
3. Verify only errors are logged (no info messages)

**Expected Results:**
- No INFO level logs in output
- Errors still logged if they occur

---

## Error Handling Testing

### Test Case 17: Invalid Export Path

**Steps:**
1. Configure invalid export path (e.g., `Z:\NonExistent\Path\`)
2. Restart indicator
3. Execute trade
4. Check for error messages in Output window

**Expected Results:**
- Error logged with details
- Indicator handles error gracefully

### Test Case 18: File Permission Error

**Steps:**
1. Create export file manually
2. Lock file (open in Excel with write lock)
3. Execute trade
4. Check for retry logic in logs

**Expected Results:**
- Log shows retry attempts
- "File write attempt 1 failed... Retrying..."
- Up to 3 retry attempts with 1 second delay

---

## Success Criteria Checklist

- [ ] Sunday 4pm PT execution exports to Monday file
- [ ] Monday 1pm PT execution uses Monday file (same session)
- [ ] Monday 4pm PT execution creates Tuesday file (new session)
- [ ] Friday before/after 3pm uses correct date
- [ ] DST transitions handle dates correctly
- [ ] Leap year dates calculate correctly
- [ ] Timezone conversion works from Eastern/Central to Pacific
- [ ] Legacy mode (UseSessionCloseDate=false) works
- [ ] Custom session start hour works
- [ ] Detailed logging provides troubleshooting information
- [ ] Error handling retries file writes gracefully
- [ ] NinjaTrader restart during session appends to existing file

---

## Notes for Testers

1. **System Clock:** Some tests require changing system clock. Be prepared to restore correct time after testing.

2. **Simulator vs Live:** All tests should be performed in simulator. Do NOT test in live trading environment.

3. **Log Files:** Keep log files from each test for documentation and troubleshooting.

4. **File Cleanup:** Clean export directory between tests to ensure fresh start.

5. **Documentation:** Take screenshots of:
   - NinjaTrader Output window showing logs
   - Export directory showing created files
   - File contents showing executions

6. **Test Order:** Tests can be run in any order, but timezone tests may require NinjaTrader restart.

---

## Troubleshooting

**Issue:** File not created
- Check export path exists and is writable
- Check EnableLogging to see error messages
- Verify indicator is running (check Output window)

**Issue:** Wrong date in filename
- Check server timezone in logs
- Verify Pacific timezone conversion is working
- Check UseSessionCloseDate parameter is true
- Verify SessionStartHourPT parameter is correct (15 for 3pm)

**Issue:** Timezone conversion error
- Check logs for "Using server time fallback" warning
- Verify Windows timezone database includes "Pacific Standard Time"
- Check NinjaTrader has access to timezone information

**Issue:** Duplicate executions in file
- This indicates deduplication logic issue
- Check execution IDs in CSV file
- Report with log excerpts

---

## Test Results Documentation Template

**Test Date:** [Date]
**Tester:** [Name]
**NinjaTrader Version:** [Version]
**Server Timezone:** [Timezone]

| Test Case | Expected Result | Actual Result | Pass/Fail | Notes |
|-----------|----------------|---------------|-----------|-------|
| Case 1    |                |               |           |       |
| Case 2    |                |               |           |       |
| ...       |                |               |           |       |

**Screenshots Attached:** [Yes/No]
**Log Files Attached:** [Yes/No]

**Overall Assessment:** [Pass/Fail/Partial]

**Issues Found:**
1. [Issue description]
2. [Issue description]

**Recommendations:**
1. [Recommendation]
2. [Recommendation]
