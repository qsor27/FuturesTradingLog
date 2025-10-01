# Position-Execution Integrity Validation - Phase 2 Continuation Context

## Current Status

**Completed Tasks:**
- ✅ Phase 1 (Foundation): Tasks 1.1-1.5
  - Domain models (ValidationResult, IntegrityIssue)
  - PositionExecutionIntegrityValidator
  - Position model extensions with integrity fields
  - Database migrations (validation tables)
  - ValidationRepository

- ✅ Task 2.1: Integrate Validator with PositionBuilder
  - Added optional validation to PositionBuilder constructor
  - Backward compatible integration
  - 7 integration tests passing

- ✅ Task 2.2: PositionExecutionIntegrityService
  - Application service with 15 tests passing
  - Methods for validation, issue management, statistics

- ✅ Task 2.3: REST API Endpoints
  - 9 endpoints in routes/validation.py
  - 16 API tests passing
  - Full CRUD operations for validation

**Remaining Phase 2 Tasks:**
- ⏳ Task 2.4: Add Automated Repair Capabilities for Common Issues
- ⏳ Task 2.5: Implement Background Validation Job Scheduling

## Key Files Created/Modified

### Domain Models
- `domain/validation_result.py` - ValidationResult dataclass with status tracking
- `domain/integrity_issue.py` - IntegrityIssue dataclass with 8 issue types
- `domain/models/position.py` - Added last_validated_at, validation_status, integrity_score
- `domain/models/execution.py` - Existing execution model

### Domain Services
- `domain/services/position_execution_integrity_validator.py` - Core validation logic
  - Completeness checks
  - Data consistency checks
  - Timestamp consistency checks
  - Methods: validate_position(), validate_positions_batch(), detect_orphaned_executions()

- `domain/services/position_builder.py` - Modified to support optional validation
  - Added enable_validation parameter
  - Added _validate_positions() method
  - Maintains backward compatibility

### Repositories
- `repositories/validation_repository.py` - Persistence for validation results and issues
  - save_validation_result(), save_integrity_issue(), save_validation_with_issues()
  - get_validation_result(), get_integrity_issues()
  - update_issue_resolution(), get_validation_statistics()

### Application Services
- `services/position_execution_integrity_service.py` - Orchestration layer
  - validate_position(), validate_positions_batch()
  - get_open_issues(), get_critical_issues()
  - resolve_issue(), ignore_issue()
  - get_validation_statistics(), get_position_integrity_score()

### API Routes
- `routes/validation.py` - REST API endpoints
  - POST /api/validation/positions/{id}
  - POST /api/validation/batch
  - GET /api/validation/results/{id}
  - GET /api/validation/issues
  - POST /api/validation/issues/{id}/resolve
  - POST /api/validation/issues/{id}/ignore
  - GET /api/validation/statistics
  - GET /api/validation/positions/{id}/score

### Database Migrations
- `scripts/migrations/001_add_position_integrity_fields.py`
- `scripts/migrations/002_create_validation_tables.py`

### Tests (All Passing)
- `tests/test_validation_models.py` - 29 tests
- `tests/test_position_execution_integrity_validator.py` - 14 tests
- `tests/test_validation_repository.py` - 12 tests
- `tests/test_position_execution_integrity_service.py` - 15 tests
- `tests/test_validation_api.py` - 16 tests
- `tests/test_position_builder_validation_integration.py` - 7 tests

**Total: 93 passing tests**

## Task 2.4: Automated Repair Capabilities

**Goal:** Add automated repair for common integrity issues

**Requirements from spec:**
- Repair missing execution data from related records
- Reconcile quantity mismatches with FIFO recalculation
- Fix timestamp anomalies where possible
- Automated vs manual repair decision tree
- Repair audit logging
- Dry-run mode for repair operations

**Estimated Time:** 8 hours

**Suggested Approach:**
1. Create domain service: `domain/services/integrity_repair_service.py`
   - Methods for each repair type
   - Dry-run support
   - Repair result tracking

2. Extend IntegrityIssue with repair metadata:
   - repair_attempted, repair_method, repair_details

3. Add repair methods to PositionExecutionIntegrityService:
   - repair_issue(), attempt_auto_repair(), get_repairable_issues()

4. Create repair API endpoints:
   - POST /api/validation/issues/{id}/repair
   - POST /api/validation/positions/{id}/auto-repair

5. Add comprehensive tests

## Task 2.5: Background Validation Job Scheduling

**Goal:** Implement scheduled validation jobs

**Requirements from spec:**
- Celery task for background validation
- Configurable validation frequency
- Failed validation notification system
- Validation scheduling UI/API
- Performance monitoring

**Estimated Time:** 6 hours

**Suggested Approach:**
1. Create Celery task: `tasks/validation_tasks.py`
   - validate_all_positions_task()
   - validate_position_task()

2. Add scheduler configuration
3. Create notification system for failures
4. Add API endpoints for job management
5. Add monitoring/logging

## Database Schema

### validation_results table:
```sql
CREATE TABLE validation_results (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    issue_count INTEGER DEFAULT 0,
    validation_type TEXT DEFAULT 'full',
    details TEXT,
    completed_at TEXT,
    error_message TEXT
)
```

### integrity_issues table:
```sql
CREATE TABLE integrity_issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_id INTEGER NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    resolution_status TEXT DEFAULT 'open',
    position_id INTEGER,
    execution_id INTEGER,
    detected_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_method TEXT,
    resolution_details TEXT,
    metadata TEXT
)
```

## Issue Types

From `domain/integrity_issue.py`:
- MISSING_EXECUTION
- ORPHANED_EXECUTION
- PRICE_MISMATCH
- QUANTITY_MISMATCH
- TIMESTAMP_ANOMALY
- INCOMPLETE_DATA
- DUPLICATE_EXECUTION
- POSITION_WITHOUT_EXECUTIONS

## Issue Severities

- CRITICAL - Data integrity violation
- HIGH - Significant discrepancy
- MEDIUM - Notable inconsistency
- LOW - Minor issue
- INFO - Informational

## Architecture Pattern

Following Domain-Driven Design:
1. Domain models - Pure data classes with validation
2. Domain services - Business logic
3. Application services - Orchestration
4. Repositories - Data persistence
5. API routes - HTTP interface

## Key Configuration

Database path: Use `config.db_path` from config module
Enable validation in PositionBuilder: Set `enable_validation=True`

## Next Steps

1. Start with Task 2.4 (Automated Repair)
2. Create IntegrityRepairService domain service
3. Add repair methods for common issue types
4. Integrate with existing service layer
5. Add API endpoints and tests
6. Move to Task 2.5 (Background Jobs)