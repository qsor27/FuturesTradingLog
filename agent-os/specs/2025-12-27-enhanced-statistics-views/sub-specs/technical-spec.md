# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-12-27-enhanced-statistics-views/spec.md

## Technical Requirements

### Data Source

All statistics will be calculated from the `positions` table, using closed positions (`position_status = 'CLOSED'`). This aligns with the product's position-based architecture.

**Position fields used:**
- `entry_time` - For date/time grouping
- `position_type` - LONG or SHORT classification
- `total_dollars_pnl` - For win/loss determination and P&L calculations
- `total_points_pnl` - For points-based metrics
- `total_commission` - For commission tracking
- `instrument` - For instrument breakdown
- `account` - For account filtering

### Metric Calculations

#### Daily View Metrics

| Metric | Calculation | Visual Type |
|--------|-------------|-------------|
| Position Count | COUNT of positions with entry_time on selected date | None (text only) |
| Win Rate | (positions with total_dollars_pnl > 0) / total positions * 100 | Gauge/Donut |
| Long % | (LONG positions / total positions) * 100 | Pie chart |
| Short % | (SHORT positions / total positions) * 100 | Pie chart |
| Long Win Rate | (winning LONG positions / total LONG positions) * 100 | Horizontal bar |
| Short Win Rate | (winning SHORT positions / total SHORT positions) * 100 | Horizontal bar |
| Best Position | MAX(total_dollars_pnl) | None (text only) |
| Worst Position | MIN(total_dollars_pnl) | None (text only) |
| Avg Points/Position | AVG(total_points_pnl) | None (text only) |
| Profit Factor | SUM(winning pnl) / ABS(SUM(losing pnl)) | None (text only) |
| Total P&L | SUM(total_dollars_pnl) | None (text only) |

#### Weekly View Metrics

| Metric | Calculation | Visual Type |
|--------|-------------|-------------|
| Win Rate by Day | Win rate calculated per day (Mon-Fri) of selected week | Bar chart |
| Best Trading Day | Day with highest win rate in week | None (text only) |
| Worst Trading Day | Day with lowest win rate in week | None (text only) |
| Weekly Position Count | Total positions for the week | None (text only) |
| Long % (Weekly) | (LONG positions / total weekly positions) * 100 | Pie chart |
| Short % (Weekly) | (SHORT positions / total weekly positions) * 100 | Pie chart |
| Long Win Rate (Weekly) | Win rate for all LONG positions in week | Horizontal bar |
| Short Win Rate (Weekly) | Win rate for all SHORT positions in week | Horizontal bar |
| Instrument Breakdown | Position count and P&L per instrument | Bar chart |
| Weekly Total P&L | SUM(total_dollars_pnl) for week | None (text only) |
| Weekly Profit Factor | Weekly gross profit / Weekly gross loss | None (text only) |

#### Monthly View Metrics

| Metric | Calculation | Visual Type |
|--------|-------------|-------------|
| Week-over-Week Performance | Win rate and P&L per week within month | Line chart |
| Best Week | Week with highest P&L in month | None (text only) |
| Worst Week | Week with lowest P&L in month | None (text only) |
| Monthly Position Count | Total positions for the month | None (text only) |
| Avg Positions/Day | Monthly position count / trading days | None (text only) |
| Long % (Monthly) | Monthly LONG percentage | Pie chart |
| Short % (Monthly) | Monthly SHORT percentage | Pie chart |
| Long Win Rate (Monthly) | Win rate for all LONG positions in month | Horizontal bar |
| Short Win Rate (Monthly) | Win rate for all SHORT positions in month | Horizontal bar |
| vs Previous Month | P&L difference from previous month | Comparison bar |
| Monthly Total P&L | SUM(total_dollars_pnl) for month | None (text only) |
| Monthly Profit Factor | Monthly gross profit / Monthly gross loss | None (text only) |

### UI/UX Specifications

#### Visual Toggle Component

Each toggleable statistic will have:
- A header row with the metric name and value (always visible)
- A toggle button/icon (chart icon) on the right side
- When toggled: an expandable area below showing the chart
- Charts use TradingView Lightweight Charts or Chart.js for consistency

```html
<div class="stat-card">
  <div class="stat-header">
    <span class="stat-label">Win Rate</span>
    <span class="stat-value">68.5%</span>
    <button class="stat-toggle" data-target="winrate-chart">
      <i class="bi bi-bar-chart"></i>
    </button>
  </div>
  <div class="stat-chart collapse" id="winrate-chart">
    <!-- Chart renders here -->
  </div>
</div>
```

#### Layout Structure

- Statistics organized into logical card groups
- Responsive grid layout (Bootstrap 5)
- Mobile-friendly collapse behavior
- Cards should match existing dashboard styling

#### Color Scheme

- Winning metrics: Green (#28a745 or existing theme success color)
- Losing metrics: Red (#dc3545 or existing theme danger color)
- Neutral metrics: Default text color
- Charts use consistent color palette from existing TradingView integration

### Performance Requirements

- Statistics calculation should complete within 100ms for typical data volumes
- Chart rendering should not block the main thread
- Consider caching frequently accessed aggregations in Redis
- Lazy-load chart libraries only when visual toggle is activated

### Integration Points

- Extend `StandardizedStatisticsCalculator` class with new methods
- Add new API endpoints for chart data (see api-spec.md)
- Reuse existing account filter functionality
- Integrate with existing statistics.html template structure
