# API Specification

This is the API specification for the spec detailed in @agent-os/specs/2025-11-11-position-dashboard-fix/spec.md

## Endpoints

### GET /api/positions/validate

**Purpose:** Validate all positions and return validation report

**Parameters:**
- `account_id` (optional): Filter by specific account
- `strict` (optional, default: false): If true, only return invalid positions

**Response:**
```json
{
  "total_positions": 1031,
  "valid_positions": 1025,
  "invalid_positions": 6,
  "validation_errors": [
    {
      "position_id": 12345,
      "instrument": "MNQ DEC25",
      "errors": [
        "Open position has exit_time",
        "Average entry price is 0.00"
      ]
    }
  ]
}
```

**Errors:**
- 500: Database error during validation

---

### POST /api/database/cleanup

**Purpose:** Delete all positions and executions for clean re-import

**Parameters:**
- `scope` (required): What to delete ("positions", "executions", or "all")
- `confirm` (required): Must be true to proceed

**Request Body:**
```json
{
  "scope": "all",
  "confirm": true
}
```

**Response:**
```json
{
  "success": true,
  "deleted_positions": 1031,
  "deleted_executions": 7234,
  "message": "Database cleaned successfully. Ready for re-import."
}
```

**Errors:**
- 400: Invalid request parameters or missing confirmation
- 500: Database operation failed

---

### GET /api/statistics/dashboard

**Purpose:** Get accurate dashboard statistics with validation status

**Parameters:**
- `account_id` (optional): Filter by specific account
- `include_validation` (optional, default: false): Include validation metrics

**Response:**
```json
{
  "total_positions": 1031,
  "closed_positions": 1026,
  "open_positions": 5,
  "win_rate": 52.3,
  "total_pnl": -1234.56,
  "avg_executions_per_position": 3.2,
  "validation": {
    "valid_positions": 1025,
    "invalid_positions": 6,
    "last_validation": "2025-11-11T12:00:00Z"
  }
}
```

**Errors:**
- 500: Database error during statistics calculation

---

## Controllers

### PositionValidationController

**Actions:**
- `validate_all_positions()`: Run validation on all positions
- `validate_position(position_id)`: Validate single position
- `get_validation_report()`: Return validation statistics

**Business Logic:**
- Load positions with related executions
- Run validation checks (state consistency, price data, P&L calculations)
- Update validation fields in database
- Return validation report with error details

**Error Handling:**
- Database connection failures: Return 500 with error message
- Invalid position_id: Return 404
- Validation errors: Log but don't fail request

### DatabaseCleanupController

**Actions:**
- `cleanup_positions()`: Delete all positions
- `cleanup_executions()`: Delete all executions
- `cleanup_all()`: Delete all trading data

**Business Logic:**
- Validate confirmation parameter
- Count records before deletion
- Execute DELETE statements based on scope
- Reset auto-increment sequences
- Run VACUUM to reclaim space
- Log deletion operation with counts

**Error Handling:**
- Missing confirmation: Return 400 with error message
- Database connection failures: Return 500
- Deletion failures: Rollback transaction and return 500
