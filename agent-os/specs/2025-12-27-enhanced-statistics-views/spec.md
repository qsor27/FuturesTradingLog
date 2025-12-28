# Spec Requirements Document

> Spec: Enhanced Statistics Views
> Created: 2025-12-27

## Overview

Enhance the existing statistics page with comprehensive Daily, Weekly, and Monthly views that display position-based trading metrics including trade counts, win rates, long/short breakdowns, and time-based performance patterns. Each statistic will display as simple text with an optional toggle to show a visual chart representation.

## User Stories

### Reviewing Daily Performance

As a trader, I want to see detailed statistics for my trading day, so that I can understand my daily performance patterns and make adjustments.

When I view the Daily statistics tab, I see at a glance: how many positions I took today, my win rate, the breakdown of long vs short positions, and individual win rates for each direction. I can toggle on a visual chart for any metric to see a graphical representation.

### Analyzing Weekly Patterns

As a trader, I want to see my win rate broken down by day of the week, so that I can identify which days I trade best and worst.

When I view the Weekly statistics tab, I see my overall week performance along with a day-by-day breakdown showing win rates for Monday through Friday. I can see the long/short split and identify if I perform better on certain days, helping me optimize my trading schedule.

### Monthly Performance Review

As a trader, I want a monthly overview of my trading performance, so that I can track my progress and consistency over time.

When I view the Monthly statistics tab, I see comprehensive metrics for the month including week-over-week performance, overall long/short analysis, and comparison metrics to identify trends and areas for improvement.

## Spec Scope

1. **Daily Statistics View** - Display position count, win rate, long/short percentage split, long win rate, short win rate, best/worst position, average duration, points per position, and profit factor for the selected day.

2. **Weekly Statistics View** - Display win rate by day-of-week (Mon-Fri), overall long/short breakdown with individual win rates, weekly totals, best/worst trading day, and instrument breakdown.

3. **Monthly Statistics View** - Display week-over-week performance, monthly totals, long/short analysis, best/worst week, comparison to previous month, profit factor, and average positions per day.

4. **Visual Toggle System** - Each statistic can toggle between text-only display and a visual chart representation (bar chart, line chart, or pie chart as appropriate).

5. **Calculation Service Enhancement** - Extend the StandardizedStatisticsCalculator to compute the new metrics from position data.

## Out of Scope

- Real-time live updating of statistics (page refresh required)
- Custom date range selection beyond the existing period tabs
- Export functionality for statistics
- Comparison across multiple accounts in a single view
- Historical trend analysis beyond the immediate previous period

## Expected Deliverable

1. Enhanced Daily tab showing all specified metrics with visual toggle buttons that expand/collapse chart views for each statistic.

2. Enhanced Weekly tab displaying day-of-week win rate breakdown and long/short analysis with toggle-able visualizations.

3. Enhanced Monthly tab showing week-over-week breakdown and comprehensive monthly metrics with toggle-able visualizations.
