# API Specification

This is the API specification for the spec detailed in @agent-os/specs/2025-12-03-ohlc-data-completeness-monitor/spec.md

## Endpoints

### GET /monitoring/data-completeness

**Purpose:** Render the data completeness dashboard HTML page

**Parameters:** None

**Response:** HTML page with Bootstrap 5 styled dashboard

**Template:** `templates/monitoring/data_completeness.html`

---

### GET /api/monitoring/completeness-matrix

**Purpose:** Get JSON data for the completeness matrix (for AJAX refresh)

**Parameters:** None

**Response:**
```json
{
  "success": true,
  "data": {
    "matrix": {
      "ES": {
        "1m": {
          "record_count": 9902,
          "expected_minimum": 2730,
          "completeness_pct": 362.7,
          "status": "complete",
          "last_timestamp": "2025-12-03T14:30:00",
          "data_age_hours": 2.5,
          "freshness_status": "fresh"
        },
        "5m": { ... },
        "15m": { ... },
        "1h": { ... },
        "4h": { ... },
        "1d": { ... }
      },
      "MNQ": { ... },
      "NQ": { ... },
      "YM": { ... },
      "RTY": { ... },
      "CL": { ... },
      "GC": { ... }
    },
    "summary": {
      "total_cells": 42,
      "complete_cells": 28,
      "partial_cells": 8,
      "missing_cells": 6,
      "health_score": 66.7,
      "last_full_sync": "2025-12-03T14:05:00",
      "next_scheduled_sync": "2025-12-04T14:05:00"
    }
  },
  "cached": true,
  "cache_age_seconds": 45
}
```

**Errors:**
- 500: Database connection error
- 503: Service unavailable (Redis down)

---

### GET /api/monitoring/gap-details/{instrument}/{timeframe}

**Purpose:** Get detailed gap analysis for a specific instrument/timeframe

**Parameters:**
- `instrument` (path): Yahoo Finance symbol suffix (ES, MNQ, NQ, YM, RTY, CL, GC)
- `timeframe` (path): Timeframe string (1m, 5m, 15m, 1h, 4h, 1d)

**Response:**
```json
{
  "success": true,
  "data": {
    "instrument": "NQ",
    "timeframe": "15m",
    "record_count": 0,
    "expected_minimum": 1560,
    "status": "missing",
    "date_range": {
      "earliest": null,
      "latest": null,
      "expected_start": "2025-10-05",
      "expected_end": "2025-12-03"
    },
    "sync_history": [
      {
        "timestamp": "2025-12-02T14:05:00",
        "success": false,
        "error": "HTTP 429: Rate limit exceeded",
        "records_added": 0
      },
      {
        "timestamp": "2025-12-01T14:05:00",
        "success": false,
        "error": "Timeout after 30s",
        "records_added": 0
      }
    ],
    "repair_available": true
  }
}
```

**Errors:**
- 400: Invalid instrument or timeframe
- 404: No data found (returns empty analysis)

---

### POST /api/monitoring/repair-gap

**Purpose:** Trigger a targeted OHLC fetch for a specific gap

**Request Body:**
```json
{
  "instrument": "NQ",
  "timeframe": "15m"
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "instrument": "NQ",
    "timeframe": "15m",
    "records_added": 1560,
    "fetch_duration_seconds": 3.2,
    "new_status": "complete",
    "message": "Successfully repaired gap: 1560 records added for NQ 15m"
  }
}
```

**Response (Failure):**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Yahoo Finance rate limit exceeded. Try again in 5 minutes.",
    "retry_after_seconds": 300
  }
}
```

**Errors:**
- 400: Invalid instrument or timeframe
- 429: Rate limited (includes retry_after_seconds)
- 503: Yahoo Finance API unavailable

---

### GET /api/monitoring/sync-health

**Purpose:** Get sync health history for the timeline view

**Parameters:**
- `days` (query, optional): Number of days of history (default: 7, max: 30)

**Response:**
```json
{
  "success": true,
  "data": {
    "history": [
      {
        "timestamp": "2025-12-03T14:05:00",
        "trigger": "scheduled",
        "duration_seconds": 125.3,
        "instruments_synced": 7,
        "timeframes_synced": 6,
        "total_records_added": 2340,
        "success": true,
        "errors": []
      },
      {
        "timestamp": "2025-12-02T14:05:00",
        "trigger": "scheduled",
        "duration_seconds": 180.5,
        "instruments_synced": 7,
        "timeframes_synced": 6,
        "total_records_added": 890,
        "success": false,
        "errors": [
          {"instrument": "NQ", "timeframe": "15m", "error": "HTTP 429"},
          {"instrument": "CL", "timeframe": "1m", "error": "Timeout"}
        ]
      }
    ],
    "summary": {
      "total_syncs": 14,
      "successful_syncs": 10,
      "failed_syncs": 4,
      "success_rate": 71.4,
      "avg_records_per_sync": 1850
    }
  }
}
```

**Errors:**
- 400: Invalid days parameter
- 503: Redis unavailable
