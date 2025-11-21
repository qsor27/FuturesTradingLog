# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-10-position-execution-chart-arrows/spec.md

## Endpoints

### GET /api/positions/<position_id>/executions-chart

**Purpose:** Retrieve execution data formatted for chart arrow display with precise timestamps and positioning data
**Parameters:** 
- `position_id` (path): Position identifier
- `timeframe` (query, optional): Chart timeframe ('1m', '5m', '1h'), defaults to '1h'
- `start_date` (query, optional): Start date for execution filtering (ISO 8601)
- `end_date` (query, optional): End date for execution filtering (ISO 8601)

**Response:** JSON object containing execution data optimized for chart display
```json
{
  "executions": [
    {
      "id": 12345,
      "timestamp": "2025-09-10T14:30:15.123Z",
      "timestamp_ms": 1725979815123,
      "price": 23645.75,
      "quantity": 2,
      "side": "buy|sell",
      "execution_type": "entry|exit",
      "pnl_dollars": -13.50,
      "pnl_points": -3.25,
      "commission": 2.50,
      "position_quantity": 2,
      "avg_price": 23643.25
    }
  ],
  "chart_bounds": {
    "min_timestamp": 1725979200000,
    "max_timestamp": 1725982800000,
    "min_price": 23600.00,
    "max_price": 23700.00
  },
  "timeframe_info": {
    "selected": "1h",
    "candle_duration_ms": 3600000
  }
}
```

**Errors:** 
- 404: Position not found
- 400: Invalid timeframe parameter
- 500: Database or calculation error

### Enhanced GET /api/chart-data/<instrument>

**Purpose:** Extend existing chart data endpoint to include execution overlay markers when position_id is provided
**Parameters:**
- `instrument` (path): Trading instrument symbol
- `timeframe` (query): Chart timeframe ('1m', '5m', '1h')
- `period` (query): Time period for chart data
- `position_id` (query, optional): Position ID to include execution overlays

**Response:** Existing OHLC data structure with added executions array when position_id provided
```json
{
  "ohlc_data": [...],
  "volume_data": [...],
  "executions": [
    {
      "timestamp": 1725979815123,
      "price": 23645.75,
      "arrow_type": "entry|exit",
      "side": "buy|sell",
      "tooltip_data": {
        "quantity": 2,
        "pnl_dollars": -13.50,
        "execution_id": 12345
      }
    }
  ]
}
```

**Errors:**
- 404: Instrument or position not found
- 400: Invalid parameters
- 500: Data processing error

## Controller Logic

### ExecutionChartController
- **getExecutionsForChart()**: Retrieve and format execution data for chart display
- **alignTimestampsToCandles()**: Align execution timestamps with candle boundaries based on timeframe
- **calculateChartBounds()**: Determine optimal chart display boundaries including execution price range
- **formatTooltipData()**: Structure execution data for frontend tooltip consumption

### Enhanced PositionController  
- **getPositionWithChartData()**: Combine position details with chart-ready execution data
- **validateChartParameters()**: Validate timeframe and date range parameters
- **cacheExecutionData()**: Implement Redis caching for execution chart data to improve performance