# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-28-position-execution-integrity/spec.md

> Created: 2025-09-28
> Version: 1.0.0

## Endpoints

### Validation Endpoints

#### GET `/api/integrity/validate`
Validate all positions with optional filters

**Parameters:**
- `account_id` (optional, string): Filter by specific account
- `instrument` (optional, string): Filter by instrument symbol
- `date_from` (optional, string): Start date for validation (YYYY-MM-DD)
- `date_to` (optional, string): End date for validation (YYYY-MM-DD)
- `page` (optional, integer): Page number for pagination (default: 1)
- `limit` (optional, integer): Items per page (default: 100, max: 1000)
- `severity` (optional, string): Filter by issue severity (low, medium, high, critical)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "validation_id": "val_2025092812345",
    "summary": {
      "total_positions": 1250,
      "validated_positions": 1245,
      "issues_found": 5,
      "severity_breakdown": {
        "critical": 1,
        "high": 2,
        "medium": 2,
        "low": 0
      }
    },
    "issues": [
      {
        "position_id": "pos_123",
        "issue_type": "quantity_mismatch",
        "severity": "critical",
        "description": "Position quantity (100) doesn't match execution total (95)",
        "expected_value": 100,
        "actual_value": 95,
        "execution_ids": ["exec_456", "exec_789"]
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 100,
      "total_pages": 1,
      "total_items": 5
    }
  }
}
```

#### POST `/api/integrity/validate`
Validate specific positions by ID

**Request Body:**
```json
{
  "position_ids": ["pos_123", "pos_456", "pos_789"],
  "validation_options": {
    "check_quantity": true,
    "check_price": true,
    "check_timestamps": true,
    "check_pnl": true
  }
}
```

**Response (200 OK):** Same format as GET endpoint

### Reporting Endpoints

#### GET `/api/integrity/report`
Generate integrity validation reports

**Parameters:**
- `format` (optional, string): Report format (json, csv, pdf) (default: json)
- `account_id` (optional, string): Filter by specific account
- `date_from` (required, string): Start date for report (YYYY-MM-DD)
- `date_to` (required, string): End date for report (YYYY-MM-DD)
- `include_resolved` (optional, boolean): Include resolved issues (default: false)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "report_id": "rep_2025092812345",
    "generated_at": "2025-09-28T12:34:56Z",
    "period": {
      "start_date": "2025-09-01",
      "end_date": "2025-09-28"
    },
    "summary": {
      "total_positions_analyzed": 5000,
      "total_issues_found": 25,
      "issues_by_type": {
        "quantity_mismatch": 10,
        "price_variance": 8,
        "timestamp_inconsistency": 5,
        "pnl_calculation_error": 2
      },
      "resolution_status": {
        "auto_resolved": 15,
        "manual_resolution_required": 8,
        "pending_review": 2
      }
    },
    "detailed_issues": [...],
    "recommendations": [
      "Review execution import process for quantity accuracy",
      "Implement stricter price validation rules"
    ]
  }
}
```

### Repair Endpoints

#### POST `/api/integrity/repair`
Auto-repair integrity issues

**Request Body:**
```json
{
  "repair_options": {
    "auto_repair_safe_issues": true,
    "dry_run": false,
    "position_ids": ["pos_123", "pos_456"],
    "repair_types": ["quantity_mismatch", "price_variance"]
  }
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "data": {
    "job_id": "repair_2025092812345",
    "estimated_duration": "5 minutes",
    "positions_to_repair": 15,
    "status_url": "/api/integrity/repair/status/repair_2025092812345"
  }
}
```

#### POST `/api/integrity/rebuild`
Rebuild positions from executions

**Request Body:**
```json
{
  "rebuild_options": {
    "position_ids": ["pos_123"],
    "account_id": "account_456",
    "instrument": "ES",
    "date_range": {
      "start_date": "2025-09-01",
      "end_date": "2025-09-28"
    },
    "backup_before_rebuild": true
  }
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "data": {
    "job_id": "rebuild_2025092812345",
    "estimated_duration": "10 minutes",
    "positions_to_rebuild": 5,
    "backup_id": "backup_2025092812345",
    "status_url": "/api/integrity/rebuild/status/rebuild_2025092812345"
  }
}
```

### Status Endpoints

