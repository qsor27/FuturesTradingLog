# Chart Data Fetch Investigation
**Date:** 2026-02-05
**Issue:** Charts not automatically fetching OHLC data when needed

## Executive Summary

**ROOT CAUSE FOUND:** The automatic OHLC data fetching infrastructure exists but has **3 critical gaps** preventing it from working:

1. ❌ **Import services don't trigger OHLC fetch** - NinjaTrader and unified CSV imports rebuild positions but discard the position IDs needed to trigger fetching
2. ❌ **Chart pages don't trigger on-demand fetch** - Position detail page loads charts without checking for or fetching missing data
3. ❌ **No manual fetch option** - Users have no way to manually trigger data download

## What's Already Implemented ✅

### Backend Infrastructure (COMPLETE)
- ✅ `tasks/gap_filling.py:363` - `fetch_position_ohlc_data()` Celery task with:
  - Smart gap detection (only downloads missing data)
  - Both specific AND continuous contract fetching
  - API quota checking and management
  - Retry logic with exponential backoff
  - Comprehensive logging

- ✅ `routes/positions.py:25` - `_trigger_position_data_fetch()` helper with:
  - Date range padding (entry - 4h to exit + 1h)
  - Priority timeframes: 1m, 5m, 15m, 1h
  - Batch processing for multiple positions
  - Error handling that doesn't fail imports

- ✅ `routes/chart_data.py:104` - Continuous contract fallback:
  - Falls back from specific (MNQ MAR26) to continuous (MNQ)
  - Returns metadata about fallback usage
  - Cache-only mode (never triggers API calls)

- ✅ `services/enhanced_position_service_v2.py:337-340` - Returns position_ids:
  ```python
  return {
      'positions_created': positions_created,
      'position_ids': position_ids,
      'validation_errors': validation_errors
  }
  ```

## The 3 Critical Gaps 🔴

### Gap #1: Import Services Discard Position IDs

**NinjaTrader Import Service** (`services/ninjatrader_import_service.py`)

**Line 1051:** Calls rebuild but discards result
```python
for account, instrument in affected_combinations:
    self._rebuild_positions_for_account_instrument(account, instrument)
    # ❌ Result with position_ids is discarded!
```

**Line 1081-1091:** Returns result without position_ids
```python
return {
    'success': True,
    'executions_imported': new_executions,
    # ... other fields ...
    # ❌ No 'position_ids' field!
}
```

**Impact:** When NinjaTrader executions are imported:
1. ✅ Executions are saved to database
2. ✅ Positions are rebuilt successfully
3. ✅ Position IDs are generated
4. ❌ Position IDs are immediately thrown away
5. ❌ OHLC fetch is never triggered
6. ❌ Charts have no data to display

**Same issue in Unified CSV Import Service** - doesn't track or return position_ids

---

### Gap #2: Chart Pages Don't Check for Missing Data

**Position Detail Route** (`routes/positions.py:349-428`)

When a user loads a position detail page:
1. ✅ Position data is loaded from database
2. ✅ Chart date range is calculated
3. ✅ Page is rendered
4. ❌ **No check if OHLC data exists for this date range**
5. ❌ **No trigger to fetch missing data**

**Current behavior:**
```
User opens position 252 → Chart loads → No data → "Loading 0 data..." forever
```

**Expected behavior:**
```
User opens position 252 → Chart loads → No data detected →
Trigger background fetch → Show "Fetching data..." → Data arrives → Chart displays
```

---

### Gap #3: No Manual Fetch Option

**No API endpoint exists** for users to manually trigger OHLC fetch:
- ❌ No `POST /api/positions/<id>/fetch-ohlc` endpoint
- ❌ No "Fetch Data" button in UI
- ❌ No way to retry if automatic fetch fails

**Impact:** If automatic fetching doesn't work, users are completely stuck.

---

## Where OHLC Fetch DOES Work ✅

**CSV Reimport Route** (`routes/positions.py:1089`)
```python
if result['positions_created'] > 0:
    try:
        _trigger_position_data_fetch(result.get('position_ids', []))
    except Exception as e:
        logger.warning(f"Failed to trigger OHLC data fetch for positions: {e}")
```

This is why **CSV reimports work** but normal imports don't!

---

## Data Flow Analysis

### Current Flow (BROKEN)

