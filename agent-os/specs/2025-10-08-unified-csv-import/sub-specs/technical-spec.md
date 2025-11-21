# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-10-08-unified-csv-import/spec.md

## Technical Requirements

### Unified CSV Import Service

- **Location:** `services/unified_csv_import_service.py`
- **Responsibilities:**
  - CSV format detection (NT Grid, TradeLog, raw executions)
  - File deduplication tracking (processed files registry)
  - CSV parsing and validation
  - Database import with transaction support
  - Automatic position rebuilding after imports
  - File archiving with timestamps
  - Error handling and recovery
  - Processing status tracking

- **Key Methods:**
  - `process_csv_file(file_path)` - Main processing pipeline
  - `detect_csv_format(file_path)` - Auto-detect CSV format
  - `is_file_processed(filename)` - Check if already imported
  - `get_processing_status()` - Return current service status
  - `manual_trigger_processing()` - Force immediate processing
  - `get_processing_history(limit=50)` - Recent import history

### File Watcher Integration

- **Service:** Simplify existing `services/csv_watcher_service.py`
- **Changes:**
  - Keep file system monitoring and debouncing logic
  - Delegate all processing to unified import service
  - Remove redundant processing code
  - Maintain 5-second debounce for NinjaTrader file writes

### CSV Format Detection

- **NT Grid CSV Detection:**
  - Has columns: Instrument, Action, Quantity, Price, Time, ID, E/X, Position, Order ID, Name, Commission, Rate, Account, Connection
  - Action values: Buy, Sell, BuyToCover, SellShort
  - E/X values: Entry, Exit

- **TradeLog CSV Detection:**
  - Has columns: instrument, side_of_market, quantity, entry_price, entry_time, account, commission, entry_execution_id
  - Pre-aggregated trade data

- **Raw Executions CSV Detection:**
  - Minimal column set matching execution data
  - Individual execution records

### Database Transaction Support

- Wrap all imports in database transactions
- Rollback on any error during processing
- Atomic imports (all-or-nothing)
- Proper error logging and reporting

### Route Consolidation

**Keep:**
- `/api/csv/status` - GET status of import system
- `/api/csv/process-now` - POST manual trigger
- `/api/csv/history` - GET recent processing history

**Remove:**
- Remove manual upload endpoints from `routes/upload.py`
- Remove position rebuild endpoints from `routes/positions.py`
- Remove NT executions processing endpoint
- Remove CSV file selection endpoints

### Frontend Changes

**Create New Page:** `templates/csv_manager.html`
- Import service status indicator
- File watcher status (running/stopped)
- Last import timestamp
- Files in processing queue
- Recent processing history table (50 entries)
- "Process Now" button
- Auto-refresh every 30 seconds

**UI Elements to Remove:**

#### Position Dashboard (`templates/positions/dashboard.html`)
**Remove Entire Section (lines 440-462):**
- [ ] Remove entire `<div class="rebuild-section">` containing "Position Management"
- [ ] Remove `<h3>Position Management</h3>` heading
- [ ] Remove "Rebuild Positions" button and its action group
- [ ] Remove "Re-import Deleted Trades" button and its action group
- [ ] Remove CSV file selection dropdown (`#csvFileSelect`)
- [ ] Remove `<div id="managementStatus">` status display
- [ ] Remove ALL associated JavaScript functions:
  - `rebuildPositions()` function (lines 622-655)
  - `reimportTrades()` function (lines 657-703)
  - `importSelectedFile()` function (lines 705-755)
- [ ] Remove associated API endpoint calls to:
  - `/positions/rebuild_positions`
  - `/positions/list_csv_files`
  - `/positions/reimport_csv`

**Add Replacement (optional):**
- [ ] Add small status badge showing "Auto-import: Active" with link to CSV Manager

#### Upload Page (`templates/upload.html`)
**Remove Manual Upload Form (lines 40-54):**
- [ ] Remove file input: `<input type="file" id="csvFile" name="file" accept=".csv">`
- [ ] Remove "Upload" submit button
- [ ] Remove "Process NT Executions Export" button
- [ ] Remove entire `<form id="uploadForm">` element
- [ ] Remove upload form submission handler JavaScript (lines 67-101)
- [ ] Remove `processNTButton` click handler JavaScript (lines 143-178)

**Keep:**
- [ ] Keep "Automatic Import Active" status banner (lines 18-38)
- [ ] Keep "Process Now" button with its handler (lines 104-128)
- [ ] Keep "Check Status" button with its handler (lines 130-141)

**Add:**
- [ ] Add link to new CSV Manager page
- [ ] Add recent processing history display (last 5 imports)

#### Trades Page (`templates/trades/index.html`)
**Note:** Need to verify if this file exists and contains Step 1/Step 2 sections
- [ ] If exists, remove "Step 1: Process NT Executions" section
- [ ] If exists, remove "Step 2: Import Trade Log" section
- [ ] If exists, remove associated form elements and buttons
- [ ] If exists, remove associated JavaScript handlers

#### Navigation Updates
**Add to Main Navigation:**
- [ ] Add "CSV Manager" link to main navigation menu in `templates/base.html`
- [ ] Update header buttons in positions dashboard to include CSV Manager link
- [ ] Update header buttons in upload page to redirect to CSV Manager

#### Backend Route Removals

**From `routes/positions.py`:**
- [ ] Remove `@positions_bp.route('/rebuild_positions', methods=['POST'])` endpoint
- [ ] Remove `rebuild_positions()` function
- [ ] Remove `@positions_bp.route('/list_csv_files')` endpoint
- [ ] Remove `list_csv_files()` function
- [ ] Remove `@positions_bp.route('/reimport_csv', methods=['POST'])` endpoint
- [ ] Remove `reimport_csv()` function

**From `routes/upload.py`:**
- [ ] Remove `@upload_bp.route('/upload', methods=['POST'])` endpoint (if exists)
- [ ] Remove `upload_file()` function (if exists)
- [ ] Remove `@upload_bp.route('/process-nt-executions', methods=['POST'])` endpoint
- [ ] Remove `process_nt_executions()` function
- [ ] Remove manual file upload handling code

**From `routes/main.py`:**
- [ ] Verify and update any CSV upload routes to redirect to CSV Manager
- [ ] Remove redundant CSV processing endpoints

### Configuration

**New Settings in `config.py`:**
```python
CSV_AUTO_IMPORT_ENABLED = True
CSV_WATCH_DIRECTORY = config.data_dir
CSV_ARCHIVE_DIRECTORY = config.data_dir / 'archive'
CSV_CHECK_INTERVAL = 300  # 5 minutes in seconds
CSV_DEBOUNCE_SECONDS = 5.0
```

### Application Startup

**Update `app.py`:**
- Initialize unified CSV import service on startup
- Start file watcher with unified service callback
- Register CSV management blueprint
- Cleanup services on shutdown

## External Dependencies

No new external dependencies required. All functionality uses existing libraries:
- `watchdog` - Already used for file monitoring
- `pandas` - Already used for CSV parsing
- `pathlib` - Standard library for file operations
