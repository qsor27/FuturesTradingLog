# Task Breakdown: Fix Candle Chart Display on Position Pages

## Investigation Status ✅

**Investigation Complete:** `docs/CHART_DATA_FETCH_INVESTIGATION.md`

**Root Cause Identified:** The OHLC fetching infrastructure is 95% complete but has 3 critical gaps preventing automatic data downloads.

---

## What's Already Implemented ✅

### Backend Infrastructure (COMPLETE)
- ✅ **Continuous Contract Fallback** - `routes/chart_data.py:142-152`
  - Falls back from specific contracts (MNQ MAR26) to continuous (MNQ)
  - Returns fallback metadata: `is_continuous_fallback`, `requested_instrument`, `actual_instrument`
  - Works correctly in production

- ✅ **Smart OHLC Fetch Task** - `tasks/gap_filling.py:363`
  - `fetch_position_ohlc_data()` Celery task with:
    - Smart gap detection (only downloads missing data)
    - Both specific AND continuous contract fetching
    - API quota checking and management
    - Retry logic with exponential backoff
    - Priority timeframes: 1m, 5m, 15m, 1h

- ✅ **Trigger Helper Function** - `routes/positions.py:25`
  - `_trigger_position_data_fetch(position_ids)` with:
    - Date range padding (entry - 4h to exit + 1h)
    - Batch processing for multiple positions
    - Error handling that doesn't fail imports

- ✅ **Position Service Returns IDs** - `services/enhanced_position_service_v2.py:337-340`
  ```python
  return {
      'positions_created': positions_created,
      'position_ids': position_ids,  # ✅ Already returns this!
      'validation_errors': validation_errors
  }
  ```

- ✅ **Celery Workers in Docker** - `docker-compose.yml`
  - celery-worker and celery-beat services configured
  - Scheduled gap-filling tasks running
  - Redis broker connected

### Frontend Infrastructure (MOSTLY COMPLETE)
- ✅ **Chart Component** - `static/js/PriceChart.js`
  - TradingView Lightweight Charts integration
  - Execution arrow overlays
  - Timeframe management (needs fixes)
  - Loading states (needs improvement)

---

## The 3 Critical Gaps 🔴

### Gap #1: Import Services Discard Position IDs
**File:** `services/ninjatrader_import_service.py`

**Problem:** Lines 1049-1052 and 1081-1091
```python
# Line 1051: Rebuilds positions but discards result
for account, instrument in affected_combinations:
    self._rebuild_positions_for_account_instrument(account, instrument)  # ❌ Result discarded

# Line 1081: Returns result without position_ids
return {
    'success': True,
    'executions_imported': new_executions,
    # ❌ No 'position_ids' field!
}
```

**Impact:** Position IDs are generated but immediately thrown away, so OHLC fetch is never triggered.

**Same issue in:** `services/unified_csv_import_service.py`

---

### Gap #2: Chart Pages Don't Check for Missing Data
**File:** `routes/positions.py`

**Problem:** Line 349 - Position detail route
- Loads position data ✅
- Calculates chart date range ✅
- Renders page ✅
- ❌ **Never checks if OHLC data exists**
- ❌ **Never triggers fetch for missing data**

**Impact:** Users see "Loading 0 data..." forever with no automatic fetch attempt.

---

### Gap #3: No Manual Fetch Option
**Files:** `routes/chart_data.py`, `templates/positions/detail.html`

**Problem:**
- ❌ No `POST /api/positions/<id>/fetch-ohlc` endpoint
- ❌ No "Fetch Data" button in UI
- ❌ Users stuck if automatic fetch doesn't work

---

## Task List (3 Groups, ~10 Tasks Total)

### Task Group 1: Fix Import Services to Return Position IDs
**Estimated Time:** 45 minutes
**Dependencies:** None

- [x] 1.1 Fix NinjaTrader import to collect and return position IDs
  - **File:** `services/ninjatrader_import_service.py`
  - **Line 1049:** Before the loop, initialize `all_position_ids = []`
  - **Line 1051:** Change to:
    ```python
    result = self._rebuild_positions_for_account_instrument(account, instrument)
    all_position_ids.extend(result.get('position_ids', []))
    ```
  - **Line 1081:** Add to return dict:
    ```python
    'position_ids': all_position_ids,
    ```
  - **Test:** Import NinjaTrader CSV and verify position_ids in result

- [x] 1.2 Fix unified CSV import to collect and return position IDs
  - **File:** `services/unified_csv_import_service.py`
  - Find where positions are rebuilt (search for `rebuild_positions` or `process_trades`)
  - Apply same pattern: collect position_ids and return them
  - **Test:** Import CSV and verify position_ids in result

- [x] 1.3 Connect import results to trigger function
  - **File:** Routes that call the import services
  - After successful import with `positions_created > 0`:
    ```python
    if result.get('positions_created', 0) > 0:
        _trigger_position_data_fetch(result.get('position_ids', []))
    ```
  - Already done for CSV reimport at `routes/positions.py:1089`
  - Check other import routes (NinjaTrader import route, etc.)