```
NinjaTrader CSV arrives
↓
ninjatrader_import_service.process_csv_file()
↓
_process_executions() - saves trades to DB
↓
FOR EACH (account, instrument):
  _rebuild_positions_for_account_instrument()
  ↓
  EnhancedPositionServiceV2.rebuild_positions_for_account_instrument()
  ↓
  _process_trades_for_instrument()
  ↓
  Returns: {positions_created: 5, position_ids: [100,101,102,103,104]}
  ↓
  ❌ RETURN VALUE DISCARDED
↓
Return result without position_ids
↓
❌ OHLC fetch never triggered
```

### What Should Happen (FIXED)

```
NinjaTrader CSV arrives
↓
ninjatrader_import_service.process_csv_file()
↓
_process_executions() - saves trades to DB
↓
all_position_ids = []
FOR EACH (account, instrument):
  result = _rebuild_positions_for_account_instrument()
  all_position_ids.extend(result.get('position_ids', []))  # ✅ COLLECT IDs
↓
Return result WITH position_ids
↓
routes/ninjatrader.py receives position_ids
↓
✅ _trigger_position_data_fetch(position_ids)
↓
✅ Celery task fetch_position_ohlc_data.delay() queued
↓
✅ Background worker fetches OHLC data
↓
✅ Chart displays data
```

---

## Chart Loading Flow

### Current Flow (BROKEN)

```
User visits /positions/252
↓
routes/positions.py:position_detail()
↓
Load position from DB
Calculate chart date range
↓
Render template with chart component
↓
Frontend PriceChart.js loads
↓
Calls /api/chart-data/MNQ%20MAR26?timeframe=1m
↓
routes/chart_data.py:get_chart_data()
↓
Line 107: "This endpoint NEVER triggers Yahoo Finance API calls"
↓
Line 142: No data for specific contract
↓
Line 143-152: Try continuous contract fallback
↓
Line 182-190: If still no data, return empty response
↓
Frontend receives: {data: [], count: 0, success: true}
↓
Chart displays: "Loading 0 data..." forever
↓
❌ User sees empty chart
```

### What Should Happen (FIXED)

```
User visits /positions/252
↓
routes/positions.py:position_detail()
↓
Load position from DB
Calculate chart date range
↓
✅ Check if OHLC data exists for this instrument + date range
↓
IF data missing:
  ✅ Trigger high-priority OHLC fetch task
  ✅ Show "Fetching data..." message in UI
  ✅ Add "manual fetch" button as fallback
↓
Render template with chart component
↓
... normal chart loading ...
↓
✅ Data available → Chart displays successfully
```

---

## Test Evidence

### What We Know Works

From commit history:
- ✅ bd2d9a3: "Fix candle chart display issues with timeframe validation and data fallback"
  - 9 files changed, 884 insertions, 88 deletions
  - Enhanced gap_filling.py with smart fetching
  - Added continuous contract fallback
  - Improved chart data APIs

### What's Still Broken

From git status and handoff docs:
- ❌ Charts still showing "Loading 0 data..." for recent positions
- ❌ Users reporting missing chart data
- ❌ Timeframe dropdown issues persist

---

## The Solution (3-Part Fix)

### Fix #1: Collect Position IDs in Import Services

**File:** `services/ninjatrader_import_service.py:1049-1052`

**Before:**
```python
for account, instrument in affected_combinations:
    self._rebuild_positions_for_account_instrument(account, instrument)
```

**After:**
```python
all_position_ids = []
for account, instrument in affected_combinations:
    result = self._rebuild_positions_for_account_instrument(account, instrument)
    all_position_ids.extend(result.get('position_ids', []))
```

**File:** `services/ninjatrader_import_service.py:1081-1091`

**Before:**
```python
return {
    'success': True,
    'executions_imported': new_executions,
    # ... other fields ...
}
```

**After:**
```python
return {
    'success': True,
    'executions_imported': new_executions,
    'position_ids': all_position_ids,  # ✅ ADD THIS
    # ... other fields ...
}
```

**Same changes needed in:** `services/unified_csv_import_service.py`

---

### Fix #2: Add On-Demand Fetch to Position Detail Route

**File:** `routes/positions.py:349` (after line 375)

**Add:**
```python
# Check if we need to fetch OHLC data for this position's chart
if date_range:
    from tasks.gap_filling import needs_ohlc_data
    instrument = position.get('instrument')

    if needs_ohlc_data(instrument, chart_start_date, chart_end_date):
        logger.info(f"Triggering on-demand OHLC fetch for position {position_id}")
        try:
            _trigger_position_data_fetch([position_id])
        except Exception as e:
            logger.warning(f"Failed to trigger on-demand OHLC fetch: {e}")
```

