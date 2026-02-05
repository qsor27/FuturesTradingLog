# Data Freshness Specification

This is the data freshness specification for the spec detailed in @.agent-os/specs/2026-01-26-fix-candle-chart-display/spec.md

## Overview

Implement a hybrid data freshness strategy combining:
1. **Position-triggered fetching** - Automatically fetch OHLC data when positions are imported
2. **Celery background workers** - Scheduled gap-filling during market hours

This ensures charts always have data for traded positions while maintaining general freshness without excessive API calls.

## Strategy 1: Position-Triggered Fetching

### Trigger Points

When a new position is imported (via CSV or API), queue a data fetch job for:
- The position's instrument (e.g., "MNQ MAR26")
- The continuous contract (e.g., "MNQ") as fallback
- Date range: position entry time - 4 hours to position exit time + 1 hour
- Timeframes: Priority set only (1m, 5m, 15m, 1h) to minimize API calls

### Implementation

**Location:** `services/import_service.py` or wherever position imports are handled

```python
def on_position_imported(position):
    """Called after a position is successfully imported"""
    from tasks.gap_filling import fetch_position_ohlc_data

    # Calculate date range with padding
    start_date = position.entry_time - timedelta(hours=4)
    end_date = (position.exit_time or datetime.now()) + timedelta(hours=1)

    # Queue async task (doesn't block import)
    fetch_position_ohlc_data.delay(
        instrument=position.instrument,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        timeframes=['1m', '5m', '15m', '1h'],
        priority='high'
    )
```

**New Celery Task:** `tasks/gap_filling.py`

```python
@celery_app.task(bind=True, queue='gap_filling')
def fetch_position_ohlc_data(self, instrument, start_date, end_date, timeframes, priority='normal'):
    """
    Fetch OHLC data for a specific position's time range.
    Uses smart fetching - only downloads data we don't already have.
    """
    from services.data_service import ohlc_service
    from utils.instrument_utils import get_root_symbol

    instruments_to_fetch = [instrument]
    root_symbol = get_root_symbol(instrument)
    if root_symbol != instrument:
        instruments_to_fetch.append(root_symbol)

    for inst in instruments_to_fetch:
        for tf in timeframes:
            # Check what data we already have
            existing_range = ohlc_service.get_data_range(inst, tf)

            # Only fetch gaps
            gaps = calculate_gaps(existing_range, start_date, end_date)
            for gap_start, gap_end in gaps:
                ohlc_service.fetch_and_store(inst, tf, gap_start, gap_end)

                # Respect rate limits
                time.sleep(YAHOO_FINANCE_CONFIG['rate_limiting']['base_delay'])
```

### Benefits

- **Efficient**: Only fetches data for positions you actually have
- **Immediate**: Data available shortly after import completes
- **Non-blocking**: Import completes quickly, fetch happens in background
- **Smart**: Doesn't re-fetch data that already exists

## Strategy 2: Celery Background Workers in Docker

### Docker Compose Changes

**File:** `docker-compose.yml`

```yaml
services:
  # Existing app service...

  celery-worker:
    image: ${DOCKER_REGISTRY:-ghcr.io/qsorensen}/${DOCKER_IMAGE:-futurestradinglog}:${TAG:-latest}
    container_name: futurestradinglog-celery-worker
    command: celery -A celery_app worker -l info -Q default,gap_filling,cache_maintenance --concurrency=2
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_PATH=/app/data/db/futures_trades_clean.db
    volumes:
      - ./data:/app/data
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "celery", "-A", "celery_app", "inspect", "ping", "-d", "celery@$$HOSTNAME"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-beat:
    image: ${DOCKER_REGISTRY:-ghcr.io/qsorensen}/${DOCKER_IMAGE:-futurestradinglog}:${TAG:-latest}
    container_name: futurestradinglog-celery-beat
    command: celery -A celery_app beat -l info
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./data:/app/data
    depends_on:
      - celery-worker
    restart: unless-stopped
```

### Celery Beat Schedule Updates

**File:** `celery_app.py`

