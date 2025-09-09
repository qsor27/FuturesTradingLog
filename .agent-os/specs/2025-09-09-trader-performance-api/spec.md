# Spec Requirements Document

> Spec: Trader Performance API
> Created: 2025-09-09
> Status: Planning

## Overview

Create REST API endpoints that provide real-time trader performance metrics for external monitoring systems running in local network containers. This API will enable automated risk management by providing daily and weekly P/L, trade counts, and win/loss statistics to external applications that can force-close NinjaTrader processes when performance thresholds are exceeded.

## User Stories

### External Risk Management System Integration

As an external risk management application, I want to access current trading performance metrics via API, so that I can automatically monitor trader behavior and intervene when necessary to prevent excessive losses.

The external system will poll this API periodically (every 30-60 seconds) to get current day or week performance data. When predefined risk thresholds are met (e.g., daily/weekly loss limit exceeded, too many losing trades), the external system can take protective action by terminating NinjaTrader processes.

### Real-time Performance Monitoring

As a trading monitoring dashboard, I want to access live performance statistics, so that I can display current trading metrics without direct database access.

The API will provide endpoints returning JSON data with all key performance indicators for the current trading day or week, formatted for easy consumption by external applications.

## Spec Scope

1. **Daily P/L Endpoint** - Return current calendar day profit/loss total in dollars
2. **Weekly P/L Endpoint** - Return current calendar week profit/loss total in dollars
3. **Trade Count Metrics** - Provide total number of trades executed for daily and weekly periods
4. **Win/Loss Statistics** - Calculate and return winning trades count and losing trades count for both timeframes
5. **Local Network API** - REST endpoints accessible via HTTP within local container network
6. **Real-time Data** - Current day and week metrics updated as new trades are processed

## Out of Scope

- Historical performance data beyond current calendar day/week
- Authentication/authorization (local network deployment)
- Process termination functionality (handled by external system)
- User interface components
- Trade-by-trade details or position information

## Expected Deliverable

1. Flask API endpoints returning JSON with P/L, trade counts, and win/loss statistics:
   - /api/performance/daily for current calendar day metrics
   - /api/performance/weekly for current calendar week metrics
2. Integration with existing position-based tracking system to calculate real-time metrics
3. API response time under 50ms consistent with platform performance standards

## Spec Documentation

- Tasks: @.agent-os/specs/2025-09-09-trader-performance-api/tasks.md
- Technical Specification: @.agent-os/specs/2025-09-09-trader-performance-api/sub-specs/technical-spec.md