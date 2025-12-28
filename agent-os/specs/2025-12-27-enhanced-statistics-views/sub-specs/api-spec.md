# API Specification

This is the API specification for the spec detailed in @agent-os/specs/2025-12-27-enhanced-statistics-views/spec.md

## Endpoints

### GET /api/statistics/daily

**Purpose:** Retrieve comprehensive daily statistics for a specific date.

**Parameters:**
- `date` (optional): Date in YYYY-MM-DD format. Defaults to today.
- `accounts` (optional): Comma-separated list of account IDs to filter.

**Response:**
```json
{
  "date": "2025-12-27",
  "position_count": 12,
  "win_rate": 66.7,
  "long_count": 7,
  "short_count": 5,
  "long_percentage": 58.3,
  "short_percentage": 41.7,
  "long_win_rate": 71.4,
  "short_win_rate": 60.0,
  "best_position_pnl": 450.00,
  "worst_position_pnl": -200.00,
  "avg_points_per_position": 3.25,
  "profit_factor": 2.1,
  "total_pnl": 875.00,
  "gross_profit": 1250.00,
  "gross_loss": 375.00,
  "total_commission": 48.00
}
```

**Errors:**
- `400 Bad Request`: Invalid date format
- `404 Not Found`: No data for specified date

---

### GET /api/statistics/weekly

**Purpose:** Retrieve comprehensive weekly statistics including day-by-day breakdown.

**Parameters:**
- `week_start` (optional): Start date of week (Monday) in YYYY-MM-DD format. Defaults to current week.
- `accounts` (optional): Comma-separated list of account IDs to filter.

**Response:**
```json
{
  "week_start": "2025-12-23",
  "week_end": "2025-12-27",
  "position_count": 45,
  "win_rate": 62.2,
  "long_count": 28,
  "short_count": 17,
  "long_percentage": 62.2,
  "short_percentage": 37.8,
  "long_win_rate": 64.3,
  "short_win_rate": 58.8,
  "total_pnl": 2340.00,
  "profit_factor": 1.85,
  "day_breakdown": [
    {"day": "Monday", "date": "2025-12-23", "position_count": 8, "win_rate": 75.0, "pnl": 620.00},
    {"day": "Tuesday", "date": "2025-12-24", "position_count": 10, "win_rate": 50.0, "pnl": -120.00},
    {"day": "Wednesday", "date": "2025-12-25", "position_count": 0, "win_rate": null, "pnl": 0.00},
    {"day": "Thursday", "date": "2025-12-26", "position_count": 12, "win_rate": 66.7, "pnl": 890.00},
    {"day": "Friday", "date": "2025-12-27", "position_count": 15, "win_rate": 60.0, "pnl": 950.00}
  ],
  "best_day": {"day": "Monday", "win_rate": 75.0},
  "worst_day": {"day": "Tuesday", "win_rate": 50.0},
  "instrument_breakdown": [
    {"instrument": "ES", "position_count": 25, "pnl": 1500.00, "win_rate": 68.0},
    {"instrument": "NQ", "position_count": 15, "pnl": 640.00, "win_rate": 53.3},
    {"instrument": "CL", "position_count": 5, "pnl": 200.00, "win_rate": 60.0}
  ]
}
```

**Errors:**
- `400 Bad Request`: Invalid date format or date is not a Monday
- `404 Not Found`: No data for specified week

---

### GET /api/statistics/monthly

**Purpose:** Retrieve comprehensive monthly statistics including week-by-week breakdown.

**Parameters:**
- `year` (optional): Year as YYYY. Defaults to current year.
- `month` (optional): Month as 1-12. Defaults to current month.
- `accounts` (optional): Comma-separated list of account IDs to filter.

**Response:**
```json
{
  "year": 2025,
  "month": 12,
  "month_name": "December",
  "position_count": 180,
  "avg_positions_per_day": 8.2,
  "trading_days": 22,
  "win_rate": 58.9,
  "long_count": 105,
  "short_count": 75,
  "long_percentage": 58.3,
  "short_percentage": 41.7,
  "long_win_rate": 61.0,
  "short_win_rate": 56.0,
  "total_pnl": 8450.00,
  "profit_factor": 1.72,
  "week_breakdown": [
    {"week_number": 1, "week_start": "2025-12-01", "position_count": 42, "win_rate": 64.3, "pnl": 2100.00},
    {"week_number": 2, "week_start": "2025-12-08", "position_count": 48, "win_rate": 54.2, "pnl": 1850.00},
    {"week_number": 3, "week_start": "2025-12-15", "position_count": 45, "win_rate": 60.0, "pnl": 2160.00},
    {"week_number": 4, "week_start": "2025-12-22", "position_count": 45, "win_rate": 57.8, "pnl": 2340.00}
  ],
  "best_week": {"week_number": 3, "pnl": 2160.00},
  "worst_week": {"week_number": 2, "pnl": 1850.00},
  "vs_previous_month": {
    "pnl_difference": 1250.00,
    "pnl_percentage_change": 17.4,
    "win_rate_difference": 3.2
  }
}
```

**Errors:**
- `400 Bad Request`: Invalid year/month values
- `404 Not Found`: No data for specified month

---

### GET /api/statistics/chart/{metric}

**Purpose:** Retrieve chart-ready data for a specific metric visualization.

**Parameters:**
- `metric` (path): One of: `daily-long-short`, `weekly-day-breakdown`, `weekly-instruments`, `monthly-week-breakdown`
- `period` (query): Date or period identifier (format depends on metric)
- `accounts` (optional): Comma-separated list of account IDs to filter.

**Response (varies by metric):**

For `daily-long-short`:
```json
{
  "chart_type": "pie",
  "data": [
    {"label": "Long", "value": 58.3, "color": "#28a745"},
    {"label": "Short", "value": 41.7, "color": "#dc3545"}
  ]
}
```

For `weekly-day-breakdown`:
```json
{
  "chart_type": "bar",
  "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
  "datasets": [
    {
      "label": "Win Rate %",
      "data": [75.0, 50.0, null, 66.7, 60.0],
      "backgroundColor": "#0d6efd"
    }
  ]
}
```

**Errors:**
- `400 Bad Request`: Invalid metric name or period format
- `404 Not Found`: No data for specified parameters
