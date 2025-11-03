# Specification: NinjaTrader CSV Import Fix

## Goal
Fix the critical CSV import reliability issues by consolidating 4 fragmented import services into a single, account-aware system that automatically processes NinjaTrader execution files with incremental deduplication and proper position tracking.

## User Stories
- As a trader, I want executions to automatically import from CSV files placed in the data folder so that I don't need manual intervention
- As a system operator, I want positions to be tracked separately per account so that multi-account trading data remains accurate and isolated

## Specific Requirements

**Automatic File Detection and Monitoring**
- Watch only the `C:\Projects\FuturesTradingLog\data` folder for new CSV files matching pattern `NinjaTrader_Executions_YYYYMMDD.csv`
- Start background watcher service automatically when application launches via `python app.py` or `docker-compose up`
- Use 30-60 second polling interval to detect new files or file modifications
- Handle NinjaTrader file locks gracefully by retrying file reads with exponential backoff
- Process files incrementally throughout the trading day as NinjaTrader appends new executions
- Move files to `data/archive` only after BOTH conditions met: (1) successful import AND (2) next calendar day

**Execution ID-Based Deduplication**
- Track processed execution IDs in Redis cache with 14-day TTL to prevent duplicate imports
- Use CSV column "ID" (execution ID from NinjaTrader) as primary deduplication key
- For executions without ID, fallback to composite key: `{Time}_{Account}_{Instrument}_{Action}_{Quantity}_{Price}`
- Check Redis cache before inserting each execution into SQLite database
- Store execution IDs in Redis set with key pattern: `processed_executions:{YYYYMMDD}`
- Support incremental file processing where same file is read multiple times as it grows during trading day

**Account-Specific Position Tracking**
- Treat each account as completely independent position tracking context
- NEVER combine or aggregate positions across different accounts
- Track quantity flow separately per account: flat (0) -> long/short (+/-) -> flat (0) lifecycle
- Position close detection: when running quantity returns to exactly 0 for that account+instrument combination
- Position open detection: when running quantity moves from 0 to non-zero for that account+instrument combination
- Support simultaneous positions in same instrument across multiple accounts (e.g., APEX1279810000057 and APEX1279810000058 both trading MNQ)
- Pass account parameter through entire position building pipeline from execution to final position record

**Service Consolidation**
- Replace `csv_watcher_service.py`, `import_service.py`, `unified_csv_import_service.py`, and `csv_processor.py` with single `ninjatrader_import_service.py`
- Implement clear separation of concerns: file watching, CSV parsing, execution insertion, position building
- Reuse existing `EnhancedPositionServiceV2` for position building but fix account parameter passing
- Integrate with existing `ExecutionProcessing.process_trades()` for CSV parsing and validation
- Use existing Redis cache service for execution ID tracking
- Maintain backward compatibility with existing database schema and domain models

**File Processing Workflow**
- Detect CSV file creation or modification in `data` folder
- Wait for file stability (no size changes for 5 seconds) before reading
- Read CSV with pandas, validate required columns: Instrument, Action, Quantity, Price, Time, ID, E/X, Position, Order ID, Name, Commission, Rate, Account, Connection
- Parse each row and check execution ID against Redis cache
- Insert new executions into `trades` table with account, instrument, quantity, price, time, execution_id, commission
- Store execution ID in Redis processed set
- Trigger incremental position rebuild for affected account+instrument combinations only
- Invalidate relevant cache entries for updated accounts and instruments
- Leave file in `data` folder until next day AND all executions successfully imported

**Position Building Algorithm Enhancement**
- Modify `EnhancedPositionServiceV2.rebuild_positions_for_account_instrument()` to accept account parameter
- Change position grouping from just instrument to (account, instrument) tuple
- Track running quantity separately per account using quantity flow analyzer
- Detect position boundaries: start when qty moves from 0, end when qty returns to 0
- Handle position scaling (adding contracts), reduction (partial exits), and reversals (long to short or vice versa)
- Calculate accurate P&L using futures multipliers from `data/config/instrument_multipliers.json`
- Create position records with account field properly populated
- Map executions to positions via `position_executions` table maintaining account association

**Error Handling and Recovery**
- Log all file processing attempts with timestamps, file names, and execution counts to `data/logs/import.log`
- Retry transient failures (file locks, network issues) with exponential backoff: 1s, 2s, 4s, 8s max
- Skip malformed CSV rows and log warnings without failing entire file import
- Handle corrupted files by catching pandas read errors and moving to `data/error` folder
- Provide health check endpoint `/api/import/health` returning last successful import time and pending file count
- Support manual retry of failed files via endpoint `/api/import/retry/{filename}`
- Gracefully handle application shutdown by completing current import before stopping watcher thread

**Database Schema Preservation**
- No schema changes required - existing `trades` and `positions` tables already support account field
- Ensure all existing indexes remain: `idx_trades_account`, `idx_trades_instrument`, `idx_trades_entry_time`, `idx_positions_account_instrument`
- Continue using SQLite WAL mode for concurrent read/write performance
- Maintain foreign key constraints between `positions` and `position_executions` tables