**Acceptance Criteria:**
- Position imports return `position_ids` in result dict
- `_trigger_position_data_fetch()` is called with collected position IDs
- OHLC fetch tasks are queued in Celery after import
- Log messages confirm fetch tasks were triggered

---

### Task Group 2: Add On-Demand Fetch to Chart Pages
**Estimated Time:** 1.5 hours
**Dependencies:** None

- [x] 2.1 Create helper function to check for missing OHLC data
  - **File:** `tasks/gap_filling.py` (add new function)
  - **Function:** `needs_ohlc_data(instrument: str, start_date: str, end_date: str, timeframe: str = '1m') -> bool`
  - **Logic:**
    ```python
    # Query ohlc_data table for coverage in date range
    # Try both specific contract and continuous contract
    # Return True if significant gaps exist (e.g., >10% missing)
    ```
  - **Test:** Call with known missing and existing data ranges

- [x] 2.2 Add data check to position detail route
  - **File:** `routes/positions.py`
  - **Location:** After line 375 (after chart date range is calculated)
  - **Code:**
    ```python
    # Check if we need to fetch OHLC data for this position's chart
    if date_range:
        from tasks.gap_filling import needs_ohlc_data
        instrument = position.get('instrument')

        if needs_ohlc_data(instrument, chart_start_date, chart_end_date):
            logger.info(f"Position {position_id}: Missing OHLC data, triggering fetch")
            try:
                _trigger_position_data_fetch([position_id])
                # Add flag to template to show "Fetching data..." message
                position['ohlc_fetch_triggered'] = True
            except Exception as e:
                logger.warning(f"Failed to trigger on-demand OHLC fetch: {e}")
    ```
  - **Test:** Visit position page with missing data, verify fetch triggered

- [x] 2.3 Add "Fetching data..." notice to template
  - **File:** `templates/positions/detail.html`
  - Near the chart container, add:
    ```html
    {% if position.ohlc_fetch_triggered %}
    <div class="alert alert-info">
      📊 Fetching market data for chart... This may take 30-60 seconds.
      <a href="javascript:location.reload()">Refresh page</a> after waiting.
    </div>
    {% endif %}
    ```
  - **Test:** Verify notice appears when fetch is triggered

**Acceptance Criteria:**
- `needs_ohlc_data()` accurately detects missing data
- Position detail route triggers fetch when data is missing
- User sees informative message about ongoing fetch
- After ~60 seconds and page refresh, chart displays data

---

### Task Group 3: Add Manual Fetch Endpoint and Button
**Estimated Time:** 1 hour
**Dependencies:** None

- [x] 3.1 Create manual fetch API endpoint
  - **File:** `routes/chart_data.py`
  - **Add new route:**
    ```python
    @chart_data_bp.route('/api/positions/<int:position_id>/fetch-ohlc', methods=['POST'])
    def trigger_manual_ohlc_fetch(position_id):
        """
        Manual trigger for OHLC data fetch.
        Allows users to explicitly request data download for a position.
        """
        try:
            from routes.positions import _trigger_position_data_fetch

            logger.info(f"Manual OHLC fetch requested for position {position_id}")
            _trigger_position_data_fetch([position_id])

            return jsonify({
                'success': True,
                'message': 'OHLC data fetch triggered. Refresh page in 30-60 seconds.',
                'position_id': position_id
            })
        except Exception as e:
            logger.error(f"Manual OHLC fetch failed for position {position_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    ```
  - **Test:** Call endpoint with curl/Postman, verify Celery task queued

- [x] 3.2 Add "Fetch Data" button to position detail page
  - **File:** `templates/positions/detail.html`
  - **Location:** Near the chart container (e.g., in chart header or below chart)
  - **Add button:**
    ```html
    <button id="fetch-ohlc-btn" class="btn btn-sm btn-secondary"
            onclick="fetchOhlcData({{ position.id }})"
            title="Download market data for this position's chart">
      📥 Fetch Chart Data
    </button>

    <script>
    function fetchOhlcData(positionId) {
        const btn = document.getElementById('fetch-ohlc-btn');
        btn.disabled = true;
        btn.textContent = 'Fetching...';

        fetch(`/api/positions/${positionId}/fetch-ohlc`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('✅ Data fetch started!\n\n' + data.message);
                // Automatically refresh page after 45 seconds
                setTimeout(() => location.reload(), 45000);
            } else {
                alert('❌ Fetch failed: ' + data.error);
                btn.disabled = false;
                btn.textContent = '📥 Fetch Chart Data';
            }
        })
        .catch(err => {
            alert('❌ Request failed: ' + err);
            btn.disabled = false;
            btn.textContent = '📥 Fetch Chart Data';
        });
    }
    </script>
    ```
  - **Test:** Click button, verify alert, wait 60s, verify data appears

