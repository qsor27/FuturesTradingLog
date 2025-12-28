# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-12-03-ohlc-data-completeness-monitor/spec.md

## Technical Requirements

### Data Completeness Matrix Component

- Create new route `/monitoring/data-completeness` in `routes/data_monitoring.py`
- Build responsive HTML table using Bootstrap 5 grid showing:
  - Rows: 7 instruments (ES, MNQ, NQ, YM, RTY, CL, GC)
  - Columns: 6 priority timeframes (1m, 5m, 15m, 1h, 4h, 1d)
  - Cells: Color-coded status badges with record counts
- Color coding logic:
  - **Green**: Record count >= expected minimum for timeframe
  - **Yellow**: Record count > 0 but < 50% of expected minimum
  - **Red**: Zero records or data older than freshness threshold
- Expected minimums based on Yahoo Finance limits:
  - 1m: 7 days * 390 bars/day = ~2,730 records
  - 5m: 60 days * 78 bars/day = ~4,680 records
  - 15m: 60 days * 26 bars/day = ~1,560 records
  - 1h: 365 days * 6.5 bars/day = ~2,372 records
  - 4h: 365 days * 1.6 bars/day = ~584 records
  - 1d: 365 records

### Gap Detection Service

- Create new service class `DataCompletenessService` in `services/data_completeness_service.py`
- Methods:
  - `get_completeness_matrix()`: Returns dict of instrument -> timeframe -> status
  - `get_gap_details(instrument, timeframe)`: Returns detailed gap analysis
  - `get_sync_health_history(days=7)`: Returns list of recent sync results
  - `trigger_gap_repair(instrument, timeframe)`: Initiates targeted OHLC fetch
- Status object structure:
  ```python
  {
      'record_count': int,
      'expected_minimum': int,
      'completeness_pct': float,
      'status': 'complete' | 'partial' | 'missing',
      'last_timestamp': datetime,
      'data_age_hours': float,
      'freshness_status': 'fresh' | 'stale' | 'missing'
  }
  ```

### Freshness Thresholds

- 1m data: Stale if > 24 hours old
- 5m data: Stale if > 48 hours old
- 15m-1h data: Stale if > 72 hours old
- 4h-1d data: Stale if > 7 days old

### Sync Health Timeline

- Store sync results in Redis with 7-day TTL:
  - Key: `ohlc_sync_history:{date}`
  - Value: JSON array of sync result objects
- Display as vertical timeline showing:
  - Timestamp of each sync
  - Success/failure status
  - Instruments synced
  - Records added
  - Any errors encountered

### One-Click Gap Repair

- Add AJAX endpoint `POST /api/monitoring/repair-gap`
- Request body: `{ "instrument": "ES", "timeframe": "15m" }`
- Response: `{ "success": true, "records_added": 1560, "message": "..." }`
- Uses existing `OHLCDataService._sync_instrument()` method
- Bypasses rate limiter queue for immediate execution (single targeted fetch)
- Updates dashboard via WebSocket or polling after completion

### UI/UX Specifications

- Dashboard header showing:
  - Overall health score (% of cells complete)
  - Last full sync timestamp
  - Next scheduled sync time
- Matrix cells are clickable, opening a modal with:
  - Detailed gap analysis
  - Date range of existing data
  - "Repair Now" button
  - Historical sync attempts for this cell
- Auto-refresh every 60 seconds via JavaScript polling
- Loading spinner during repair operations
- Toast notifications for repair success/failure

### Integration Points

- Leverage existing `FuturesDB.get_ohlc_count(instrument, timeframe)` for record counts
- Use existing `OHLCDataService.sync_instruments()` for repairs
- Store sync history in Redis alongside existing cache data
- Reuse existing Bootstrap 5 styling from other monitoring pages

### Performance Considerations

- Cache completeness matrix in Redis for 5 minutes to avoid repeated DB queries
- Use batch SQL query to get all counts in single database round-trip:
  ```sql
  SELECT instrument, timeframe, COUNT(*) as count, MAX(timestamp) as latest
  FROM ohlc_data
  GROUP BY instrument, timeframe
  ```
- Limit sync history to 100 most recent entries per day
