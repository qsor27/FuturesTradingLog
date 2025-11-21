# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-11-unified-csv-import/spec.md

> Created: 2025-09-11
> Version: 1.0.0

## Endpoints

### New Endpoints

#### POST /api/csv/reprocess
**Purpose:** Manual re-processing of CSV files
**Request Body:**
```json
{
  "files": ["filename1.csv", "filename2.csv"], // optional, if empty processes all
  "date_range": {
    "start": "2025-09-01", // optional
    "end": "2025-09-11"    // optional
  },
  "force_rebuild": true // optional, default false
}
```
**Response:**
```json
{
  "status": "success",
  "job_id": "reprocess_20250911_123456",
  "message": "Re-processing started for 2 files"
}
```

#### GET /api/csv/reprocess/status/{job_id}
**Purpose:** Get re-processing job status
**Response:**
```json
{
  "job_id": "reprocess_20250911_123456",
  "status": "processing", // pending, processing, completed, failed
  "progress": {
    "total_files": 2,
    "processed_files": 1,
    "current_file": "filename2.csv"
  },
  "errors": [],
  "completed_at": null
}
```

#### GET /api/csv/files
**Purpose:** List available CSV files in /Data directory
**Response:**
```json
{
  "files": [
    {
      "filename": "ES_20250911.csv",
      "size": 1024576,
      "modified": "2025-09-11T10:30:00Z",
      "last_processed": "2025-09-11T10:31:00Z"
    }
  ]
}
```

### Deprecated Endpoints (Return 410 Gone)

#### POST /upload
**Response:**
```json
{
  "error": "This endpoint has been deprecated. Use /api/csv/reprocess for manual CSV processing.",
  "status": 410,
  "migration_guide": "https://docs.example.com/csv-import-migration"
}
```

#### POST /batch-import-csv
**Response:**
```json
{
  "error": "This endpoint has been deprecated. CSV files are now automatically imported from the /Data directory.",
  "status": 410,
  "migration_guide": "https://docs.example.com/csv-import-migration"
}
```

#### POST /reimport-csv
**Response:**
```json
{
  "error": "This endpoint has been deprecated. Use /api/csv/reprocess for re-importing CSV files.",
  "status": 410,
  "migration_guide": "https://docs.example.com/csv-import-migration"
}
```

#### POST /process-nt-executions
**Response:**
```json
{
  "error": "This endpoint has been deprecated. NinjaTrader executions are automatically processed from CSV files.",
  "status": 410,
  "migration_guide": "https://docs.example.com/csv-import-migration"
}
```

#### GET /csv-manager
**Response:**
```json
{
  "error": "This interface has been deprecated. Use the new unified CSV management interface.",
  "status": 410,
  "migration_guide": "https://docs.example.com/csv-import-migration"
}
```

## Controllers

### New Controllers

#### `UnifiedCSVController`
- Handles all new CSV-related endpoints
- Manages job queuing for re-processing operations
- Provides file listing and status monitoring

### Modified Controllers

#### `FileWatcherController` (Enhanced)
- Enhanced to use unified import service
- Queue-based processing for automatic imports
- Improved error handling and logging

### Removed Controllers

#### `UploadController`
- Remove file upload handling logic
- Replace with deprecation responses

#### `BatchImportController`
- Remove batch import functionality  
- Replace with deprecation responses

#### `CSVManagerController`
- Remove CSV manager interface
- Replace with deprecation responses