#### GET `/api/integrity/status`
Get system integrity status

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "system_health": "healthy",
    "last_validation": "2025-09-28T10:30:00Z",
    "current_issues": {
      "critical": 0,
      "high": 2,
      "medium": 5,
      "low": 10
    },
    "auto_repair_enabled": true,
    "scheduled_validations": {
      "next_run": "2025-09-28T18:00:00Z",
      "frequency": "every_6_hours"
    },
    "active_jobs": [
      {
        "job_id": "repair_2025092812345",
        "type": "repair",
        "status": "running",
        "progress": 65
      }
    ]
  }
}
```

#### GET `/api/integrity/{job_type}/status/{job_id}`
Get status of repair or rebuild job

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "job_id": "repair_2025092812345",
    "type": "repair",
    "status": "completed",
    "progress": 100,
    "started_at": "2025-09-28T12:00:00Z",
    "completed_at": "2025-09-28T12:05:30Z",
    "results": {
      "positions_processed": 15,
      "successful_repairs": 13,
      "failed_repairs": 2,
      "issues_resolved": 13
    },
    "logs": [
      "Started repair process for 15 positions",
      "Successfully repaired quantity mismatch in position pos_123",
      "Failed to repair position pos_456: Manual intervention required"
    ]
  }
}
```

## Controllers

### IntegrityController

**Class:** `IntegrityController`
**Location:** `routes/integrity.py`

**Dependencies:**
- `PositionExecutionIntegrityService`
- `BackgroundJobService`
- `AuthenticationService`
- `AuditService`

**Actions:**

#### `validate_positions()`
- Handles GET `/api/integrity/validate`
- Validates request parameters
- Calls `PositionExecutionIntegrityService.validate_positions()`
- Returns paginated validation results
- Logs validation requests for audit

#### `validate_specific_positions()`
- Handles POST `/api/integrity/validate`
- Validates request body and position IDs
- Calls `PositionExecutionIntegrityService.validate_specific_positions()`
- Returns validation results for specified positions

#### `generate_integrity_report()`
- Handles GET `/api/integrity/report`
- Validates date range parameters
- Calls `PositionExecutionIntegrityService.generate_report()`
- Supports multiple output formats (JSON, CSV, PDF)
- Implements caching for performance

#### `auto_repair_issues()`
- Handles POST `/api/integrity/repair`
- Validates repair options and authorization
- Creates background job for repair process
- Returns job ID for status tracking
- Implements dry-run mode for testing

#### `rebuild_positions()`
- Handles POST `/api/integrity/rebuild`
- Validates rebuild parameters and authorization
- Creates backup before rebuild
- Initiates background rebuild job
- Returns job tracking information

#### `get_system_status()`
- Handles GET `/api/integrity/status`
- Returns current system integrity status
- Shows active jobs and schedules
- Provides health metrics

#### `get_job_status()`
- Handles GET `/api/integrity/{job_type}/status/{job_id}`
- Returns status and progress of background jobs
- Provides detailed logs and results
- Supports real-time updates via WebSocket

**Error Handling:**
- Input validation with detailed error messages
- Database connection error handling
- Background job failure management
- Rate limiting for resource-intensive operations
- Graceful degradation for partial system failures

**Background Job Management:**
- Uses Redis-backed job queue
- Implements job progress tracking
- Provides job cancellation capability
- Automatic cleanup of completed jobs
- Job result persistence for audit trail

## Request/Response Formats

**Standard Error Response (4xx/5xx):**
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Position validation failed due to missing executions",
    "details": {
      "position_id": "pos_123",
      "missing_executions": ["exec_456"]
    },
    "timestamp": "2025-09-28T12:34:56Z"
  }
}
```

**Pagination Format:**
```json
{
  "pagination": {
    "page": 1,
    "limit": 100,
    "total_pages": 5,
    "total_items": 487,
    "has_next": true,
    "has_previous": false
  }
}
```

**Filter Parameters:**
- Support for multiple filter combinations
- Case-insensitive string matching
- Date range validation
- Enum validation for severity levels
- Default values for optional parameters

**Progress Tracking:**
```json
{
  "progress": {
    "current": 65,
    "total": 100,
    "status": "processing",
    "current_task": "Validating position pos_123",
    "estimated_completion": "2025-09-28T12:40:00Z"
  }
}
```

## Authentication & Authorization

**Authentication Methods:**
- Session-based authentication for web interface
- API key authentication for programmatic access
- JWT tokens for service-to-service communication

**Authorization Levels:**

**Admin Access (Required for):**
- POST `/api/integrity/repair`
- POST `/api/integrity/rebuild`
- System configuration changes
- Bulk operations

**Read-Only Access (Allowed for):**
- GET `/api/integrity/validate`
- GET `/api/integrity/report`
- GET `/api/integrity/status`
- Job status monitoring

**Programmatic Access:**
- API key required for all endpoints
- Rate limiting: 1000 requests/hour per key
- Scope-based permissions per API key
- Audit logging of all API key usage

**Security Headers:**
- CORS configuration for web clients
- Rate limiting per IP address
- Request size limits for file uploads
- SQL injection protection
- XSS protection for JSON responses

**Error Codes:**
- `401 Unauthorized`: Invalid or missing authentication
- `403 Forbidden`: Insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: System error
- `503 Service Unavailable`: System maintenance