**New helper function needed in:** `tasks/gap_filling.py`
```python
def needs_ohlc_data(instrument: str, start_date: str, end_date: str,
                    timeframe: str = '1m') -> bool:
    """
    Check if we have OHLC data for the given instrument and date range.

    Returns True if data is missing or incomplete.
    """
    # Implementation: Query ohlc_data table for coverage
    # Return True if gaps exist
```

---

### Fix #3: Add Manual Fetch Endpoint + UI Button

**File:** `routes/chart_data.py` (new endpoint)

```python
@chart_data_bp.route('/api/positions/<int:position_id>/fetch-ohlc', methods=['POST'])
def trigger_manual_ohlc_fetch(position_id):
    """
    Manual trigger for OHLC data fetch.
    Allows users to explicitly request data download for a position.
    """
    try:
        from routes.positions import _trigger_position_data_fetch

        _trigger_position_data_fetch([position_id])

        return jsonify({
            'success': True,
            'message': 'OHLC data fetch triggered',
            'position_id': position_id
        })
    except Exception as e:
        logger.error(f"Manual OHLC fetch failed for position {position_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

**File:** `templates/positions/detail.html` (add button near chart)

```html
<button id="fetch-ohlc-btn" class="btn btn-sm btn-secondary"
        onclick="fetchOhlcData({{ position.id }})">
    Fetch Chart Data
</button>

<script>
function fetchOhlcData(positionId) {
    fetch(`/api/positions/${positionId}/fetch-ohlc`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('Data fetch started. Refresh page in 30 seconds.');
            } else {
                alert('Fetch failed: ' + data.error);
            }
        });
}
</script>
```

---

## Implementation Priority

### Critical (Must Fix for Basic Functionality)
1. **Fix #1** - Collect position_ids in import services
   - Files: `ninjatrader_import_service.py`, `unified_csv_import_service.py`
   - Lines: ~20 line changes total
   - Impact: Enables automatic fetch on import

2. **Fix #2** - Add on-demand fetch to position detail page
   - Files: `routes/positions.py`, `tasks/gap_filling.py`
   - Lines: ~30 lines total
   - Impact: Charts fetch data when viewed

### Important (Better UX)
3. **Fix #3** - Add manual fetch button
   - Files: `routes/chart_data.py`, `templates/positions/detail.html`
   - Lines: ~40 lines total
   - Impact: User escape hatch if auto-fetch fails

---

## Testing Strategy

### Unit Tests Needed
1. Test `_process_executions()` returns position_ids
2. Test `needs_ohlc_data()` correctly detects gaps
3. Test manual fetch endpoint returns success

### Integration Tests Needed
1. Import NinjaTrader CSV → verify OHLC fetch triggered
2. Load position detail page with missing data → verify fetch triggered
3. Click "Fetch Data" button → verify fetch triggered

### End-to-End Test
1. Delete all OHLC data for MNQ
2. Import fresh NinjaTrader executions
3. Verify:
   - ✅ Positions created
   - ✅ OHLC fetch triggered automatically
   - ✅ Data downloaded in background
4. Navigate to position detail page
5. Verify:
   - ✅ Chart loads with data
   - ✅ No "Loading 0 data..." message

---

## Estimated Effort

- **Fix #1:** 30 minutes (collect position_ids)
- **Fix #2:** 1 hour (on-demand fetch logic + helper)
- **Fix #3:** 45 minutes (API endpoint + UI button)
- **Testing:** 1 hour (verify all 3 triggers work)

**Total:** ~3-4 hours for complete fix

---

## Related Files

### Core Implementation
- `services/ninjatrader_import_service.py` - NinjaTrader import
- `services/unified_csv_import_service.py` - CSV import
- `services/enhanced_position_service_v2.py` - Position building (already correct)
- `routes/positions.py` - Position routes and trigger helper
- `tasks/gap_filling.py` - OHLC fetch task (already correct)
- `routes/chart_data.py` - Chart data API

### UI Files
- `templates/positions/detail.html` - Position detail page
- `static/js/PriceChart.js` - Chart component

### Configuration
- `docker-compose.yml` - Celery workers (already configured)
- `tasks/__init__.py` - Celery task registration

---

## Conclusion

The **infrastructure is 95% complete**. The OHLC fetching system works perfectly - we just need to **connect the dots** by:

1. Collecting position IDs from imports
2. Triggering fetch when charts need data
3. Adding a manual fallback option

All three fixes are **small, focused changes** to existing code. No major refactoring required.
