# Specification: NinjaTrader Session Date Export

## Goal
Modify the NinjaTrader ExecutionExporter indicator to export executions with the trading session's **closing date** rather than the current date, ensuring alignment with the futures market schedule and the FuturesTradingLog application's daily import strategy.

## Problem Statement

The current NinjaTrader ExecutionExporter indicator exports execution data using the **current date** or **opening date** of the session. This causes issues with the daily import strategy:

1. **Date Mismatch**: Trading session starting Sunday 3pm PT exports as "Sunday" but should be "Monday" (closes Monday 2pm PT)
2. **Import Failures**: Application expects `NinjaTrader_Executions_20251111.csv` (Monday) but gets `NinjaTrader_Executions_20251110.csv` (Sunday)
3. **Open Position Data**: Exporting during active session creates partial position data
4. **Validation Errors**: Date mismatch validation rejects files during import

## Futures Market Schedule

**Trading Hours:** 23 hours/day, 5 days/week
- **Sunday:** 3pm PT (open) → Monday 2pm PT (close) = Export as **Monday.csv**
- **Monday:** 3pm PT (open) → Tuesday 2pm PT (close) = Export as **Tuesday.csv**
- **Tuesday:** 3pm PT (open) → Wednesday 2pm PT (close) = Export as **Wednesday.csv**
- **Wednesday:** 3pm PT (open) → Thursday 2pm PT (close) = Export as **Thursday.csv**
- **Thursday:** 3pm PT (open) → Friday 2pm PT (close) = Export as **Friday.csv**

**Closed:** Friday 2pm PT → Sunday 3pm PT (Market closed for weekend)

## User Stories

- As a trader, I want executions exported with the session closing date so imports match the expected file naming pattern
- As a trader, I want executions from Sunday 3pm PT → Monday 2pm PT exported as Monday's file so data aligns with market close
- As a system operator, I want clear validation that exported files match the expected session date so import errors are prevented
- As a developer, I want the indicator to handle timezone conversion correctly so Pacific Time sessions export with correct dates

## Specific Requirements

### Core Logic Requirements

**Session Date Calculation:**
- After 3pm Pacific Time (6pm Eastern): Use **next day's date** for export filename
- Before 3pm Pacific Time (6pm Eastern): Use **current day's date** for export filename
- This ensures the file uses the session's **closing date**

**Example:**
```
Current Time: Sunday 4pm PT (session opened at 3pm PT)
Export Date: Monday (session will close Monday 2pm PT)
Filename: NinjaTrader_Executions_20251111.csv

Current Time: Monday 1pm PT (session still open from Sunday 3pm PT)
Export Date: Monday (session will close Monday 2pm PT)
Filename: NinjaTrader_Executions_20251111.csv

Current Time: Monday 3:05pm PT (new session just opened)
Export Date: Tuesday (session will close Tuesday 2pm PT)
Filename: NinjaTrader_Executions_20251112.csv
```

### Timezone Handling

**Primary Timezone:** Pacific Time (America/Los_Angeles)
- NinjaTrader may run on servers in different timezones
- Indicator must convert server time to Pacific Time before determining session date
- Use NinjaTrader's built-in timezone support: `Core.Globals.Now` with timezone conversion

**Secondary Timezone:** Eastern Time (America/New_York)
- Alternative cutoff: 6pm Eastern = 3pm Pacific
- Support both for flexibility

### File Naming Requirements

**Format:** `NinjaTrader_Executions_YYYYMMDD.csv`
- YYYY = 4-digit year
- MM = 2-digit month (01-12)
- DD = 2-digit day (01-31)

**Examples:**
- Sunday 4pm PT session → `NinjaTrader_Executions_20251111.csv` (Monday)
- Monday 1pm PT session → `NinjaTrader_Executions_20251111.csv` (Monday)
- Monday 4pm PT session → `NinjaTrader_Executions_20251112.csv` (Tuesday)

### Export Timing

**Continuous Export During Session:**
- Append executions to current day's file as they occur
- File grows throughout 23-hour trading session
- Use session closing date for entire session duration

**No Export During Market Close:**
- Friday 2pm PT → Sunday 3pm PT: No trading, no exports
- File remains in place until next session begins

### Data Validation

**Indicator Should:**
- Log current time in Pacific Time for debugging
- Log calculated session closing date
- Log final export filename
- Validate file was created/appended successfully
- Handle file write errors gracefully

