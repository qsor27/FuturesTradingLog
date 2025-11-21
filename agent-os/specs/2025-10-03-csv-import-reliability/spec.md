# Spec Requirements Document

> Spec: CSV Import Reliability and Open Position Tracking
> Created: 2025-10-03
> Status: Planning

## Overview

Establish reliable, real-time CSV import process from NinjaTrader with duplicate prevention via execution ID tracking and proper handling of incomplete open positions. The system will automatically monitor CSV files, import new executions, archive completed daily files, and display open positions with visual indicators and partial P&L.

## User Stories

1. **Automated CSV Import**
   - As a trader, I want the system to automatically import new executions from NinjaTrader's CSV files in real-time, so that my position dashboard is always up-to-date without manual intervention.
   - The system monitors the CSV directory, detects new data, imports using execution IDs to prevent duplicates, and handles re-imports gracefully.

2. **Open Position Visibility**
   - As a trader, I want to see which positions are still open (quantity ≠ 0) with different visual styling, so that I can distinguish between complete and incomplete positions at a glance.
   - Open positions display in a different color, show partial P&L for matched portions, and update in real-time as new executions arrive.

3. **CSV Archive Management**
   - As a trader, I want the system to automatically archive yesterday's CSV files after importing, so that my CSV directory stays organized and NinjaTrader can continue writing to today's file.
   - Files are archived once the date changes and all data is imported, but today's active file remains in place for ongoing updates.

## Spec Scope

1. **Real-Time CSV Monitoring** - Background process watches CSV directory for new/modified files and triggers imports automatically
2. **Execution ID Deduplication** - Track imported execution IDs to prevent re-processing deleted/re-imported trades
3. **Open Position Handling** - Position builder correctly identifies open positions (qty ≠ 0) and calculates partial P&L
4. **Visual Position Indicators** - UI displays open positions in different color with clear status labels
5. **Automatic CSV Archiving** - Archive previous day's CSV files after successful import, preserve today's active file

## Out of Scope

- Manual CSV upload interface (already exists)
- Data validation and error correction tools
- Import history and audit trail dashboard
- Conflict resolution for concurrent imports
- Real-time WebSocket updates to frontend (use polling for now)
- Multi-file concurrent import processing

## Expected Deliverable

1. CSV files are automatically imported in real-time with execution ID tracking preventing duplicates
2. Open positions (quantity ≠ 0) display in dashboard with different color and partial P&L shown
3. Yesterday's CSV files are automatically archived after midnight import completion

## Spec Documentation

- Tasks: @.agent-os/specs/2025-10-03-csv-import-reliability/tasks.md
- Technical Specification: @.agent-os/specs/2025-10-03-csv-import-reliability/sub-specs/technical-spec.md
- Database Schema: @.agent-os/specs/2025-10-03-csv-import-reliability/sub-specs/database-schema.md
