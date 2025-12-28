# Spec Tasks

## Tasks

- [x] 1. Extend Statistics Calculation Service
  - [x] 1.1 Write tests for new daily statistics methods (position count, long/short breakdown, win rates by direction)
  - [x] 1.2 Implement `get_daily_enhanced_statistics()` method in StandardizedStatisticsCalculator
  - [x] 1.3 Write tests for weekly statistics methods (day-of-week breakdown, instrument breakdown)
  - [x] 1.4 Implement `get_weekly_enhanced_statistics()` method
  - [x] 1.5 Write tests for monthly statistics methods (week-over-week, previous month comparison)
  - [x] 1.6 Implement `get_monthly_enhanced_statistics()` method
  - [x] 1.7 Verify all calculation tests pass

- [x] 2. Create API Endpoints
  - [x] 2.1 Write tests for `/api/statistics/daily` endpoint
  - [x] 2.2 Implement daily statistics API endpoint
  - [x] 2.3 Write tests for `/api/statistics/weekly` endpoint
  - [x] 2.4 Implement weekly statistics API endpoint
  - [x] 2.5 Write tests for `/api/statistics/monthly` endpoint
  - [x] 2.6 Implement monthly statistics API endpoint
  - [x] 2.7 Write tests for `/api/statistics/chart/{metric}` endpoint
  - [x] 2.8 Implement chart data API endpoint
  - [x] 2.9 Verify all API tests pass

- [x] 3. Create Visual Toggle Component
  - [x] 3.1 Create reusable stat-card template component with toggle functionality
  - [x] 3.2 Add JavaScript for toggle expand/collapse behavior
  - [x] 3.3 Integrate Chart.js for rendering visualizations (pie, bar, line charts)
  - [x] 3.4 Style component to match existing dashboard theme

- [x] 4. Enhance Daily Statistics View
  - [x] 4.1 Update statistics.html daily tab with new metric cards
  - [x] 4.2 Add long/short percentage display with pie chart toggle
  - [x] 4.3 Add long/short win rate display with bar chart toggle
  - [x] 4.4 Add best/worst position, avg points, profit factor metrics
  - [x] 4.5 Wire up API calls and chart rendering
  - [ ] 4.6 Test daily view in browser

- [x] 5. Enhance Weekly Statistics View
  - [x] 5.1 Update statistics.html weekly tab with new metric cards
  - [x] 5.2 Add day-of-week win rate breakdown with bar chart toggle
  - [x] 5.3 Add best/worst trading day display
  - [x] 5.4 Add instrument breakdown with bar chart toggle
  - [x] 5.5 Add long/short metrics (reuse daily component pattern)
  - [x] 5.6 Wire up API calls and chart rendering
  - [ ] 5.7 Test weekly view in browser

- [x] 6. Enhance Monthly Statistics View
  - [x] 6.1 Update statistics.html monthly tab with new metric cards
  - [x] 6.2 Add week-over-week performance display with line chart toggle
  - [x] 6.3 Add best/worst week display
  - [x] 6.4 Add vs previous month comparison display
  - [x] 6.5 Add avg positions per day metric
  - [x] 6.6 Add long/short metrics (reuse component pattern)
  - [x] 6.7 Wire up API calls and chart rendering
  - [ ] 6.8 Test monthly view in browser

- [ ] 7. Final Integration and Testing
  - [x] 7.1 Run full test suite to ensure no regressions
  - [ ] 7.2 Test all three views with account filtering
  - [ ] 7.3 Verify chart toggle functionality across all metrics
  - [ ] 7.4 Test responsive layout on mobile viewport
  - [ ] 7.5 Verify performance meets <100ms calculation target