**Warning Conditions:**
- If unable to determine Pacific Time (timezone conversion fails)
- If file write fails due to permissions or disk space
- If session date calculation seems incorrect (weekend dates, etc.)

### Backward Compatibility

**Existing Data:**
- Do not modify existing CSV files in archive
- New indicator logic applies only to new exports going forward
- Historical data imports remain unchanged

**Configuration:**
- Maintain existing export path configuration
- Maintain existing column structure and order
- No breaking changes to CSV format

## Technical Implementation (C# - NinjaScript)

### Key Components

**1. Timezone Conversion**
```csharp
TimeZoneInfo pacificZone = TimeZoneInfo.FindSystemTimeZoneById("Pacific Standard Time");
DateTime pacificNow = TimeZoneInfo.ConvertTime(Core.Globals.Now, pacificZone);
```

**2. Session Date Calculation**
```csharp
DateTime sessionCloseDate;
if (pacificNow.Hour >= 15) // After 3pm PT
{
    sessionCloseDate = pacificNow.AddDays(1).Date;
}
else
{
    sessionCloseDate = pacificNow.Date;
}
```

**3. Filename Generation**
```csharp
string filename = $"NinjaTrader_Executions_{sessionCloseDate:yyyyMMdd}.csv";
string fullPath = Path.Combine(exportDirectory, filename);
```

**4. Logging**
```csharp
Log($"Current Pacific Time: {pacificNow:yyyy-MM-dd HH:mm:ss}", LogLevel.Information);
Log($"Session Close Date: {sessionCloseDate:yyyy-MM-dd}", LogLevel.Information);
Log($"Export Filename: {filename}", LogLevel.Information);
```

### Error Handling

**Timezone Conversion Failures:**
- Fallback to server time with warning log
- Use best-guess date based on server time
- Alert user to check timezone configuration

**File Write Failures:**
- Retry up to 3 times with 1-second delay
- Log detailed error message
- Buffer executions in memory if file unavailable

**Invalid Date Calculations:**
- Validate date is not in the past (more than 1 day old)
- Validate date is not in the future (more than 2 days ahead)
- Log warning if date seems incorrect

## Configuration Settings

**Indicator Parameters:**
- `ExportPath` (string): Directory path for CSV exports (default: `C:\Projects\FuturesTradingLog\data\`)
- `UseSessionCloseDate` (bool): Enable session close date logic (default: `true`)
- `SessionStartHourPT` (int): Hour when new session begins in Pacific Time (default: `15` for 3pm)
- `EnableLogging` (bool): Enable detailed logging (default: `true`)

## Testing Requirements

**Unit Tests:**
- Test timezone conversion (various timezones → Pacific Time)
- Test session date calculation (before/after 3pm PT)
- Test filename generation (correct format, correct date)
- Test weekend handling (Friday close → Sunday open)

**Integration Tests:**
- Test with NinjaTrader simulator running in different timezones
- Verify executions from Sunday 4pm PT session write to Monday file
- Verify executions from Monday 1pm PT session write to Monday file
- Verify executions from Monday 4pm PT session write to Tuesday file
- Verify file grows correctly throughout 23-hour session

**Edge Cases:**
- Daylight Saving Time transitions
- Leap year date handling
- NinjaTrader restart mid-session
- Multiple accounts trading simultaneously

## Success Criteria

- ✓ Executions export with session closing date, not current date
- ✓ Sunday 3pm PT → Monday 2pm PT session exports as Monday file
- ✓ Timezone conversion handles all US timezones correctly
- ✓ File naming matches FuturesTradingLog import expectations
- ✓ Import validation passes without date mismatch errors
- ✓ Detailed logging for troubleshooting
- ✓ Backward compatible with existing CSV format
- ✓ No breaking changes to archived historical data

## Documentation Requirements

- Update `NINJATRADER_EXPORT_SETUP.md` with new session date logic
- Add timezone configuration instructions
- Document testing procedure for verifying correct date export
- Include troubleshooting guide for common timezone issues
- Provide example log output showing correct date calculation

## Dependencies

- NinjaTrader 8 platform with NinjaScript support
- Access to modify ExecutionExporter indicator source code
- FuturesTradingLog application with daily import scheduler (Task Group 4)
- Understanding of C# and NinjaScript indicator development

## Related Specifications

- [2025-11-03 Position Boundary Detection](../2025-11-03-position-boundary-detection/) - Task Group 4: Daily Import Strategy
- [2025-10-31 NinjaTrader CSV Import Fix](../2025-10-31-ninjatrader-csv-import-fix/) - CSV import service implementation
