# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2026-01-22-import-logging-page/spec.md

## Page Routes

### GET /import-logs

**Purpose:** Render the main import logs page with import execution history table

**Parameters:** None (filtering handled client-side after page load)

**Response:** HTML page rendered from `templates/import_logs.html`

**Controller:** `routes/import_logs.py::import_logs_page()`

**Template Variables:**
- `page_title`: "Import Logs"
- `imports`: Initial page of import executions (25 most recent)
- `total_count`: Total number of import executions

## API Endpoints

### GET /api/import-logs/list

**Purpose:** Retrieve paginated list of import executions with filtering

**Parameters:**
- `page` (int, optional, default=1): Page number
- `per_page` (int, optional, default=25): Results per page (10/25/50/100)
- `status` (string, optional): Filter by status ('success', 'partial', 'failed')
- `account` (string, optional): Filter by affected account name
- `start_date` (ISO date, optional): Filter imports after this date
- `end_date` (ISO date, optional): Filter imports before this date
- `search` (string, optional): Search in file_name
- `sort_by` (string, optional, default='import_time'): Sort column
- `sort_order` (string, optional, default='desc'): Sort direction ('asc'/'desc')

**Response:**
```json
{
  "success": true,
  "imports": [
    {
      "id": 123,
      "import_batch_id": "550e8400-e29b-41d4-a716-446655440000",
      "file_name": "executions_2026-01-22.csv",
      "import_time": "2026-01-22T10:30:45",
      "status": "partial",
      "total_rows": 150,
      "success_rows": 145,
      "failed_rows": 5,
      "skipped_rows": 0,
      "processing_time_ms": 1250,
      "affected_accounts": ["Account1", "Account2"],
      "error_summary": "5 rows failed validation"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 87,
    "pages": 4
  }
}
```

**Errors:**
- 400: Invalid parameters (invalid page number, per_page out of range)
- 500: Database error

---

### GET /api/import-logs/detail/<import_batch_id>

**Purpose:** Retrieve detailed row-by-row logs for a specific import execution

**Parameters:**
- `import_batch_id` (path parameter, required): UUID of the import batch

**Response:**
```json
{
  "success": true,
  "import_summary": {
    "id": 123,
    "import_batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_name": "executions_2026-01-22.csv",
    "file_path": "C:\\data\\executions_2026-01-22.csv",
    "import_time": "2026-01-22T10:30:45",
    "status": "partial",
    "total_rows": 150,
    "success_rows": 145,
    "failed_rows": 5,
    "processing_time_ms": 1250,
    "affected_accounts": ["Account1", "Account2"],
    "error_summary": "5 rows failed validation"
  },
  "row_logs": [
    {
      "id": 5001,
      "row_number": 1,
      "status": "success",
      "created_trade_id": 9876,
      "raw_row_data": {
        "Instrument": "NQ",
        "Side": "Buy",
        "Quantity": "2",
        "Price": "16500.25",
        "Time": "2026-01-22 09:30:00"
      }
    },
    {
      "id": 5002,
      "row_number": 2,
      "status": "failed",
      "error_message": "Invalid timestamp format",
      "error_category": "parsing_error",
      "validation_errors": [
        {
          "field": "entry_time",
          "error": "Could not parse '2026-01-22T09:30' as datetime"
        }
      ],
      "raw_row_data": {
        "Instrument": "ES",
        "Side": "Sell",
        "Quantity": "1",
        "Price": "4800.50",
        "Time": "2026-01-22T09:30"
      }
    }
  ]
}
```

**Errors:**
- 404: Import batch not found
- 500: Database error

---

### POST /api/import-logs/retry/<import_batch_id>

**Purpose:** Retry processing a failed or partially successful import

**Parameters:**
- `import_batch_id` (path parameter, required): UUID of the import batch to retry

**Request Body:** None

**Response:**
```json
{
  "success": true,
  "message": "Import retry initiated for executions_2026-01-22.csv",
  "file_moved": true,
  "new_batch_id": "660e8400-e29b-41d4-a716-446655440111"
}
```

**Errors:**
- 404: Import batch not found or file no longer exists
- 400: Import was successful (retry not allowed for fully successful imports)
- 500: File operation error or processing error

**Controller Logic:**
1. Verify import batch exists and status is 'failed' or 'partial'
2. Locate source file (check error folder, then archive folder)
3. Move file from error/archive folder back to data folder
4. Trigger unified_csv_import_service.process_new_files()
5. Return new batch ID for tracking the retry

---

### POST /api/import-logs/rollback/<import_batch_id>

