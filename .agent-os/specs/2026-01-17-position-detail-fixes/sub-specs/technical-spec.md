# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2026-01-17-position-detail-fixes/spec.md

## Technical Requirements

### 1. Execution Pair Display with FIFO Matching

**Backend Changes:**

- Modify `get_position_executions()` in `scripts/TradingLog_db.py` to return FIFO-matched entry/exit pairs
- Each pair should include:
  - `entry_time`, `entry_price`, `entry_quantity`
  - `exit_time`, `exit_price`
  - `pair_points_pnl` = (exit_price - entry_price) for long, inverse for short
  - `pair_dollars_pnl` = pair_points_pnl × quantity × instrument_multiplier
  - `pair_duration` = exit_time - entry_time
  - `pair_commission` = entry_commission + exit_commission

**FIFO Matching Algorithm:**
```
1. Sort all executions by timestamp
2. Separate into entry_queue and exit_queue based on side
3. For each exit:
   a. Match with oldest available entry (FIFO)
   b. Handle partial fills (entry qty > exit qty or vice versa)
   c. Calculate per-pair P&L
4. Return list of matched pairs
```

**Template Changes:**
- Update `templates/positions/detail.html` execution table to show:
  - Pair # (1, 2, 3...)
  - Entry Time | Exit Time
  - Entry Price | Exit Price
  - Quantity
  - Duration
  - Points P&L (colored)
  - Dollar P&L (colored)
  - Commission

### 2. Candle Data Pipeline Diagnosis & Fix

**Investigation Areas:**

1. **Date Range Calculation** (`routes/positions.py` lines 196-267)
   - Verify `chart_start_date` and `chart_end_date` are calculated correctly
   - Check timezone conversion (Pacific → UTC) is accurate
   - Ensure dates are passed to template in correct ISO format

2. **Cache-Only Chart Service** (`services/cache_only_chart_service.py`)
   - Verify database query is finding data for requested instrument/timeframe
   - Check instrument name matching (e.g., "MNQ" vs "MNQ SEP25")
   - Validate date range filtering in queries

3. **Chart API Endpoint** (`routes/chart_data.py` lines 104-282)
   - Verify `start_date` and `end_date` params are being parsed correctly
   - Check data is being returned in TradingView Lightweight Charts format
   - Validate `position_id` triggers execution overlay loading

4. **Frontend Chart Loading** (`static/js/PriceChart.js`)
   - Verify chart initialization with date range parameters
   - Check API request URL construction
   - Validate data binding to candlestick series

5. **Database Data Availability**
   - Query `ohlc_data` table to confirm data exists for position's date range
   - Check if timeframe requested has data (1m, 5m, 15m, 1h, 4h, 1d)

**Likely Fix Areas:**
- Instrument name mismatch between position and OHLC data
- Date range calculation not accounting for UTC properly
- Chart service query filtering out valid data
- Frontend not passing date params to API

### 3. Execution Arrow Markers

**Backend:**
- `get_position_executions_for_chart()` in `scripts/TradingLog_db_extension.py` already provides execution data
- Verify it returns proper format for chart markers:
  ```json
  {
    "id": "exec_123",
    "timestamp": "2026-01-15T14:30:00",
    "timestamp_ms": 1736952600000,
    "price": 19485.25,
    "quantity": 2,
    "side": "buy",
    "execution_type": "entry"
  }
  ```

**Frontend:**
- `PriceChart.js` has `loadExecutionArrows()` method (lines 2303-2365)
- `addExecutionArrows()` creates markers (lines 1038-1065)
- Verify arrow rendering:
  - Entry (Buy for Long, Sell for Short) → Green arrow below bar
  - Exit (Sell for Long, Buy for Short) → Red arrow above bar

**Marker Configuration:**
```javascript
{
  time: unix_timestamp,
  position: 'belowBar' | 'aboveBar',
  color: '#4CAF50' (entry) | '#F44336' (exit),
  shape: 'arrowUp' | 'arrowDown',
  text: 'ENTRY: 2@19485.25' | 'EXIT: 2@19510.50'
}
```

### 4. Chart Date Range Handling

**Current Implementation:**
- Position route calculates padding based on trade duration
- Very short (< 1 hour): 4 hours padding
- Standard (1-30 days): 15% duration padding
- Long (> 30 days): 20% duration padding

**Required Verification:**
- Chart receives `data-start-date` and `data-end-date` attributes
- PriceChart.js reads these and includes in API request
- API parses ISO dates correctly
- Query uses inclusive date filtering

## UI/UX Specifications

### Execution Table Layout

| Pair | Entry Time | Exit Time | Qty | Entry $ | Exit $ | Duration | Pts P&L | $ P&L | Comm |
|------|------------|-----------|-----|---------|--------|----------|---------|-------|------|
| 1 | 2026-01-15 09:35 | 2026-01-15 10:12 | 2 | 19485.25 | 19510.50 | 37m | +25.25 | +$101.00 | $1.40 |
| 2 | 2026-01-15 09:42 | 2026-01-15 10:15 | 1 | 19490.00 | 19505.00 | 33m | +15.00 | +$30.00 | $0.70 |

**Styling:**
- Positive P&L: Green (#4ade80)
- Negative P&L: Red (#f87171)
- Duration: Gray (#9ca3af)
- Table maintains current dark theme

### Chart Arrow Markers

- Entry arrows: Bright green (#4CAF50), positioned below candle
- Exit arrows: Bright red (#F44336), positioned above candle
- Arrow text shows: "ENTRY: qty@price" or "EXIT: qty@price"
- Markers should be visible at all zoom levels

## Performance Considerations

- FIFO matching should be O(n) where n = number of executions
- Execution data already cached via Redis (`get_position_executions_for_chart_cached`)
- Chart data uses cache-only mode (no API calls during page load)
- No additional database queries beyond existing patterns
