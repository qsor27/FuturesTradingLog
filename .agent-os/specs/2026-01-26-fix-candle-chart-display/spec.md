# Spec Requirements Document

> Spec: Fix Candle Chart Display on Position Pages
> Created: 2026-01-26

## Overview

Fix multiple issues with the candle/OHLC chart display on position detail pages that prevent charts from loading properly and cause timeframe switching to fail. The chart should display up-to-the-minute market data for the position's execution timeframe and allow seamless timeframe switching.

## User Stories

### Viewing Market Context for Recent Trades

As a trader, I want to see the market context chart when viewing my position details, so that I can analyze my entry and exit points against price action.

When I open a position detail page for a recent trade (e.g., position 252 from January 26, 2026), the chart should:
1. Load candle data covering the position's execution times
2. Display the data without getting stuck on "Loading" state
3. Allow me to switch between timeframes (1m, 5m, 15m, 1h, etc.)
4. Show execution arrows overlaid on the correct candles

**Current Problem:** The chart shows "Loading 0 data..." and never displays candles because the specific contract (MNQ MAR26) lacks data for recent dates, while the continuous contract (MNQ) has the data.

### Switching Timeframes

As a trader, I want to switch between different timeframes to analyze my trade at various granularities, so that I can see both the micro-level execution context (1m) and broader market structure (1h, 4h).

**Current Problem:**
- The timeframe dropdown initializes with value "0" (invalid) instead of a valid timeframe
- Timeframe changes are blocked while the chart is loading, causing user clicks to be ignored
- The dropdown shows data counts from continuous contract but fetches from specific contract

## Spec Scope

1. **Continuous Contract Fallback** - When a specific contract (e.g., MNQ MAR26) lacks data for the requested date range, automatically fall back to the continuous contract (MNQ) and display a notice to the user

2. **Fix Initial Timeframe Selection** - Ensure the chart initializes with a valid default timeframe (e.g., "1m" or "1h") instead of "0", and properly sync the dropdown with the actual timeframe being loaded

3. **Fix Timeframe Switching During Load** - Queue timeframe change requests that occur during loading instead of silently ignoring them, or allow switching to cancel the current load and start a new one

4. **Consistent Instrument Resolution** - Ensure both the available-timeframes API and chart-data API use the same instrument resolution logic, so dropdown counts match actual available data

5. **Improve Loading State UX** - Show more informative loading messages and properly handle the transition between timeframes

6. **Position-Triggered Data Fetching** - Automatically fetch OHLC data when new positions are imported, ensuring charts always have data for traded positions

7. **Celery Workers in Docker** - Add Celery worker and beat services to Docker stack for reliable scheduled gap-filling during market hours

## Out of Scope

- Adding new external data sources beyond Yahoo Finance
- Real-time streaming data (WebSocket feeds)
- Performance optimization of chart rendering
- Mobile-specific UI improvements

## Expected Deliverable

1. Position detail page charts load successfully for recent positions, displaying candle data from the continuous contract when specific contract data is unavailable

2. Timeframe dropdown initializes with a valid default value and all timeframe switches work correctly without getting stuck

3. User sees a clear indicator when viewing continuous contract data instead of specific contract data (e.g., "Showing MNQ data - MNQ MAR26 data unavailable for this date range")

4. When a new position is imported, OHLC data for that position's time range is automatically fetched within 2 minutes

5. Celery workers run reliably as part of the Docker stack, maintaining data freshness during market hours
