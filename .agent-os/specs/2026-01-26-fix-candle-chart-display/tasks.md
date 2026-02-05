# Spec Tasks

## Tasks

- [x] 1. Fix timeframe validation and default value
  - [x] 1.1 Add VALID_TIMEFRAMES constant to ChartSettingsAPI.js
  - [x] 1.2 Validate stored timeframe in getSettings() method
  - [x] 1.3 Validate timeframe in PriceChart.js constructor
  - [x] 1.4 Fix dropdown initial value in price_chart.html template
  - [x] 1.5 Verify chart loads with valid default timeframe

- [x] 2. Implement continuous contract fallback in chart-data API
  - [x] 2.1 Add/verify get_root_symbol() function in instrument_mapper.py
  - [x] 2.2 Modify get_chart_data() in chart_data.py to try specific contract first
  - [x] 2.3 Add fallback logic to query continuous contract when specific fails
  - [x] 2.4 Add is_continuous_fallback and actual_instrument to response metadata
  - [x] 2.5 Test API returns continuous contract data when specific unavailable

- [x] 3. Update available-timeframes API for consistency
  - [x] 3.1 Add date range filtering to available-timeframes endpoint
  - [x] 3.2 Include fallback_info when using continuous contract
  - [x] 3.3 Ensure counts reflect actual available data for date range
  - [x] 3.4 Test endpoint returns consistent data with chart-data endpoint

- [x] 4. Fix timeframe switching during loading state
  - [x] 4.1 Add AbortController to loadData() for cancellable requests
  - [x] 4.2 Modify updateTimeframe() to cancel current load and start new one
  - [x] 4.3 Update loading state management to handle cancellation
  - [x] 4.4 Test rapid timeframe switching doesn't cause errors or stuck states

- [x] 5. Add UI feedback for continuous contract fallback
  - [x] 5.1 Add showContinuousFallbackWarning() method to PriceChart.js
  - [x] 5.2 Call warning method when API returns is_continuous_fallback: true
  - [x] 5.3 Style the warning banner consistently with existing alerts
  - [x] 5.4 Make warning dismissible
  - [x] 5.5 Test warning displays correctly and can be dismissed

- [x] 6. Implement position-triggered data fetching
  - [x] 6.1 Create fetch_position_ohlc_data Celery task in tasks/gap_filling.py
  - [x] 6.2 Add on_position_imported hook to trigger data fetch after import
  - [x] 6.3 Implement smart gap detection (only fetch data we don't have)
  - [x] 6.4 Add rate limiting and quota tracking to prevent API abuse
  - [x] 6.5 Test importing a new position triggers OHLC fetch

- [x] 7. Add Celery workers to Docker stack
  - [x] 7.1 Add celery-worker service to docker-compose.yml
  - [x] 7.2 Add celery-beat service to docker-compose.yml
  - [x] 7.3 Update Celery beat schedule with market hours awareness
  - [x] 7.4 Add health checks for Celery services
  - [x] 7.5 Test Docker stack starts all services correctly

- [x] 8. Add data freshness monitoring
  - [x] 8.1 Create /api/v1/health/data-freshness endpoint
  - [x] 8.2 Track API quota usage (daily limit: 2000 calls)
  - [x] 8.3 Add staleness detection for instruments
  - [x] 8.4 Test health endpoint reports accurate status

- [x] 9. End-to-end testing and verification (partial - Docker image rebuild required)
  - [ ] 9.1 Test position 252 (requires continuous contract fallback) - BLOCKED: Docker image rebuild needed
  - [ ] 9.2 Test position with specific contract data available - BLOCKED: Docker image rebuild needed
  - [ ] 9.3 Test all timeframe switches work without getting stuck - BLOCKED: Docker image rebuild needed
  - [ ] 9.4 Test with fresh browser (no cached settings) to verify defaults - BLOCKED: Docker image rebuild needed
  - [ ] 9.5 Verify execution arrows display correctly on chart - BLOCKED: Docker image rebuild needed
  - [ ] 9.6 Test importing new position fetches OHLC data within 2 minutes - BLOCKED: Docker image rebuild needed
  - [x] 9.7 Verify Celery workers infrastructure operational
