# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-12-26-daily-import-deduplication/spec.md

## Technical Requirements

### Redis State Tracking

- **Key**: `daily_import:last_scheduled:{YYYYMMDD}`
- **Value**: JSON with timestamp, result status, executions imported
- **TTL**: 7 days (cleanup old entries automatically)
- **Check**: Before running scheduled import, verify key doesn't exist for today's date

### Market Day Validation

- Use Python's `datetime.weekday()` to check if current day is Saturday (5) or Sunday (6)
- Skip scheduled import with INFO log message: "Skipping scheduled import - market closed (weekend)"
- Continue to allow manual imports on weekends if explicitly triggered

### Import Deduplication Logic

```python
def _should_run_scheduled_import(self) -> tuple[bool, str]:
    """
    Check if scheduled import should run.

    Returns:
        (should_run, reason) tuple
    """
    now_pt = datetime.now(self.pacific_tz)
    today_str = now_pt.strftime('%Y%m%d')

    # Check if weekend
    if now_pt.weekday() in (5, 6):  # Saturday or Sunday
        return False, "market closed (weekend)"

    # Check if already ran today
    redis_key = f'daily_import:last_scheduled:{today_str}'
    if self.redis_client and self.redis_client.exists(redis_key):
        return False, f"already completed for {today_str}"

    return True, "ready to run"
```

### State Recording After Success

```python
def _record_scheduled_import_complete(self, result: dict):
    """Record successful scheduled import to Redis."""
    if not self.redis_client:
        return

    today_str = datetime.now(self.pacific_tz).strftime('%Y%m%d')
    redis_key = f'daily_import:last_scheduled:{today_str}'

    import_record = {
        'timestamp': datetime.now(self.pacific_tz).isoformat(),
        'success': result.get('success', False),
        'executions_imported': result.get('total_executions', 0),
        'files_processed': result.get('files_processed', 0)
    }

    self.redis_client.setex(
        redis_key,
        7 * 24 * 60 * 60,  # 7 day TTL
        json.dumps(import_record)
    )
```

### Manual Import Behavior

- Manual imports via `/api/csv/daily-import/manual` should NOT check deduplication
- Manual imports should NOT update the scheduled import Redis key
- This allows users to force reimport if needed

### Logging Requirements

- Log skip reason clearly: "Skipping scheduled import: {reason}"
- Log successful deduplication check: "Daily import check passed, proceeding with import"
- Include date context in all log messages

## Integration Points

- **File**: `services/daily_import_scheduler.py`
- **Method to modify**: `_scheduled_import_callback()`
- **New methods**: `_should_run_scheduled_import()`, `_record_scheduled_import_complete()`
- **Redis client**: Use existing `self.import_service.redis_client` or add direct Redis connection

## Performance Criteria

- Redis check should add < 5ms to import startup
- No impact on manual import performance
- Graceful degradation if Redis unavailable (proceed with import, log warning)