```python
beat_schedule = {
    # Fill gaps for recently active instruments (every 15 min during market hours)
    'fill-recent-gaps': {
        'task': 'tasks.gap_filling.fill_recent_gaps',
        'schedule': crontab(minute='*/15', hour='6-22', day_of_week='0-4'),  # Mon-Fri, 6am-10pm
    },

    # Extended gap filling (every 4 hours)
    'fill-extended-gaps': {
        'task': 'tasks.gap_filling.fill_extended_gaps',
        'schedule': crontab(minute=0, hour='*/4'),
    },

    # Cache maintenance (daily at 2 AM)
    'cache-maintenance': {
        'task': 'tasks.cache_maintenance.cleanup_expired_cache',
        'schedule': crontab(minute=0, hour=2),
    },

    # Health check - verify data freshness (hourly)
    'data-freshness-check': {
        'task': 'tasks.monitoring.check_data_freshness',
        'schedule': crontab(minute=30),
    },
}
```

### Market Hours Awareness

Only fetch data during market hours to avoid wasting API calls:

```python
def is_market_hours():
    """Check if we're in futures market hours (nearly 24/5)"""
    now = datetime.now(timezone('US/Eastern'))
    weekday = now.weekday()
    hour = now.hour

    # Futures trade Sunday 6pm - Friday 5pm ET with 1hr daily break
    if weekday == 5:  # Saturday
        return False
    if weekday == 6 and hour < 18:  # Sunday before 6pm
        return False
    if weekday == 4 and hour >= 17:  # Friday after 5pm
        return False

    return True
```

## API Call Budget Management

### Daily Budget: 2000 calls

**Allocation:**
| Use Case | Calls/Day | Notes |
|----------|-----------|-------|
| Position-triggered | ~200 | Avg 5 positions × 4 timeframes × 2 instruments × 5 gap segments |
| Scheduled gap-filling | ~800 | 3 priority instruments × 6 timeframes × ~45 updates |
| Manual refresh | ~100 | User-triggered |
| **Buffer** | ~900 | For spikes, retries, new instruments |

### Rate Limiting

```python
YAHOO_FINANCE_CONFIG = {
    'rate_limiting': {
        'adaptive_enabled': True,
        'base_delay': 1.0,           # 1 second between calls (safe)
        'max_delay': 30.0,           # Cap backoff at 30 seconds
        'daily_quota_limit': 2000,
        'quota_warning_threshold': 1600,  # Alert at 80%
    }
}
```

## Monitoring and Observability

### New Metrics

```python
# Track data freshness
METRICS = {
    'ohlc_fetch_total': Counter('Total OHLC fetches'),
    'ohlc_fetch_errors': Counter('OHLC fetch errors'),
    'api_quota_used': Gauge('Yahoo API calls today'),
    'data_staleness_hours': Histogram('Hours since last update per instrument'),
}
```

### Health Check Endpoint

**GET /api/v1/health/data-freshness**

```json
{
    "status": "healthy",
    "instruments": {
        "MNQ": {
            "latest_data": "2026-01-26T20:45:00",
            "staleness_minutes": 15,
            "status": "fresh"
        },
        "MNQ MAR26": {
            "latest_data": "2025-12-18T21:59:00",
            "staleness_minutes": 55666,
            "status": "stale"
        }
    },
    "api_quota": {
        "used_today": 847,
        "limit": 2000,
        "remaining": 1153
    },
    "celery": {
        "workers_active": 2,
        "beat_running": true,
        "pending_tasks": 3
    }
}
```

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | Modify | Add celery-worker and celery-beat services |
| `celery_app.py` | Modify | Update beat schedule with market hours |
| `tasks/gap_filling.py` | Modify | Add position-triggered fetch task |
| `services/import_service.py` | Modify | Trigger data fetch on position import |
| `config.py` | Modify | Add market hours config, budget tracking |
| `routes/health.py` | Create | Data freshness health endpoint |

## Testing Plan

1. **Position Import Test**: Import a new position, verify OHLC data is fetched within 2 minutes
2. **Celery Worker Test**: Verify workers start with Docker and process tasks
3. **Rate Limit Test**: Verify system respects 2000/day quota
4. **Market Hours Test**: Verify no fetches during market close
5. **Fallback Test**: Verify continuous contract data is fetched when specific contract unavailable
