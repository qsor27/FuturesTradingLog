# Spec Requirements Document

> Spec: Daily Import Deduplication
> Created: 2025-12-26

## Overview

Ensure the scheduled daily import runs only once per market close during the valid market-closed window (2:00pm - 3:00pm PT), preventing duplicate imports from container restarts, manual triggers, or multiple scheduler invocations.

## User Stories

### Prevent Duplicate Scheduled Imports

As a trader, I want the daily import to run exactly once after market close, so that I don't get duplicate position rebuilds or wasted processing from multiple import attempts.

When the app container restarts after the 2:05pm PT scheduled import has already run, the system should detect this and skip the import. Similarly, if the scheduler fires multiple times (due to bugs or misconfigurations), only the first execution should process data.

### Weekend and Holiday Awareness

As a trader, I want the daily import to skip weekends and market holidays, so that the system doesn't attempt imports when there's no new trading data available.

Futures markets are closed from Friday 2pm PT to Sunday 3pm PT. The scheduled import should recognize this and only run Monday-Friday during the market-closed window.

## Spec Scope

1. **Redis-Persisted Import State** - Track last successful scheduled import date in Redis to detect if today's import already ran
2. **Market Day Validation** - Skip scheduled imports on weekends (Saturday/Sunday) when markets are closed
3. **Idempotent Import Logic** - Make the scheduled import idempotent so multiple triggers on the same day don't cause issues
4. **Manual Import Override** - Allow manual imports to bypass the deduplication check when explicitly triggered by user

## Out of Scope

- Market holiday calendar integration (future enhancement)
- Partial trading day handling (early closes)
- Multi-timezone support beyond Pacific Time
- Historical backfill of missed imports

## Expected Deliverable

1. Scheduled daily import runs exactly once per trading day, even if the container restarts multiple times
2. Weekend scheduled imports are skipped automatically with appropriate logging
3. Manual imports via API continue to work regardless of scheduled import state
