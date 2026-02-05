# Spec Tasks

## Tasks

- [ ] 1. Database Schema Implementation
  - [ ] 1.1 Write tests for import_execution_logs table creation and indexes
  - [ ] 1.2 Create migration for import_execution_logs table with all columns and constraints
  - [ ] 1.3 Write tests for import_execution_row_logs table creation and indexes
  - [ ] 1.4 Create migration for import_execution_row_logs table with foreign keys
  - [ ] 1.5 Write tests for trades table alteration (import_row_log_id column)
  - [ ] 1.6 Create migration to add import_row_log_id column to trades table
  - [ ] 1.7 Run all migrations and verify schema creation
  - [ ] 1.8 Verify all tests pass

- [ ] 2. Import Logging Service Layer
  - [ ] 2.1 Write tests for ImportLogsService class with row-level logging
  - [ ] 2.2 Create models/import_execution.py with ImportExecutionLog and ImportRowLog classes
  - [ ] 2.3 Create services/import_logs_service.py with log_import_execution(), log_row_result(), and finalize_import() methods
  - [ ] 2.4 Add logging hooks to unified_csv_import_service.py to capture row-by-row processing
  - [ ] 2.5 Add logging hooks to ninjatrader_import_service.py for row-level tracking
  - [ ] 2.6 Test import execution with new logging to verify database writes
  - [ ] 2.7 Verify all tests pass

- [ ] 3. API Endpoints Implementation
  - [ ] 3.1 Write tests for all import logs API endpoints
  - [ ] 3.2 Create routes/import_logs.py blueprint with /import-logs prefix
  - [ ] 3.3 Implement GET /api/import-logs/list endpoint with filtering and pagination
  - [ ] 3.4 Implement GET /api/import-logs/detail/<import_batch_id> endpoint
  - [ ] 3.5 Implement POST /api/import-logs/retry/<import_batch_id> endpoint
  - [ ] 3.6 Implement POST /api/import-logs/rollback/<import_batch_id> endpoint
  - [ ] 3.7 Implement GET /api/import-logs/download/<import_batch_id> endpoint
  - [ ] 3.8 Implement GET /api/import-logs/affected-trades/<import_batch_id> endpoint
  - [ ] 3.9 Register blueprint in app.py
  - [ ] 3.10 Verify all tests pass

- [ ] 4. Frontend UI Implementation
  - [ ] 4.1 Write tests for import logs page rendering and interactions
  - [ ] 4.2 Create templates/import_logs.html with table structure using existing components
  - [ ] 4.3 Implement expandable row JavaScript for detail view with row logs
  - [ ] 4.4 Add status badge rendering with success/warning/error icons
  - [ ] 4.5 Implement red background highlighting for failed imports using .negative CSS class
  - [ ] 4.6 Create filter controls for status, date range, account with client-side JavaScript
  - [ ] 4.7 Implement action buttons (Retry, Rollback, View Trades, Download) with AJAX calls
  - [ ] 4.8 Add confirmation modal for rollback action
  - [ ] 4.9 Implement pagination controls using existing pagination component
  - [ ] 4.10 Update navigation in templates/base.html to replace CSV Manager with Import Logs
  - [ ] 4.11 Verify all tests pass

- [ ] 5. Integration and End-to-End Testing
  - [ ] 5.1 Write end-to-end tests for complete import flow with logging
  - [ ] 5.2 Test import execution creates proper log entries with row-level details
  - [ ] 5.3 Test failed import creates error logs with validation messages
  - [ ] 5.4 Test retry operation moves file and triggers reprocessing
  - [ ] 5.5 Test rollback operation deletes trades and invalidates cache
  - [ ] 5.6 Test view affected trades filters by import_batch_id
  - [ ] 5.7 Test download logs generates JSON and text formats correctly
  - [ ] 5.8 Test expandable rows load row logs via AJAX
  - [ ] 5.9 Test filtering by status, date, account works correctly
  - [ ] 5.10 Verify all tests pass