**Background Service Architecture**
- Implement as background thread started in `app.py` on application initialization
- Use Python threading with daemon=False to ensure graceful shutdown
- Register cleanup handler with Flask `atexit` to stop watcher on application termination
- Maintain service state in memory: last processed file, last import time, error count
- Expose service status via endpoint `/api/import/status` for monitoring

**Historical Data Re-import**
- Provide database migration script `scripts/reimport_historical_csvs.py` for one-time execution
- Process all CSV files from `data/archive` folder in chronological order by filename date
- Clear existing `trades` and `positions` tables before re-import
- Rebuild all positions from scratch using account-aware position builder
- Log summary statistics: files processed, executions imported, positions created, accounts found
- Support dry-run mode with `--dry-run` flag to preview what would be imported without database changes

## Visual Design

**`planning/visuals/importerroroncsv-manager.png`**
- Shows current manual CSV import interface at `/csv-manager` endpoint with file selection checkboxes
- Displays failed import results: "0 successful, 6 failed" with "File not found or invalid type" errors
- Files listed include NinjaTrader_Executions_20251024.csv through 20251031.csv format
- Interface has sections for "NinjaTrader Executions" and "Processed TradeLog" with 91 total files
- Buttons visible: "Select All", "Select None", "Select Recent (Last 7 Days)", "Import Selected Files"
- This entire manual import UI will be removed AFTER automatic system is tested and confirmed working
- Error indicates path resolution bug where backend cannot locate files that frontend displays
- Automatic system will eliminate need for this interface by processing files immediately upon detection

## Existing Code to Leverage

**EnhancedPositionServiceV2 (`services/enhanced_position_service_v2.py`)**
- Already implements PositionBuilder with QuantityFlowAnalyzer for detecting position boundaries based on quantity returning to 0
- Contains `rebuild_positions_for_account_instrument()` method that needs account parameter properly passed to grouping logic
- Has `_deduplicate_trades()` method using execution IDs to prevent duplicate processing
- Provides `_save_position_to_db()` for atomic position creation with execution mappings
- Need to modify `_process_trades_for_instrument()` to group by (account, instrument) instead of just instrument

**CSVWatcherService (`services/csv_watcher_service.py`)**
- Implements watchdog-based file monitoring with debouncing (5 second default)
- Handles file modification and creation events with timer-based throttling
- Provides `start()`, `stop()`, and status checking methods for service lifecycle
- Already cancels pending timers on shutdown for clean resource cleanup
- Can reuse file watching logic but need to integrate with new import pipeline

**UnifiedCSVImportService (`services/unified_csv_import_service.py`)**
- Contains CSV validation logic in `_detect_file_type()` and `_validate_csv_data()` methods
- Implements `_process_csv_file()` for reading and parsing CSV with pandas
- Has `_import_trades_to_database()` for inserting execution records
- Includes `_rebuild_positions()` integration with EnhancedPositionServiceV2
- Provides `_invalidate_cache_after_import()` for clearing Redis cache entries
- Can extract CSV parsing and validation functions for reuse in new consolidated service

**ExecutionExporter.cs NinjaScript Indicator (`ninjascript/ExecutionExporter.cs`)**
- Generates CSV files with exact format: Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection
- Tracks positions per account independently using dictionary key `{accountName}_{instrumentFullName}` (lines 268-303)
- Provides Entry/Exit hints in E/X column based on quantity flow analysis
- Uses execution IDs from NinjaTrader ExecutionId property for deduplication
- Creates daily files with pattern `NinjaTrader_Executions_YYYYMMDD.csv` and appends throughout day
- Position tracking logic shows correct account isolation that Python import must replicate

**Redis Cache Service (`services/redis_cache_service.py`)**
- Provides Redis connection with 14-day TTL for cached data
- Can store execution ID sets for deduplication tracking
- Supports bulk cache invalidation for instruments and accounts
- Use for tracking processed execution IDs with key pattern `processed_executions:{date}`

**Domain Models (Trade, Position, QuantityFlowAnalyzer)**
- Trade model already has account field and MarketSide enum for Buy/Sell/BuyToCover/SellShort
- Position model supports account-based grouping and status tracking (open/closed)
- QuantityFlowAnalyzer detects position_start, position_modify, position_close, position_reversal events based on quantity changes
- Can leverage these models directly without modifications for account-aware position building

## Out of Scope
- Removing manual CSV import UI from web interface (will be done AFTER testing as separate cleanup task)
- Real-time position updates faster than 30-60 seconds (acceptable performance target)
- Advanced scheduling or time-based import rules beyond simple file watching
- Email or push notifications on import failures (log-based monitoring sufficient)
- Processing CSV files from directories other than `data` folder
- Modifying the NinjaTrader ExecutionExporter.cs indicator code or CSV format
- Supporting non-NinjaTrader CSV formats or alternative data sources
- Multi-threaded or parallel file processing (single-threaded sequential processing sufficient)
- Automatic position rebuilds triggered by execution edits (separate feature in different spec)
- Cross-account position linking or aggregation (future Phase 3 roadmap feature)
