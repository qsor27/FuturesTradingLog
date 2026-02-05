# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2026-01-22-import-logging-page/spec.md

> Created: 2026-01-22
> Version: 1.0.0

## Technical Requirements

### Frontend Requirements

- **Replace CSV Manager Route**: Update navigation in `templates/base.html` to point to new Import Logs page instead of `/unified-csv-manager`
- **Import Logs Template**: Create `templates/import_logs.html` using existing dark theme patterns from base.html
- **Component Reuse**: Leverage existing table component (`templates/components/table.html`) with sortable columns, pagination, and row selection
- **Status Badge Component**: Reuse stat card patterns for status indicators (success/warning/error) with icons
- **Expandable Row Pattern**: Implement JavaScript accordion pattern for expanding import detail rows (similar to existing chart collapsing)
- **Color-Coded Rows**: Apply `.positive` (green) and `.negative` (red) CSS classes for success/failure highlighting
- **Modal for Confirmations**: Reuse existing modal patterns for rollback confirmations and error log viewing
- **Client-Side Filtering**: JavaScript filter controls for status, date range, account (similar to existing trade filters)
- **AJAX Actions**: Fetch API calls for retry, rollback, and detail expansion without page reload

### Backend Requirements

- **New Blueprint**: Create `routes/import_logs.py` with blueprint prefix `/import-logs`
- **Database Service**: Extend `services/unified_csv_import_service.py` to write detailed logs to new `import_execution_logs` table
- **Log Capture During Import**: Modify import processing to capture row-by-row results (success/failure/skip) with error messages
- **Import Execution Model**: Create data model in `models/import_execution.py` for structured log data
- **Query Optimization**: Index on import_batch_id, status, import_time for fast filtering and retrieval
- **API Endpoints**: RESTful endpoints for list, detail, retry, rollback, download operations
- **File Management**: Reuse existing error folder patterns for moving files between data/error/archive directories
- **Cache Invalidation**: Trigger cache invalidation after retry/rollback operations (reuse existing cache_manager patterns)

### Data Capture Requirements

- **Per-Import Metadata**: Capture file_name, file_hash, import_batch_id, import_time, status (success/partial/failed), total_rows, success_rows, failed_rows, skipped_rows, processing_time_ms, affected_accounts (JSON array)
- **Per-Row Processing Logs**: Capture row_number, status (success/failed/skipped), error_message, raw_row_data (JSON), validation_errors (JSON array), created_trade_id (foreign key if successful)
- **Error Categories**: Classify errors as validation_error, parsing_error, duplicate_error, database_error, business_logic_error
- **Validation Details**: Store specific validation failures (missing_columns, invalid_timestamp, invalid_quantity, commission_parse_error)
- **Performance Metrics**: Capture start_time, end_time, rows_per_second for import performance tracking

### Integration Requirements

- **Unified CSV Import Service**: Extend to write structured logs instead of only file-based logging
- **NinjaTrader Import Service**: Add logging hooks to capture row-level processing
- **Existing Log Files**: Continue writing to `csv_import.log` and `import.log` for backward compatibility
- **Import History Table**: Link to existing `import_history` table via `import_batch_id` foreign key
- **Trades Table**: Link `import_execution_row_logs.created_trade_id` to `trades.id` for trace-back capability
- **Position Rebuilding**: Trigger position rebuild after retry/rollback operations using existing EnhancedPositionServiceV2

### UI/UX Requirements

- **Responsive Table**: Support desktop-first design with horizontal scrolling on smaller screens
- **Pagination**: Default 25 rows per page with options for 10/50/100
- **Default Sort**: Most recent imports first (import_time DESC)
- **Expandable Details**: Click row to expand showing tabbed interface: Row Logs | Validation Errors | Performance Metrics
- **Retry Button**: Only visible for failed/partial imports, disabled if file no longer exists
- **Rollback Button**: Only visible for successful/partial imports, requires confirmation modal
- **View Trades Button**: Always visible, opens trades page filtered by import_batch_id
- **Download Logs Button**: Downloads structured JSON or formatted text file with full execution details
- **Status Badges**: Green checkmark (success), yellow warning (partial), red X (failed)
- **Error Count Display**: Show "X errors" badge next to failed imports with count
- **Processing Time**: Display as "Xms" or "Xs" for quick performance assessment
- **Accounts Affected**: Display as comma-separated list or badge count

### Performance Requirements

- **Lazy Loading**: Only load row-level logs when user expands detail row (not on initial page load)
- **Pagination**: Limit initial query to 25 imports, load more on demand
- **Index Optimization**: Ensure queries use indexes on status, import_time, import_batch_id
- **Log Retention**: Consider archiving row-level logs older than 90 days to separate table
- **Response Time**: Import list page should load in <500ms, detail expansion in <200ms