**Purpose:** Rollback an import by deleting all associated trades and preparing for re-import

**Parameters:**
- `import_batch_id` (path parameter, required): UUID of the import batch to rollback

**Request Body:**
```json
{
  "confirm": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Import rolled back successfully",
  "trades_deleted": 145,
  "file_moved": true,
  "file_path": "C:\\data\\executions_2026-01-22.csv"
}
```

**Errors:**
- 404: Import batch not found
- 400: Missing or invalid confirmation
- 500: Database error or file operation error

**Controller Logic:**
1. Verify import batch exists
2. Require confirmation=true in request body
3. Begin database transaction
4. Delete all trades where import_batch_id matches
5. Update import_execution_logs status to 'rolled_back'
6. Move file from archive back to data folder (if archived)
7. Invalidate position cache for affected accounts
8. Trigger position rebuild for affected accounts
9. Commit transaction
10. Return count of deleted trades

---

### GET /api/import-logs/download/<import_batch_id>

**Purpose:** Download detailed execution logs as a text or JSON file

**Parameters:**
- `import_batch_id` (path parameter, required): UUID of the import batch
- `format` (query parameter, optional, default='json'): Output format ('json', 'text')

**Response:** File download (application/json or text/plain)

**JSON Format Example:**
```json
{
  "import_batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "executions_2026-01-22.csv",
  "import_time": "2026-01-22T10:30:45",
  "status": "partial",
  "summary": {
    "total_rows": 150,
    "success_rows": 145,
    "failed_rows": 5,
    "processing_time_ms": 1250
  },
  "row_logs": [...]
}
```

**Text Format Example:**
```
Import Execution Log
====================
Batch ID: 550e8400-e29b-41d4-a716-446655440000
File: executions_2026-01-22.csv
Time: 2026-01-22 10:30:45
Status: PARTIAL

Summary:
  Total Rows: 150
  Success: 145
  Failed: 5
  Processing Time: 1250ms

Row-by-Row Results:
-------------------
Row 1: SUCCESS - Created trade #9876
Row 2: FAILED - Invalid timestamp format
  Error: Could not parse '2026-01-22T09:30' as datetime
  Raw Data: {Instrument: ES, Side: Sell, ...}
...
```

**Errors:**
- 404: Import batch not found
- 400: Invalid format parameter
- 500: File generation error

---

### GET /api/import-logs/affected-trades/<import_batch_id>

**Purpose:** Retrieve list of trades created by a specific import batch

**Parameters:**
- `import_batch_id` (path parameter, required): UUID of the import batch

**Response:**
```json
{
  "success": true,
  "import_batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "executions_2026-01-22.csv",
  "trades": [
    {
      "id": 9876,
      "instrument": "NQ",
      "side_of_market": "Buy",
      "quantity": 2,
      "entry_price": 16500.25,
      "entry_time": "2026-01-22 09:30:00",
      "dollars_gain_loss": 250.50,
      "account": "Account1"
    }
  ],
  "count": 145
}
```

**Errors:**
- 404: Import batch not found
- 500: Database error

**Controller Logic:**
1. Query trades table WHERE import_batch_id = ?
2. Return trade records with essential fields
3. Include count for summary

---

### GET /api/import-logs/stats

**Purpose:** Get summary statistics for import logs dashboard (optional enhancement)

**Parameters:** None

**Response:**
```json
{
  "success": true,
  "total_imports": 87,
  "successful_imports": 72,
  "partial_imports": 10,
  "failed_imports": 5,
  "total_rows_processed": 15430,
  "average_processing_time_ms": 950,
  "last_import_time": "2026-01-22T10:30:45"
}
```

**Errors:**
- 500: Database error

---

## Error Response Format

All endpoints return errors in consistent format:

```json
{
  "success": false,
  "error": "Human-readable error message",
  "error_code": "IMPORT_NOT_FOUND",
  "details": {}
}
```

## Integration Points

### With Unified CSV Import Service

- `unified_csv_import_service.process_file()` modified to call `ImportLogsService.log_import_execution()`
- After each row processed, call `ImportLogsService.log_row_result()`
- On import completion, call `ImportLogsService.finalize_import()`

### With NinjaTrader Import Service

- Similar logging hooks added to `ninjatrader_import_service._process_file()`
- Maintains existing Redis deduplication while adding database logging

### With Cache Manager

- After retry: `cache_manager.invalidate_positions_cache(affected_accounts)`
- After rollback: `cache_manager.invalidate_all_caches()`

### With Position Service

- After rollback: `EnhancedPositionServiceV2.rebuild_positions(accounts, instruments)`
