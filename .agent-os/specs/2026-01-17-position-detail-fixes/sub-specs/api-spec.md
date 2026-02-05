# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2026-01-17-position-detail-fixes/spec.md

## Endpoints

### GET /api/chart-data/<instrument>

**Purpose:** Retrieve OHLC candlestick data for chart display

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| timeframe | string | No | Chart timeframe (1m, 5m, 15m, 1h, 4h, 1d). Default: 1h |
| days | integer | No | Number of days of data. Default: 1 |
| start_date | string | No | ISO 8601 start date (e.g., 2026-01-15T00:00:00) |
| end_date | string | No | ISO 8601 end date (e.g., 2026-01-16T00:00:00) |
| position_id | integer | No | Position ID for execution overlay markers |

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "time": 1736935200,
      "open": 19485.25,
      "high": 19510.50,
      "low": 19480.75,
      "close": 19505.00,
      "volume": 45230
    }
  ],
  "count": 127,
  "instrument": "MNQ",
  "timeframe": "1h",
  "available_timeframes": {"1h": 500, "15m": 2000},
  "best_timeframe": "1h",
  "executions": [
    {
      "id": 123,
      "timestamp": "2026-01-15T14:30:00",
      "timestamp_ms": 1736952600000,
      "price": 19485.25,
      "quantity": 2,
      "side": "buy",
      "execution_type": "entry"
    }
  ]
}
```

**Response (No Data):**
```json
{
  "success": true,
  "data": [],
  "count": 0,
  "instrument": "MNQ",
  "timeframe": "1h",
  "available_timeframes": {"4h": 250, "1d": 100},
  "best_timeframe": "4h",
  "message": "No data for requested timeframe, try available_timeframes"
}
```

**Errors:**
| Code | Message | Cause |
|------|---------|-------|
| 400 | Invalid instrument | Instrument parameter missing or invalid |
| 400 | Invalid timeframe | Timeframe not in allowed list |
| 400 | Invalid date format | start_date or end_date not ISO 8601 |

---

### GET /api/executions/<position_id>

**Purpose:** Retrieve execution data for chart arrow markers

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| timeframe | string | No | Chart timeframe for timestamp alignment. Default: 1h |
| start_date | string | No | ISO 8601 filter start |
| end_date | string | No | ISO 8601 filter end |

**Response:**
```json
{
  "success": true,
  "executions": [
    {
      "id": 123,
      "timestamp": "2026-01-15T14:30:00",
      "timestamp_ms": 1736952600000,
      "price": 19485.25,
      "quantity": 2,
      "side": "buy",
      "execution_type": "entry",
      "pnl_dollars": 0,
      "pnl_points": 0,
      "commission": 0.70,
      "position_quantity": 2,
      "avg_price": 19485.25
    },
    {
      "id": 123,
      "timestamp": "2026-01-15T15:10:00",
      "timestamp_ms": 1736955000000,
      "price": 19510.50,
      "quantity": 2,
      "side": "sell",
      "execution_type": "exit",
      "pnl_dollars": 101.00,
      "pnl_points": 25.25,
      "commission": 0.70,
      "position_quantity": 0,
      "avg_price": 19510.50
    }
  ],
  "chart_bounds": {
    "min_time": "2026-01-15T14:30:00",
    "max_time": "2026-01-15T15:10:00",
    "min_price": 19485.25,
    "max_price": 19510.50
  },
  "timeframe_info": {
    "selected": "1h",
    "candle_duration_ms": 3600000
  }
}
```

**Errors:**
| Code | Message | Cause |
|------|---------|-------|
| 404 | Position not found | Invalid position_id |

---

### GET /api/position/<position_id>/execution-pairs

**Purpose:** Retrieve FIFO-matched execution pairs with per-pair P&L (NEW ENDPOINT)

**Parameters:** None (position_id in URL)

**Response:**
```json
{
  "success": true,
  "position_id": 346,
  "instrument": "MNQ",
  "position_type": "Long",
  "execution_pairs": [
    {
      "pair_number": 1,
      "entry_time": "2026-01-15T14:30:00",
      "exit_time": "2026-01-15T15:07:00",
      "entry_price": 19485.25,
      "exit_price": 19510.50,
      "quantity": 2,
      "duration_seconds": 2220,
      "duration_display": "37m",
      "points_pnl": 25.25,
      "dollars_pnl": 101.00,
      "entry_commission": 0.70,
      "exit_commission": 0.70,
      "total_commission": 1.40,
      "entry_execution_id": "abc123",
      "exit_execution_id": "def456"
    },
    {
      "pair_number": 2,
      "entry_time": "2026-01-15T14:42:00",
      "exit_time": "2026-01-15T15:15:00",
      "entry_price": 19490.00,
      "exit_price": 19505.00,
      "quantity": 1,
      "duration_seconds": 1980,
      "duration_display": "33m",
      "points_pnl": 15.00,
      "dollars_pnl": 30.00,
      "entry_commission": 0.35,
      "exit_commission": 0.35,
      "total_commission": 0.70,
      "entry_execution_id": "ghi789",
      "exit_execution_id": "jkl012"
    }
  ],
  "summary": {
    "total_pairs": 2,
    "total_quantity": 3,
    "total_points_pnl": 40.25,
    "total_dollars_pnl": 131.00,
    "total_commission": 2.10,
    "net_pnl": 128.90,
    "winning_pairs": 2,
    "losing_pairs": 0,
    "win_rate": 100.0
  }
}
```

**Errors:**
| Code | Message | Cause |
|------|---------|-------|
| 404 | Position not found | Invalid position_id |
| 400 | Position still open | Cannot calculate pairs for open positions |

## Controller Logic

### Execution Pair Matching (FIFO)

```python
def get_execution_pairs(position_id: int) -> Dict:
    """
    Match entries to exits using FIFO (First-In-First-Out).

    Algorithm:
    1. Get all executions for position
    2. Separate into entry_queue (buys for long, sells for short)
    3. Separate into exit_queue (sells for long, buys for short)
    4. Sort both queues by timestamp
    5. For each exit execution:
       a. Pop oldest entry from queue
       b. Match quantities (handle partial fills)
       c. Calculate P&L for matched pair
    6. Return list of matched pairs with P&L
    """
```

### Chart Data with Position Context

```python
def get_chart_data(instrument: str, **params) -> Dict:
    """
    1. Parse date range from start_date/end_date or calculate from days
    2. Query cache_only_chart_service for OHLC data
    3. If position_id provided:
       a. Get executions for position
       b. Add to response as 'executions' array
    4. Format response for TradingView Lightweight Charts
    """
```

## Error Handling

- All endpoints return JSON with `success: false` and `error` message on failure
- HTTP status codes used appropriately (400 for bad request, 404 for not found)
- Detailed error messages in development, generic in production
