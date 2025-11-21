# Spec Tasks

These are the tasks to be completed for the spec detailed in @.agent-os/specs/2025-10-03-csv-import-reliability/spec.md

> Created: 2025-10-03
> Status: Ready for Implementation

## Tasks

### Phase 1: Database and Deduplication (Priority: High)

- [ ] **DB-001:** Create database migration for `imported_executions` table
  - Create migration file with table schema
  - Add indexes for execution_id, csv_filename, import_timestamp
  - Test migration up/down

- [ ] **DB-002:** Create ImportedExecution SQLAlchemy model
  - Define model class in models directory
  - Add relationship annotations if needed
  - Add to model imports

- [ ] **DB-003:** Create backfill migration for existing trades
  - Query all trades with execution_id
  - Insert into imported_executions with 'BACKFILL' source
  - Handle duplicate execution_ids gracefully

- [ ] **IMP-001:** Update CSV import service with deduplication logic
  - Check execution_id exists before importing each trade
  - Insert into both trades and imported_executions atomically
  - Log skipped duplicates for monitoring

- [ ] **IMP-002:** Add execution_id extraction from CSV
  - Verify execution_id column exists in NinjaTrader CSV
  - Handle missing/null execution_ids
  - Add validation for execution_id format

- [ ] **TEST-001:** Test deduplication with re-imported CSV files
  - Import same CSV file twice
  - Verify trades only imported once
  - Verify imported_executions table tracks correctly

### Phase 2: File Watcher Service (Priority: High)

- [ ] **DEP-001:** Install watchdog library
  - Add watchdog to requirements.txt
  - Run pip install watchdog
  - Verify installation

- [ ] **SVC-001:** Create CSVWatcherService class
  - Implement FileSystemEventHandler
  - Add on_modified and on_created handlers
  - Filter for .csv files only

- [ ] **SVC-002:** Implement debouncing logic
  - Add 5-second delay before triggering import
  - Cancel pending import if new event arrives
  - Use threading.Timer for debounce

- [ ] **SVC-003:** Integrate watcher with Flask application
  - Start watcher on app startup
  - Stop watcher on app shutdown
  - Add error recovery/restart logic

- [ ] **SVC-004:** Add logging for file watcher events
  - Log file modifications detected
  - Log import triggers
  - Log errors and recovery actions

- [ ] **TEST-002:** Test file watcher with live CSV updates
  - Simulate NinjaTrader writing to CSV
  - Verify imports trigger automatically
  - Test debouncing works correctly

### Phase 3: Open Position Visual Indicators (Priority: Medium)

- [ ] **POS-001:** Verify position builder sets is_open correctly
  - Check quantity calculation logic
  - Ensure is_open = (quantity != 0)
  - Test with open and closed positions

- [ ] **POS-002:** Add is_open field to position API response
  - Include is_open boolean in JSON
  - Include open quantity value
  - Include partial_pnl for matched portions

- [ ] **UI-001:** Update frontend to apply .position-open CSS class
  - Read is_open from API response
  - Apply CSS class to table rows
  - Test styling appears correctly

- [ ] **UI-002:** Add CSS styling for open positions
  - Light yellow background (#fff3cd)
  - Amber left border (#ffc107)
  - "(OPEN)" label in status column
  - Ensure readable text contrast

- [ ] **UI-003:** Display open quantity and partial P&L
  - Show "Open: +2" or "Open: -3" for quantity
  - Show "Partial P&L: $250.00"
  - Format numbers consistently

- [ ] **TEST-003:** Test open position indicators with real data
  - Create position with partial fill
  - Verify visual styling appears
  - Verify P&L shows correctly

### Phase 4: CSV Archiving (Priority: Low)

- [ ] **ARC-001:** Create archive directory structure
  - Create data/csv/archive/ directory
  - Set up YYYY-MM/ subdirectory pattern
  - Add .gitkeep to preserve structure

- [ ] **ARC-002:** Implement date extraction from CSV filename
  - Parse filename format (e.g., "Executions_2025-10-02.csv")
  - Handle various date formats
  - Return None for files without dates

- [ ] **ARC-003:** Implement archive logic
  - Check file date < today
  - Move file to archive/YYYY-MM/
  - Preserve today's active file
  - Handle file system errors gracefully

- [ ] **ARC-004:** Schedule daily midnight archive job
  - Install APScheduler if needed
  - Create scheduled job for midnight
  - Also trigger after each import completes
  - Add logging for archive operations

- [ ] **TEST-004:** Test CSV archiving process
  - Create test CSV files with old dates
  - Run archive process
  - Verify files moved correctly
  - Verify today's file not archived

### Integration and Testing

- [ ] **INT-001:** End-to-end integration test
  - Start file watcher
  - Add new execution to CSV file
  - Verify automatic import
  - Verify deduplication on re-import
  - Verify open position display
  - Verify archiving of old files

- [ ] **DOC-001:** Update user documentation
  - Document automatic import feature
  - Document open position indicators
  - Document CSV archiving behavior
  - Add troubleshooting section

- [ ] **DOC-002:** Update admin documentation
  - Document imported_executions table
  - Document file watcher service
  - Document archive directory structure
  - Add monitoring guidelines
