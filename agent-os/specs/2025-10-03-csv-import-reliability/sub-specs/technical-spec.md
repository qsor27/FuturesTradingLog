# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-10-03-csv-import-reliability/spec.md

> Created: 2025-10-03
> Version: 1.0.0

## Technical Requirements

### 1. Real-Time CSV Monitoring Service

**Implementation:**
- Use `watchdog` library for file system monitoring
- Monitor directory: `data/csv/`
- Watch for: file creation, modification events
- Debounce delay: 5 seconds (prevent multiple triggers for same file)
- Service runs as background thread/process

**File Watcher Logic:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CSVImportHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.csv'):
            # Debounce and trigger import
            pass

    def on_created(self, event):
        if event.src_path.endswith('.csv'):
            # Debounce and trigger import
            pass
```

**Service Management:**
- Start watcher on application startup
- Graceful shutdown on application exit
- Error recovery: restart watcher if it crashes
- Logging: all import events and errors

### 2. Execution ID Deduplication System

**Database Integration:**
- New table: `imported_executions` (see database-schema.md)
- Check execution_id before importing each execution
- INSERT IGNORE or ON CONFLICT DO NOTHING for atomic deduplication
- Track source CSV filename for audit purposes

**Import Process Flow:**
1. Parse CSV file into execution records
2. For each execution:
   - Extract execution_id
   - Check if execution_id exists in imported_executions table
   - If exists: skip this execution (already imported)
   - If new: insert into trades table AND imported_executions table
3. Use database transaction to ensure atomicity
4. Log skipped duplicates for debugging

**De-duplication Query:**
```python
# Check if execution already imported
existing = db.session.query(ImportedExecution).filter_by(
    execution_id=execution_id
).first()

if existing:
    # Skip - already imported
    continue

# Import trade and record execution_id
trade = Trade(...)
db.session.add(trade)

imported_exec = ImportedExecution(
    execution_id=execution_id,
    csv_filename=csv_filename,
    account=account,
    instrument=instrument
)
db.session.add(imported_exec)
db.session.commit()
```

### 3. Open Position Handling

**Position Builder Updates:**
- Position builder already correctly calculates quantity from previous spec
- Ensure `is_open` field set when `quantity != 0`
- Calculate partial P&L for matched portions of open positions

**Position Model Fields:**
```python
class Position:
    quantity: int  # Net open quantity (0 = closed, !=0 = open)
    is_open: bool  # True if quantity != 0
    matched_quantity: int  # Quantity that has been matched/closed
    partial_pnl: Decimal  # P&L from matched portions only
    unrealized_pnl: Decimal  # P&L from open quantity (future enhancement)
```

**UI Integration:**
- Add `is_open` boolean to position API response
- Frontend applies `.position-open` CSS class based on is_open flag
- Display partial P&L and open quantity in position table

### 4. Visual Position Indicators

**Frontend Changes:**
- Position table row receives `.position-open` class when `is_open: true`
- CSS styling:
```css
.position-open {
    background-color: #fff3cd; /* Light yellow */
    border-left: 4px solid #ffc107; /* Amber border */
}

.position-open .status-label::after {
    content: " (OPEN)";
    color: #856404;
    font-weight: bold;
}
```

**Position Data Display:**
- Show quantity: "Open: +2" or "Open: -3" for non-zero positions
- Show partial P&L: "Partial P&L: $250.00"
- Update indicators in real-time via polling (5 second interval)

### 5. Automatic CSV Archiving

**Archive Logic:**
- Run on application startup and daily at midnight
- Archive files where filename date < today's date
- Archive location: `data/csv/archive/YYYY-MM/filename.csv`
- Preserve today's active file (NinjaTrader still writing to it)

**Archive Process:**
```python
import os
import shutil
from datetime import date, datetime

def archive_old_csv_files():
    csv_dir = "data/csv/"
    archive_base = "data/csv/archive/"
    today = date.today()

    for filename in os.listdir(csv_dir):
        if not filename.endswith('.csv'):
            continue

        # Extract date from filename (e.g., "Executions_2025-10-02.csv")
        file_date = extract_date_from_filename(filename)

        if file_date and file_date < today:
            # Archive this file
            archive_month_dir = os.path.join(
                archive_base,
                f"{file_date.year}-{file_date.month:02d}"
            )
            os.makedirs(archive_month_dir, exist_ok=True)

            src = os.path.join(csv_dir, filename)
            dst = os.path.join(archive_month_dir, filename)
            shutil.move(src, dst)

            logger.info(f"Archived {filename} to {archive_month_dir}")
```

**Archive Scheduling:**
- Use APScheduler or similar for daily midnight job
- Also run archive check after each CSV import completes
- Never archive files with today's date

## Approach

### Phase 1: Database and Deduplication (Priority: High)
1. Create `imported_executions` table via migration
2. Update CSV import service to check execution_id before inserting
3. Add execution_id tracking to existing import flow
4. Test duplicate prevention with re-imported CSV files

### Phase 2: File Watcher Service (Priority: High)
1. Install watchdog library: `pip install watchdog`
2. Create CSVWatcherService class
3. Integrate with Flask application lifecycle
4. Add debouncing logic (5 second delay)
5. Test with live NinjaTrader CSV updates

### Phase 3: Open Position Visual Indicators (Priority: Medium)
1. Verify position builder sets `is_open` field correctly
2. Add `is_open` to position API response
3. Update frontend to apply `.position-open` CSS class
4. Add open quantity and partial P&L display
5. Test with partially filled positions

### Phase 4: CSV Archiving (Priority: Low)
1. Create archive directory structure
2. Implement archive logic with date extraction
3. Schedule daily midnight archive job
4. Test archive process doesn't interfere with active imports
5. Add archive status to admin dashboard (future)

## External Dependencies

### Python Libraries
- **watchdog** (^2.1.0) - File system event monitoring
- **APScheduler** (^3.10.0) - Scheduled job execution for archiving

### Existing Services
- CSV import service (to be enhanced with deduplication)
- Position builder service (already handles quantity correctly)
- Trade model and database (extend with execution_id tracking)

### File System
- Read/write access to `data/csv/` directory
- Create/manage `data/csv/archive/` directory structure
- Handle Windows file locking during NinjaTrader writes
