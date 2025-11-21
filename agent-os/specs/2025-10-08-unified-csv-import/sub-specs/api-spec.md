# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-10-08-unified-csv-import/spec.md

## Endpoints

### GET /api/csv/status

**Purpose:** Get current status of the unified CSV import system
**Parameters:** None
**Response:**
```json
{
  "success": true,
  "file_watcher": {
    "running": true,
    "check_interval": 300,
    "watched_directory": "/path/to/data"
  },
  "import_service": {
    "last_import_time": "2025-10-08T14:30:00Z",
    "files_in_queue": 0,
    "total_processed": 142,
    "total_errors": 3
  },
  "archive_directory": "/path/to/archive"
}
```
**Errors:** 500 on service error

### POST /api/csv/process-now

**Purpose:** Manually trigger immediate CSV file processing
**Parameters:** None
**Response:**
```json
{
  "success": true,
  "message": "Processing triggered successfully",
  "files_found": 2,
  "files_processed": 2,
  "errors": []
}
```
**Errors:** 500 on processing error

### GET /api/csv/history

**Purpose:** Get recent CSV processing history
**Parameters:**
- `limit` (optional): Number of entries to return (default: 50, max: 100)
**Response:**
```json
{
  "success": true,
  "history": [
    {
      "filename": "Executions_20251008.csv",
      "format_detected": "NT Grid CSV",
      "processed_at": "2025-10-08T14:30:00Z",
      "status": "success",
      "records_imported": 45,
      "positions_rebuilt": 12,
      "archive_path": "/path/to/archive/Executions_20251008_143000.csv"
    }
  ],
  "total_entries": 142
}
```
**Errors:** 500 on error

## Controllers

### CSVManagementController

**Actions:**
- `get_status()` - Retrieves current system status
- `trigger_processing()` - Forces immediate file processing
- `get_history(limit)` - Returns processing history

**Business Logic:**
- Coordinates with unified import service
- Handles error responses
- Formats status information for API consumers
- Validates request parameters
