# Spec Requirements Document

> Spec: OHLC Data Completeness Monitor
> Created: 2025-12-03

## Overview

Implement a data completeness monitoring dashboard that proactively identifies missing OHLC data across instruments and timeframes, providing visual indicators and alerting when imports fail. This feature will enable traders to quickly identify data gaps and ensure chart reliability before making trading decisions.

## User Stories

### Data Gap Visibility

As a trader, I want to see at a glance which instruments and timeframes have complete OHLC data, so that I can trust the charts I'm analyzing for trading decisions.

When I open the data monitoring page, I should see a matrix showing all instruments vs. timeframes with clear visual indicators (green/yellow/red) for data completeness status. This helps me understand if the 15-minute chart for NQ is missing data before I rely on it for analysis.

### Proactive Gap Detection

As a system administrator, I want the system to automatically detect and report data gaps after each OHLC sync operation, so that I can take corrective action before users encounter missing chart data.

After each scheduled or manual OHLC sync, the system should compare expected data coverage against actual records and log any gaps. A summary should be accessible via the monitoring dashboard showing sync health over time.

### Quick Gap Repair

As a trader, I want a one-click option to trigger a repair sync for specific missing data, so that I don't have to wait for the next scheduled import or manually trigger a full sync.

From the data completeness dashboard, I should be able to click on a gap indicator and trigger a targeted sync for just that instrument/timeframe combination.

## Spec Scope

1. **Data Completeness Matrix** - Visual dashboard showing instrument vs. timeframe grid with color-coded completeness indicators (green = complete, yellow = partial, red = missing)

2. **Gap Detection Service** - Background service that analyzes OHLC records after each sync and identifies gaps based on expected data coverage per Yahoo Finance limits

3. **Sync Health Timeline** - Historical view showing sync success/failure rates over the past 7 days with timestamps and error details

4. **One-Click Gap Repair** - Button on each gap indicator to trigger targeted OHLC fetch for specific instrument/timeframe combinations

5. **Data Freshness Indicators** - Show last sync timestamp and data age for each instrument/timeframe cell in the matrix

## Out of Scope

- Email or push notification alerts for failed syncs (future enhancement)
- Automatic retry logic for failed syncs (handled by existing circuit breaker)
- Changes to the core OHLC import scheduler timing
- Database schema changes to OHLC storage
- Integration with external monitoring systems (Prometheus metrics already exist)

## Expected Deliverable

1. Data completeness dashboard accessible at `/monitoring/data-completeness` showing real-time gap status for all 7 instruments across 6 priority timeframes (42 cells total)

2. Gap detection runs automatically after each OHLC sync and populates the dashboard with current status

3. One-click repair buttons successfully trigger targeted OHLC fetches and update the dashboard status upon completion