- [x] 3.3 Button always visible (manual trigger available regardless of data state)
  - **File:** `templates/positions/detail.html`
  - **Wrap button:**
    ```html
    {% if position.ohlc_data_missing or not position.chart_data_available %}
    <!-- button here -->
    {% endif %}
    ```
  - **File:** `routes/positions.py` (set flag)
  - In position detail route, check if data exists and set `position['chart_data_available']`
  - **Test:** Verify button only shows when needed

**Acceptance Criteria:**
- Manual fetch endpoint works and queues Celery task
- Button appears on position detail pages with missing data
- Clicking button triggers fetch and shows confirmation
- User can manually retry if automatic fetch fails

---

## Integration Testing

### Task Group 4: End-to-End Verification
**Estimated Time:** 1 hour
**Dependencies:** Task Groups 1, 2, 3

- [ ] 4.1 Test automatic fetch on import
  - **Setup:** Delete all OHLC data for a test instrument
  - **Action:** Import NinjaTrader executions or CSV with trades
  - **Verify:**
    - ✅ Import succeeds
    - ✅ Positions are created
    - ✅ Celery task `fetch_position_ohlc_data` is queued
    - ✅ Task executes within 60 seconds
    - ✅ OHLC data is downloaded
    - ✅ Visit position page → chart displays data

- [ ] 4.2 Test on-demand fetch when viewing chart
  - **Setup:** Create position with missing OHLC data
  - **Action:** Visit position detail page
  - **Verify:**
    - ✅ `needs_ohlc_data()` returns True
    - ✅ Fetch task is triggered automatically
    - ✅ "Fetching data..." notice appears
    - ✅ After 60s and refresh, chart displays data

- [ ] 4.3 Test manual fetch button
  - **Setup:** Position with missing data
  - **Action:** Click "Fetch Chart Data" button
  - **Verify:**
    - ✅ API endpoint called successfully
    - ✅ Celery task queued
    - ✅ User sees confirmation alert
    - ✅ After 60s, data available and chart displays

- [ ] 4.4 Test continuous contract fallback
  - **Setup:** Position with specific contract (e.g., MNQ MAR26)
  - **Action:** Ensure specific contract has no data, but continuous contract (MNQ) does
  - **Verify:**
    - ✅ Chart API falls back to continuous contract
    - ✅ Response includes `is_continuous_fallback: true`
    - ✅ Chart displays data from continuous contract
    - ✅ (Optional) Fallback notice appears in UI

- [ ] 4.5 Test all three triggers work together
  - **Setup:** Fresh database with no OHLC data
  - **Action:**
    1. Import trades (should trigger fetch #1)
    2. Visit position page before fetch completes (should trigger fetch #2)
    3. Click manual button (should trigger fetch #3)
  - **Verify:**
    - ✅ Only one fetch task is queued (deduplication)
    - ✅ Data is fetched successfully
    - ✅ Chart displays correctly

**Acceptance Criteria:**
- All 3 triggers successfully queue OHLC fetch tasks
- OHLC data is downloaded and stored in database
- Charts display data after fetch completes
- No duplicate fetch tasks for same position/date range
- **PRIMARY CONCERN MET:** 100% certainty charts will fetch needed data

---

## Summary

### Total Tasks: ~15 tasks across 4 groups

**Implementation Order:**
1. Task Group 1 (45 min) - Fix import services
2. Task Group 2 (1.5 hr) - Add on-demand fetch to charts
3. Task Group 3 (1 hr) - Add manual fetch button
4. Task Group 4 (1 hr) - Integration testing

**Total Estimated Time:** ~4-5 hours

---

## Critical Success Metrics

1. ✅ **Import Trigger:** Importing trades automatically fetches OHLC data
2. ✅ **Chart Trigger:** Viewing a chart with missing data triggers fetch
3. ✅ **Manual Trigger:** User can manually trigger fetch with button
4. ✅ **Continuous Fallback:** Charts fall back to continuous contract when specific contract lacks data
5. ✅ **100% Certainty:** All three mechanisms tested and verified working

---

## Files to Modify

### Backend (Python)
- `services/ninjatrader_import_service.py` - Collect position IDs
- `services/unified_csv_import_service.py` - Collect position IDs
- `routes/positions.py` - On-demand fetch in detail route
- `routes/chart_data.py` - Manual fetch endpoint
- `tasks/gap_filling.py` - Add `needs_ohlc_data()` helper

### Frontend (HTML/JS)
- `templates/positions/detail.html` - Add fetch button and notices

### Total Files: 6 files
### Total Lines Changed: ~150 lines (mostly additions)

---

## What's NOT Needed

The following from the original task list are **already complete**:
- ❌ Continuous contract fallback implementation (done)
- ❌ Smart gap detection (done)
- ❌ API quota management (done)
- ❌ Retry logic with exponential backoff (done)
- ❌ Celery worker Docker configuration (done)
- ❌ Scheduled gap-filling tasks (done)
- ❌ Position service returns position IDs (done)
- ❌ Trigger helper function (done)

We only need to **connect the existing pieces** with 3 focused fixes.
