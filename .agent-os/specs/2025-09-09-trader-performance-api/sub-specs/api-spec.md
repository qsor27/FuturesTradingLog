# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-09-trader-performance-api/spec.md

> Created: 2025-09-09
> Version: 1.0.0

## Endpoints

### GET /api/performance/daily

**Purpose:** Retrieve current calendar day trading performance metrics for external monitoring systems
**Parameters:** None required
**Response:** JSON object with performance statistics
**Errors:** 500 (database error), 503 (service unavailable)

### GET /api/performance/weekly

**Purpose:** Retrieve current calendar week trading performance metrics for external monitoring systems
**Parameters:** None required
**Response:** JSON object with performance statistics
**Errors:** 500 (database error), 503 (service unavailable)

**Daily Response Format:**
```json
{
  "status": "success",
  "timestamp": "2025-09-09T14:30:00Z",
  "date": "2025-09-09",
  "period": "daily",
  "data": {
    "daily_pnl": -250.75,
    "total_trades": 8,
    "winning_trades": 3,
    "losing_trades": 5,
    "win_rate": 0.375,
    "currency": "USD"
  },
  "metadata": {
    "calculation_method": "position_based",
    "timezone": "America/Chicago",
    "last_updated": "2025-09-09T14:29:45Z"
  }
}
```

**Weekly Response Format:**
```json
{
  "status": "success",
  "timestamp": "2025-09-09T14:30:00Z",
  "week_start": "2025-09-08",
  "week_end": "2025-09-14",
  "period": "weekly",
  "data": {
    "weekly_pnl": -1250.50,
    "total_trades": 35,
    "winning_trades": 15,
    "losing_trades": 20,
    "win_rate": 0.429,
    "currency": "USD"
  },
  "metadata": {
    "calculation_method": "position_based",
    "timezone": "America/Chicago",
    "last_updated": "2025-09-09T14:29:45Z"
  }
}
```

**Error Response Format:**
```json
{
  "status": "error",
  "error": {
    "code": 500,
    "message": "Database connection failed",
    "timestamp": "2025-09-09T14:30:00Z"
  }
}
```

## Controllers

**Action:** get_daily_performance()
**Business Logic:** 
- Query positions table for current calendar day (midnight to midnight)
- Calculate P/L using existing position-based tracking algorithm
- Count completed positions as trades (quantity flow 0 → +/- → 0)
- Categorize trades as winning (positive P/L) or losing (negative P/L)
- Apply Redis caching with 30-60 second TTL

**Action:** get_weekly_performance()
**Business Logic:**
- Query positions table for current calendar week (Monday to Sunday)
- Calculate P/L using existing position-based tracking algorithm for week timeframe
- Count completed positions as trades for the entire week period
- Categorize trades as winning (positive P/L) or losing (negative P/L)
- Apply Redis caching with 30-60 second TTL using separate cache keys

**Error Handling:**
- Database connection failures return 503 status
- Invalid date calculations return 500 status  
- Cache misses fall back to direct database query
- All errors logged using existing structured logging system

## Integration Points

**Database Integration:** Leverages existing FuturesDB context manager and position tracking tables
**Caching Integration:** Uses existing Redis infrastructure with intelligent cache invalidation
**Blueprint Integration:** Follows existing Flask blueprint pattern for consistent routing structure