# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2026-01-26-fix-candle-chart-display/spec.md

## Technical Requirements

### 1. Instrument Resolution & Fallback Logic

**Location:** `routes/chart_data.py` and `services/instrument_mapper.py`

- Modify `/api/chart-data/<instrument>` endpoint to implement fallback logic:
  1. First attempt to fetch data for the requested specific contract (e.g., "MNQ MAR26")
  2. If no data exists for the requested date range, attempt fallback to root/continuous symbol (e.g., "MNQ")
  3. Return metadata indicating whether fallback was used: `is_continuous_fallback: true`
  4. Include both `requested_instrument` and `actual_instrument` in response

- Modify `/api/available-timeframes/<instrument>` endpoint to:
  1. Check data availability for specific contract first
  2. If specific contract has no data for relevant date range, include continuous contract counts
  3. Return `fallback_instrument` field when using continuous data

**Key Function Changes:**
```python
def get_chart_data_with_fallback(instrument, timeframe, start_date, end_date):
    # Try specific contract first
    data = get_ohlc_data(instrument, timeframe, start_date, end_date)
    if data:
        return data, instrument, False

    # Fallback to continuous contract
    root_symbol = get_root_symbol(instrument)  # "MNQ MAR26" -> "MNQ"
    if root_symbol != instrument:
        data = get_ohlc_data(root_symbol, timeframe, start_date, end_date)
        if data:
            return data, root_symbol, True

    return [], instrument, False
```

### 2. Fix Initial Timeframe Selection

**Location:** `static/js/PriceChart.js` and `static/js/ChartSettingsAPI.js`

- In `ChartSettingsAPI.js`, validate stored timeframe values:
  ```javascript
  const VALID_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

  getSettings() {
      const settings = this._loadFromStorage();
      // Validate timeframe
      if (!VALID_TIMEFRAMES.includes(settings.default_timeframe)) {
          settings.default_timeframe = '1h'; // Safe default
      }
      return settings;
  }
  ```

- In `PriceChart.js` constructor, validate the initial timeframe:
  ```javascript
  this.options.timeframe = VALID_TIMEFRAMES.includes(options.timeframe)
      ? options.timeframe
      : '1h';
  ```

- In `templates/components/price_chart.html`, ensure dropdown has valid initial selection

### 3. Fix Timeframe Switching During Loading

**Location:** `static/js/PriceChart.js`

Current problematic code (line ~1620):
```javascript
if (this.isLoading) {
    console.warn('Chart is loading, ignoring timeframe change');
    return;  // PROBLEM: Silently ignores user action
}
```

**Solution Options:**

**Option A: Cancel and restart (Recommended)**
```javascript
async updateTimeframe(newTimeframe) {
    if (this.isLoading && this.loadController) {
        // Cancel current load
        this.loadController.abort();
        console.log('Cancelled previous load for timeframe switch');
    }

    this.options.timeframe = newTimeframe;
    await this.loadData();
}
```

**Option B: Queue the change**
```javascript
async updateTimeframe(newTimeframe) {
    if (this.isLoading) {
        this.pendingTimeframe = newTimeframe;
        console.log('Queued timeframe change:', newTimeframe);
        return;
    }

    this.options.timeframe = newTimeframe;
    await this.loadData();
}

// In loadData completion:
if (this.pendingTimeframe) {
    const pending = this.pendingTimeframe;
    this.pendingTimeframe = null;
    await this.updateTimeframe(pending);
}
```

### 4. UI Feedback for Continuous Contract Fallback

**Location:** `static/js/PriceChart.js` and `templates/components/price_chart.html`

- Add a dismissible warning banner when displaying continuous contract data:
  ```javascript
  showContinuousFallbackWarning(requestedInstrument, actualInstrument) {
      const warningHtml = `
          <div class="chart-warning alert alert-info alert-dismissible" role="alert">
              <i class="bi bi-info-circle"></i>
              Showing ${actualInstrument} data - ${requestedInstrument} data unavailable for this date range
              <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
          </div>
      `;
      this.container.insertAdjacentHTML('beforebegin', warningHtml);
  }
  ```

- Update chart title to reflect actual instrument being displayed

### 5. Consistent Date Range Handling

**Location:** `routes/chart_data.py`

- When `start_date` and `end_date` parameters are provided (position auto-center mode):
  1. Check if data exists for that date range with specific contract
  2. If not, check continuous contract
  3. If neither has data, return helpful error with available date ranges

- Add validation to ensure the API doesn't return data from a completely different time period than requested

## Files to Modify

| File | Changes |
|------|---------|
| `routes/chart_data.py` | Add fallback logic, improve date range handling |
| `services/instrument_mapper.py` | Add/fix `get_root_symbol()` function |
| `static/js/PriceChart.js` | Fix timeframe validation, loading state, fallback UI |
| `static/js/ChartSettingsAPI.js` | Validate stored settings |
| `templates/components/price_chart.html` | Add fallback warning UI container |

## Testing Considerations

1. Test with position that has specific contract data available
2. Test with position that requires continuous contract fallback
3. Test rapid timeframe switching during load
4. Test with invalid stored settings (localStorage with `default_timeframe: "0"`)
5. Test available-timeframes endpoint returns consistent data with chart-data endpoint
