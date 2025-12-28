# Feature Idea: Auto-Center Position Chart on Trade Date Range

## Initial Description
Change the chart on the position page to automatically center the candles on when the position was actually open. For example, if a trade is from 6 months ago, the chart should display candles from 6 months ago (centered on the position's entry and exit times), not just show recent candles from today.

## Problem Statement
Currently, the position detail page chart shows recent candles (default: last 7 days with 1-hour timeframe). This means:
- For historical positions (e.g., closed 6 months ago), the chart shows today's candles where no trading activity occurred
- Users cannot see the actual price action during the position's lifetime
- The execution arrows may be off-screen or not visible
- Users must manually adjust the date range to see when the position was actually open

## Desired Behavior
When viewing a position detail page:
1. Chart should automatically calculate the date range based on the position's `entry_time` and `exit_time`
2. For closed positions: Show candles from entry to exit, with some padding before/after
3. For open positions: Show candles from entry to current time, with padding before entry
4. Execution arrows should be visible and centered in the chart view
5. User should still be able to adjust timeframe and zoom in/out, but initial view should be centered on the trade

## Technical Context
- Position model has `entry_time` (datetime) and `exit_time` (optional datetime)
- Chart component is in `templates/components/price_chart.html`
- Position detail page is `templates/positions/detail.html` (lines 278-300)
- Chart accepts `chart_days` parameter which controls the date range
- Backend API `/api/chart-data/{instrument}` calculates start/end dates based on `days` parameter

## User Impact
- Traders can immediately see the price action during their actual trades
- Better context for reviewing trade decisions
- No manual date adjustment needed for historical positions
- Improved user experience when reviewing past performance
