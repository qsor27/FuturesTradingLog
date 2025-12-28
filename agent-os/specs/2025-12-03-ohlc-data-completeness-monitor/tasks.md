# Spec Tasks

## Tasks

- [x] 1. Create DataCompletenessService core
  - [x] 1.1 Write tests for DataCompletenessService methods
  - [x] 1.2 Create `services/data_completeness_service.py` with class skeleton
  - [x] 1.3 Implement `get_completeness_matrix()` with batch SQL query
  - [x] 1.4 Implement `get_gap_details(instrument, timeframe)` method
  - [x] 1.5 Add Redis caching (5-minute TTL) for matrix results
  - [x] 1.6 Verify all tests pass (20/20 tests passing)

- [x] 2. Implement sync health tracking
  - [x] 2.1 Write tests for sync history storage and retrieval (8 tests)
  - [x] 2.2 Add `record_sync_result()` method to DataCompletenessService
  - [x] 2.3 Implement `get_sync_health_history(days)` method
  - [x] 2.4 Integrate sync recording into `daily_import_scheduler.py` after each sync
  - [x] 2.5 Verify all tests pass (28/28 tests passing)

- [x] 3. Create API endpoints
  - [x] 3.1 Write tests for all 4 API endpoints (14 tests in test_data_completeness_api.py)
  - [x] 3.2 Add `/api/monitoring/completeness-matrix` GET endpoint
  - [x] 3.3 Add `/api/monitoring/gap-details/{instrument}/{timeframe}` GET endpoint
  - [x] 3.4 Add `/api/monitoring/repair-gap` POST endpoint
  - [x] 3.5 Add `/api/monitoring/sync-health` GET endpoint
  - [x] 3.6 Verify all tests pass (42/42 tests passing)

- [x] 4. Build dashboard UI
  - [x] 4.1 Create `templates/monitoring/data_completeness.html` with Bootstrap 5 layout
  - [x] 4.2 Implement completeness matrix table with color-coded cells
  - [x] 4.3 Add summary header with health score and sync timestamps
  - [x] 4.4 Create gap detail modal with repair button
  - [x] 4.5 Implement sync health timeline component
  - [x] 4.6 Add JavaScript for auto-refresh (60s polling)
  - [x] 4.7 Add toast notifications for repair operations
  - [x] 4.8 Verify UI renders correctly in browser

- [x] 5. Integration and testing
  - [x] 5.1 Write integration tests for full dashboard flow (included in API tests)
  - [x] 5.2 Add route `/monitoring/data-completeness` to `routes/data_monitoring.py`
  - [x] 5.3 Add navigation link to existing monitoring dashboard
  - [x] 5.4 Test one-click repair endpoint (tested via API tests)
  - [x] 5.5 Verify all tests pass (42/42 tests passing)
