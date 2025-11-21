# Manual Test Plan: FuturesTradingLog Integration Testing

## Overview
This document provides step-by-step procedures for manually testing the integration between the ExecutionExporter indicator (NinjaTrader) and the FuturesTradingLog daily import system.

**Test Objective:** Verify that exported CSV files with session closing dates are correctly imported by FuturesTradingLog without date mismatch validation errors.

**Prerequisites:**
- ExecutionExporter indicator installed and configured in NinjaTrader 8
- FuturesTradingLog application installed and configured
- Test executions exported from NinjaTrader
- Access to FuturesTradingLog database and logs

---

## Test Setup

### 1. Configure Export Path
Both systems must use the same export directory:
- **NinjaTrader ExecutionExporter:** `C:\Projects\FuturesTradingLog\data\`
- **FuturesTradingLog Import:** `C:\Projects\FuturesTradingLog\data\`

### 2. Verify NinjaTrader Configuration
1. Open NinjaTrader ExecutionExporter parameters
2. Verify settings:
   - **Use Session Close Date:** `true`
   - **Session Start Hour (PT):** `15`
   - **Create Daily Files:** `true`
   - **Enable Logging:** `true`

### 3. Verify FuturesTradingLog Configuration
1. Open `C:\Projects\FuturesTradingLog\config.py` or equivalent
2. Verify import path: `data/`
3. Verify daily import scheduler is enabled

---

## Integration Test Case 1: Sunday Session Import

**Test Objective:** Verify Sunday evening trades export to Monday file and import correctly

**Test Date:** Any Sunday after 3pm PT (or simulated)

### Steps

**Part A: Export from NinjaTrader**
1. Execute trades on Sunday 4pm PT in NinjaTrader simulator
2. Verify file created: `NinjaTrader_Executions_[Monday YYYYMMDD].csv`
3. Check file contents:
   - Executions have Sunday timestamps in Time column
   - File is named with Monday date
4. Copy NinjaTrader logs showing session date calculation

**Part B: Import to FuturesTradingLog**
1. Run FuturesTradingLog daily import scheduler:
   ```bash
   python services/daily_import_scheduler.py
   ```
   OR manually trigger import:
   ```bash
   python routes/csv_management.py import --file NinjaTrader_Executions_[Monday YYYYMMDD].csv
   ```

2. Monitor import logs for:
   - File detection: "Found file: NinjaTrader_Executions_[Monday].csv"
   - Import start: "Processing file..."
   - Execution parsing: "Parsed X executions"
   - Position building: "Built X positions"
   - Import completion: "Import successful"

3. Check for validation errors:
   - Look for: "Date mismatch warning" - Should NOT appear
   - Look for: "Execution date does not match file date" - Should NOT appear

**Part C: Verify Database**
1. Query database for imported positions:
   ```sql
   SELECT id, instrument, entry_time, exit_time, session_date
   FROM positions
   WHERE created_at > [import_time]
   ORDER BY entry_time DESC;
   ```

2. Verify position data:
   - Entry time shows Sunday evening timestamp
   - Session date matches Monday (file date)
   - Positions are correctly built from executions

**Expected Results:**
- [ ] File exports with Monday date
- [ ] Import finds file by Monday date
- [ ] No date mismatch validation errors
- [ ] Positions created correctly in database
- [ ] Session date in database matches Monday

---

## Integration Test Case 2: Monday Morning Session Import

**Test Objective:** Verify Monday morning trades append to Monday file and import correctly

**Test Date:** Any Monday before 3pm PT

### Steps

**Part A: Export from NinjaTrader**
1. Execute trades on Monday 1pm PT
2. Verify trades append to existing Monday file: `NinjaTrader_Executions_[Monday YYYYMMDD].csv`
3. File should contain both:
   - Sunday evening executions (from previous session)
   - Monday morning executions (same session)

**Part B: Import to FuturesTradingLog**
1. Run import scheduler or manual import
2. Check for duplicate detection:
   - Previously imported Sunday executions should be skipped
   - Only new Monday morning executions should be imported
3. Monitor logs for:
   - "Skipping duplicate execution: [ID]" (for Sunday trades)
   - "Importing new execution: [ID]" (for Monday morning trades)

**Part C: Verify Database**
1. Query positions:
   ```sql
   SELECT COUNT(*) as position_count
   FROM positions
   WHERE session_date = '[Monday date]';
   ```

2. Verify:
   - Existing positions updated if Monday trades modify them
   - New positions created if Monday trades are new positions
   - No duplicate positions created

**Expected Results:**
- [ ] Monday morning trades append to Monday file
- [ ] Import detects previously imported Sunday executions
- [ ] Only new Monday executions are imported
- [ ] No duplicate positions created
- [ ] Positions correctly updated with Monday executions

---

## Integration Test Case 3: Session Transition Import

**Test Objective:** Verify correct handling when session transitions from Monday to Tuesday

**Test Date:** Monday 3pm PT (session boundary)

### Steps

**Part A: Export Before Transition (Monday 2:45pm PT)**
1. Execute trades at Monday 2:45pm PT
2. Verify file: `NinjaTrader_Executions_[Monday YYYYMMDD].csv`
3. Import to FuturesTradingLog
4. Verify positions created with Monday session date

**Part B: Export After Transition (Monday 4:00pm PT)**
1. Execute trades at Monday 4:00pm PT
2. Verify NEW file created: `NinjaTrader_Executions_[Tuesday YYYYMMDD].csv`
3. Import to FuturesTradingLog
4. Verify positions created with Tuesday session date

**Part C: Verify Both Sessions in Database**
1. Query Monday positions:
   ```sql
   SELECT COUNT(*) as count
   FROM positions
   WHERE session_date = '[Monday date]';
   ```

2. Query Tuesday positions:
   ```sql
   SELECT COUNT(*) as count
   FROM positions
   WHERE session_date = '[Tuesday date]';
   ```

3. Verify:
   - Monday positions are separate from Tuesday positions
   - Session dates are distinct
   - No cross-contamination between sessions

**Expected Results:**
- [ ] File rotation occurs at 3pm PT session boundary
- [ ] Monday file imports with Monday session date
- [ ] Tuesday file imports with Tuesday session date
- [ ] Sessions remain distinct in database

---

## Integration Test Case 4: Weekend Handling

**Test Objective:** Verify Friday session handling and weekend gap

**Test Date:** Friday 2pm PT and Friday 3:30pm PT

### Steps

**Part A: Friday Before 3pm**
1. Execute trades Friday 2pm PT
2. Verify file: `NinjaTrader_Executions_[Friday YYYYMMDD].csv`
3. Import and verify Friday session date

**Part B: Friday After 3pm (Market Closed)**
1. If simulator allows, execute trade Friday 3:30pm PT
2. Expected file: `NinjaTrader_Executions_[Saturday YYYYMMDD].csv`
3. Note: This is a non-trading day file

**Part C: Weekend Gap**
1. Verify no files for Saturday/Sunday trading (market closed)
2. Monday import resumes with Monday file

**Expected Results:**
- [ ] Friday before 3pm uses Friday file
- [ ] Friday after 3pm uses Saturday file (if applicable)
- [ ] No weekend trading files (unless futures weekend trading)
- [ ] Monday import resumes correctly

---

## Integration Test Case 5: Historical Import

**Test Objective:** Verify import of multiple historical files from different sessions

### Steps

**Setup: Create Multiple Session Files**
1. Use NinjaTrader to export executions from multiple sessions:
   - Monday session: `NinjaTrader_Executions_20251110.csv`
   - Tuesday session: `NinjaTrader_Executions_20251111.csv`
   - Wednesday session: `NinjaTrader_Executions_20251112.csv`

**Import All Files**
1. Run batch import:
   ```bash
   python routes/csv_management.py import_all --directory data/
   ```

2. Monitor logs for each file:
   - Monday file processed -> Monday session date
   - Tuesday file processed -> Tuesday session date
   - Wednesday file processed -> Wednesday session date

**Verify Database**
1. Query positions by session:
   ```sql
   SELECT session_date, COUNT(*) as position_count
   FROM positions
   WHERE session_date BETWEEN '2025-11-10' AND '2025-11-12'
   GROUP BY session_date
   ORDER BY session_date;
   ```

2. Verify:
   - Each session has distinct positions
   - Session dates match file dates
   - Total position count is correct

**Expected Results:**
- [ ] All historical files import successfully
- [ ] Session dates correctly assigned per file
- [ ] No date mismatch errors across multiple files
- [ ] Positions grouped correctly by session

---

## Integration Test Case 6: Date Validation

**Test Objective:** Verify FuturesTradingLog date validation accepts session close dates

**Background:** FuturesTradingLog has validation that checks execution timestamps against file dates.

### Steps

**Part A: Normal Case (Should Pass)**
1. Export file with Sunday 5pm PT execution to Monday file
2. Import to FuturesTradingLog
3. Check validation logs:
   - Execution timestamp: Sunday 5pm PT
   - File date: Monday
   - Validation: Should PASS (Sunday evening is part of Monday session)

**Part B: Abnormal Case (Should Warn)**
1. Manually edit CSV to add execution with Wednesday timestamp to Monday file
2. Attempt import
3. Check validation logs:
   - Should log WARNING: "Execution timestamp significantly different from file date"
   - Should still import but flag for review

**Expected Results:**
- [ ] Session close date logic aligns with validation expectations
- [ ] Sunday evening executions in Monday file pass validation
- [ ] Out-of-session executions trigger warnings but don't block import

---

## Integration Test Case 7: DST Transition Import

**Test Objective:** Verify import during Daylight Saving Time transitions

**Test Date:** March 9, 2025 (Spring Forward) and November 2, 2025 (Fall Back)

### Steps

**Spring Forward (March 9)**
1. Export executions from Sunday March 9 at 4pm PDT (after transition)
2. Verify file: `NinjaTrader_Executions_20250310.csv` (Monday)
3. Import to FuturesTradingLog
4. Verify timestamps and session dates handle DST correctly

**Fall Back (November 2)**
1. Export executions from Sunday November 2 at 4pm PST (after transition)
2. Verify file: `NinjaTrader_Executions_20251103.csv` (Monday)
3. Import to FuturesTradingLog
4. Verify timestamps and session dates handle DST correctly

**Expected Results:**
- [ ] DST transitions don't cause date calculation errors
- [ ] Timestamps remain accurate across DST changes
- [ ] Session dates correctly span DST boundary

---

## Integration Test Case 8: Multi-Instrument Import

**Test Objective:** Verify import handles multiple instruments in same session file

### Steps

**Part A: Export Mixed Instruments**
1. In NinjaTrader, trade multiple instruments in same session:
   - ES (E-mini S&P 500)
   - NQ (E-mini NASDAQ)
   - YM (E-mini Dow)
2. All executions export to same session file
3. Verify CSV contains mixed instruments

**Part B: Import and Verify**
1. Import session file
2. Check logs for each instrument:
   - "Processing ES execution"
   - "Processing NQ execution"
   - "Processing YM execution"

**Part C: Verify Database**
1. Query positions by instrument:
   ```sql
   SELECT instrument, COUNT(*) as position_count
   FROM positions
   WHERE session_date = '[session date]'
   GROUP BY instrument;
   ```

2. Verify:
   - Each instrument has separate positions
   - Session date is consistent across all instruments
   - Position building is correct per instrument

**Expected Results:**
- [ ] Multiple instruments export to single session file
- [ ] Import correctly parses all instruments
- [ ] Positions created separately per instrument
- [ ] Session date applies to all instruments

---

## Integration Test Case 9: Position Continuity

**Test Objective:** Verify multi-execution positions are correctly built across session file imports

**Test Date:** Any trading day with scaling in/out

### Steps

**Part A: Create Multi-Execution Position**
1. In NinjaTrader, execute scaling position:
   - Entry 1: Buy 2 ES at 10am
   - Entry 2: Buy 1 ES at 11am (total position: 3 long)
   - Exit 1: Sell 1 ES at 1pm (reduce to 2 long)
   - Exit 2: Sell 2 ES at 2pm (close position)

2. All executions export to same session file

**Part B: Import and Build Position**
1. Import session file
2. Check position builder logs:
   - "Position opened: 2 contracts"
   - "Position scaled in: +1 contract (total: 3)"
   - "Position scaled out: -1 contract (total: 2)"
   - "Position closed: -2 contracts (total: 0)"

**Part C: Verify Position in Database**
1. Query the position:
   ```sql
   SELECT *
   FROM positions
   WHERE session_date = '[session date]'
   AND instrument = 'ES'
   ORDER BY entry_time;
   ```

2. Verify position attributes:
   - Entry quantity: 3 (total scaled in)
   - Exit quantity: 3 (total scaled out)
   - Entry average price: Weighted average of entries
   - Exit average price: Weighted average of exits
   - PnL: Correctly calculated from all executions

**Expected Results:**
- [ ] Multi-execution position correctly built from session file
- [ ] Scaling in/out tracked accurately
- [ ] PnL calculated from all executions
- [ ] Position integrity maintained

---

## Integration Test Case 10: Error Recovery

**Test Objective:** Verify import recovery from errors during processing

### Steps

**Part A: Simulate Import Error**
1. Corrupt a session file (invalid CSV format, missing columns)
2. Attempt import
3. Check error logs:
   - Error detected and logged
   - Import rolled back (no partial data)
   - Other files continue to import

**Part B: Fix and Re-Import**
1. Fix corrupted file
2. Re-run import
3. Verify successful import on second attempt

**Expected Results:**
- [ ] Import errors are caught and logged
- [ ] Failed imports don't leave partial data
- [ ] Fixed files can be re-imported successfully

---

## Daily Import Scheduler Testing

### Test Case 11: Automated Daily Import

**Test Objective:** Verify daily import scheduler finds and imports new session files

### Steps

**Part A: Setup Scheduler**
1. Configure daily import scheduler to run at specific time (e.g., 3:00 PM PT)
2. Ensure scheduler has access to export directory

**Part B: Generate Test Data**
1. Export executions throughout day (before scheduler runs)
2. Allow scheduler to run at configured time

**Part C: Monitor Scheduler**
1. Check scheduler logs:
   - "Scheduler triggered at [time]"
   - "Scanning directory: [export path]"
   - "Found files: [list]"
   - "Importing file: [filename]"
   - "Import completed: [summary]"

**Part D: Verify Results**
1. Check database for newly imported positions
2. Verify scheduler marked files as processed
3. Verify no duplicate imports on next scheduler run

**Expected Results:**
- [ ] Scheduler runs at configured time
- [ ] New session files detected and imported
- [ ] Previously imported files skipped
- [ ] Import summary logged

---

## Performance Testing

### Test Case 12: Large File Import

**Test Objective:** Verify import performance with large session files (many executions)

### Steps

**Part A: Generate Large File**
1. Use NinjaTrader to generate session file with 100+ executions
2. File size: 50+ KB

**Part B: Import Large File**
1. Time the import process
2. Monitor memory usage
3. Check for performance degradation

**Part C: Verify Data Integrity**
1. Verify all executions imported
2. Verify all positions built correctly
3. Check for data corruption

**Expected Results:**
- [ ] Large files import in reasonable time (<10 seconds)
- [ ] No memory issues during import
- [ ] Data integrity maintained
- [ ] Performance is acceptable

---

## Success Criteria Checklist

### File Export & Naming
- [ ] Sunday evening trades export to Monday file
- [ ] Session close date logic produces correct filenames
- [ ] File naming matches FuturesTradingLog expectations

### Import Detection
- [ ] Daily import scheduler finds session files
- [ ] File pattern matching works correctly
- [ ] Multiple session files imported in correct order

### Date Validation
- [ ] No "date mismatch" validation errors
- [ ] Session close date accepted by validation
- [ ] Execution timestamps validated correctly

### Position Building
- [ ] Single-execution positions built correctly
- [ ] Multi-execution positions built correctly
- [ ] Scaling in/out tracked accurately
- [ ] PnL calculated correctly from all executions

### Session Management
- [ ] Sessions remain distinct in database
- [ ] Session transitions handled correctly
- [ ] Weekend gaps don't cause issues

### Error Handling
- [ ] Import errors logged clearly
- [ ] Failed imports don't corrupt database
- [ ] Recovery from errors works

### Integration Points
- [ ] NinjaTrader and FuturesTradingLog use same session date logic
- [ ] Export path matches import path
- [ ] CSV format compatible
- [ ] Timezone handling consistent

---

## Troubleshooting

**Issue:** Import not finding files
- Check export path matches import path
- Verify file naming pattern: `NinjaTrader_Executions_YYYYMMDD.csv`
- Check file permissions

**Issue:** Date mismatch validation errors
- Verify NinjaTrader UseSessionCloseDate = true
- Check session start hour configuration (should be 15)
- Review NinjaTrader logs for correct session date calculation

**Issue:** Duplicate positions created
- Check duplicate detection logic in import
- Verify execution ID uniqueness
- Review deduplication logs

**Issue:** Positions not building correctly
- Check position builder logs
- Verify entry/exit classification in CSV
- Review position tracking by instrument and account

**Issue:** Missing executions after import
- Check for CSV parsing errors in logs
- Verify all executions have required fields
- Check for duplicate execution IDs causing skips

---

## Test Results Documentation Template

**Test Date:** [Date]
**Tester:** [Name]
**NinjaTrader Version:** [Version]
**FuturesTradingLog Version:** [Version]

| Test Case | Expected Result | Actual Result | Pass/Fail | Notes |
|-----------|----------------|---------------|-----------|-------|
| Case 1    |                |               |           |       |
| Case 2    |                |               |           |       |
| ...       |                |               |           |       |

**Export Files Generated:**
- [List of CSV files with dates]

**Import Logs Attached:** [Yes/No]
**Database Queries Attached:** [Yes/No]
**Screenshots Attached:** [Yes/No]

**Overall Assessment:** [Pass/Fail/Partial]

**Integration Issues Found:**
1. [Issue description]
2. [Issue description]

**Data Integrity Verified:** [Yes/No/Partial]

**Recommendations:**
1. [Recommendation]
2. [Recommendation]

---

## Appendix: Useful Database Queries

### Check Recent Imports
```sql
SELECT
    session_date,
    COUNT(*) as position_count,
    SUM(pnl) as total_pnl,
    MIN(entry_time) as first_entry,
    MAX(exit_time) as last_exit
FROM positions
WHERE created_at > DATETIME('now', '-1 day')
GROUP BY session_date
ORDER BY session_date DESC;
```

### Find Positions by Session Date
```sql
SELECT *
FROM positions
WHERE session_date = '2025-11-10'
ORDER BY entry_time;
```

### Check for Duplicate Executions
```sql
SELECT execution_id, COUNT(*) as count
FROM executions
GROUP BY execution_id
HAVING count > 1;
```

### Verify Session Date Distribution
```sql
SELECT
    DATE(session_date) as date,
    COUNT(*) as positions,
    COUNT(DISTINCT instrument) as instruments
FROM positions
WHERE session_date >= DATE('now', '-7 days')
GROUP BY DATE(session_date)
ORDER BY date DESC;
```
