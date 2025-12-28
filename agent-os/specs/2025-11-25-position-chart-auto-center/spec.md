# Specification: Position Chart Auto-Centering

## Goal
Automatically center the position detail page chart on the actual date range when the position was open (entry to exit), rather than showing recent candles, ensuring execution arrows are always visible and properly contextualized within the trade timeline.

## User Stories
- As a trader, I want the chart to automatically show the date range when my position was active so that I can see the full market context for that specific trade
- As a trader reviewing closed positions, I want to see some padding before entry and after exit so that I can understand the market setup and aftermath

## Specific Requirements

**Calculate Auto-Centered Date Range from Position Timestamps**
- Extract `entry_time` and `exit_time` from Position model (both are datetime fields)
- For closed positions: Calculate date range from `entry_time` to `exit_time`
- For open positions: Calculate date range from `entry_time` to current time
- Apply padding: 15% of total position duration before entry, 15% after exit (minimum 1 hour padding for very short trades)
- Handle edge cases: positions under 1 hour duration get 2-hour padding, positions over 30 days get 20% padding

**Extend Chart Data API to Support Explicit Date Ranges**
- Modify `/api/chart-data/<instrument>` endpoint in `routes/chart_data.py`
- Add support for `start_date` and `end_date` query parameters (ISO format strings)
- Keep existing `days` parameter for backward compatibility
- Date parameters take precedence over `days` parameter when both provided
- Parse date strings using `datetime.fromisoformat()` for consistency

**Calculate Date Range in Position Detail Route**
- Modify `position_detail()` function in `routes/positions.py` (around line 100-155)
- After loading position data, calculate optimal chart date range
- Formula: `padding_duration = max(timedelta(hours=1), (exit_time - entry_time) * 0.15)`
- For closed: `start_date = entry_time - padding_duration`, `end_date = exit_time + padding_duration`
- For open: `start_date = entry_time - padding_duration`, `end_date = datetime.now()`
- Pass calculated `chart_start_date` and `chart_end_date` to template context

**Update Position Detail Template to Use Date Range**
- Modify `templates/positions/detail.html` (lines 293-299 where chart variables are set)
- Add `chart_start_date` and `chart_end_date` template variables
- Format dates as ISO strings for JavaScript consumption
- Pass dates to price_chart.html component via new parameters

**Update Chart Component to Accept Date Parameters**
- Modify `templates/components/price_chart.html` to accept optional date parameters
- Add `chart_start_date` and `chart_end_date` variables with defaults to None
- Pass dates as data attributes to chart container div
- Update chart initialization script to use date range if provided

**Modify PriceChart.js Date Handling**
- Update `static/js/PriceChart.js` to read date range from data attributes
- Modify API call construction to include `start_date` and `end_date` parameters when available
- Ensure proper date serialization when building API URL query string
- Maintain backward compatibility with existing `days` parameter usage

**Edge Case Handling**
- Very short trades (< 1 hour): Force minimum 2-hour total window (1 hour before, 1 hour after)
- Very long trades (> 30 days): Cap padding at 20% to avoid excessive data loading
- Open positions with no exit_time: Use current timestamp as end boundary
- Missing entry_time: Fallback to default 7-day recent view with warning log
- Trades with future timestamps: Validate and cap to current time

**Preserve Existing Chart Functionality**
- Manual timeframe selection remains functional
- Manual zoom and pan capabilities unaffected
- Volume toggle continues to work
- Execution arrow rendering preserved
- Chart settings API integration maintained

## Out of Scope
- Modifying chart timeframe selection logic based on position duration
- Implementing chart presets or saved chart views
- Adding position duration indicators or timeline markers
- Creating chart annotation tools for manual marking
- Building chart comparison between multiple positions
- Implementing automated chart screenshot capture
- Adding real-time price updates for open positions
- Creating chart export functionality (PDF, image)
- Building chart sharing features
- Implementing advanced technical indicators on the chart
