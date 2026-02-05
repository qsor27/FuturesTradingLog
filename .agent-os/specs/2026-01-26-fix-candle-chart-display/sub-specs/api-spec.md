# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2026-01-26-fix-candle-chart-display/spec.md

## Endpoints

### GET /api/chart-data/<instrument>

**Purpose:** Fetch OHLC candle data for chart display with automatic continuous contract fallback

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| timeframe | string | Yes | Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d |
| days | int | No | Number of days of data (default: 1) |
| start_date | ISO datetime | No | Explicit start date for position auto-centering |
| end_date | ISO datetime | No | Explicit end date for position auto-centering |
| position_id | int | No | Position ID for execution overlay data |

**Response (Success):**
```json
{
    "success": true,
    "instrument": "MNQ MAR26",
    "timeframe": "1m",
    "count": 480,
    "has_data": true,
    "data": [
        {
            "time": 1769460000,
            "open": 25880.00,
            "high": 25885.00,
            "low": 25878.00,
            "close": 25883.75,
            "volume": 1234
        }
    ],
    "metadata": {
        "requested_instrument": "MNQ MAR26",
        "actual_instrument": "MNQ",
        "is_continuous_fallback": true,
        "start_date": "2026-01-26T16:41:18",
        "end_date": "2026-01-27T00:42:13",
        "data_source": "database",
        "processing_time_ms": 15.5
    },
    "available_timeframes": {
        "1m": 21096,
        "5m": 11684,
        "15m": 3681,
        "1h": 922,
        "4h": 253,
        "1d": 255
    },
    "best_timeframe": "1m"
}
```

**Response (No Data):**
```json
{
    "success": true,
    "instrument": "MNQ MAR26",
    "timeframe": "1m",
    "count": 0,
    "has_data": false,
    "data": [],
    "metadata": {
        "requested_instrument": "MNQ MAR26",
        "actual_instrument": "MNQ MAR26",
        "is_continuous_fallback": false,
        "fallback_attempted": true,
        "fallback_instrument": "MNQ",
        "fallback_also_empty": true
    },
    "available_timeframes": {},
    "best_timeframe": null,
    "error_hint": "No market data available for MNQ MAR26 or MNQ in the requested date range."
}
```

**Key Changes:**
- New `metadata.is_continuous_fallback` field indicates when continuous contract data is being returned
- New `metadata.actual_instrument` shows which instrument's data is actually being returned
- `available_timeframes` now reflects the actual instrument being used (after fallback if applicable)

### GET /api/available-timeframes/<instrument>

**Purpose:** Get available timeframes and data counts for instrument, with fallback awareness

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| start_date | ISO datetime | No | Filter by date range start |
| end_date | ISO datetime | No | Filter by date range end |

**Response:**
```json
{
    "success": true,
    "instrument": "MNQ MAR26",
    "has_data": true,
    "available_timeframes": {
        "1m": 21096,
        "5m": 11684,
        "15m": 3681,
        "1h": 922
    },
    "best_timeframe": "1m",
    "total_timeframes": 4,
    "fallback_info": {
        "using_fallback": true,
        "fallback_instrument": "MNQ",
        "reason": "MNQ MAR26 has no data for requested date range"
    }
}
```

**Key Changes:**
- New `fallback_info` object when continuous contract fallback is needed
- When `start_date`/`end_date` are provided, check data availability within that range
- Counts should reflect data available within the requested date range (if specified)

## Error Handling

All endpoints return consistent error format:
```json
{
    "success": false,
    "error": "Error message",
    "error_code": "INSTRUMENT_NOT_FOUND",
    "available_instruments": ["MNQ", "MNQ MAR26", "ES", "ES MAR26"]
}
```

Error codes:
- `INSTRUMENT_NOT_FOUND` - Unknown instrument symbol
- `INVALID_TIMEFRAME` - Unsupported timeframe value
- `NO_DATA_AVAILABLE` - No data for instrument/timeframe/date range
- `DATE_RANGE_ERROR` - Invalid start_date/end_date parameters
