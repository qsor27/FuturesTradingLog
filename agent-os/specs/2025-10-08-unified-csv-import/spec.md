# Spec Requirements Document

> Spec: Unified CSV Import System
> Created: 2025-10-08

## Overview

Consolidate all CSV import methods (manual uploads, file watcher, NT executions processing, position rebuilding, and trade re-importing) into a single automatic background service that detects, processes, and archives CSV files without user intervention. This will eliminate confusion from multiple import entry points and ensure consistent, reliable data import across all CSV formats.

## ⚠️ Critical: UI Element Removal Required

**This spec REQUIRES removing all redundant UI import elements.** The entire purpose of this refactoring is to eliminate confusion from multiple CSV import entry points. The following UI elements **MUST be removed**:

### Required Removals:
- ❌ **Position Dashboard:** "Rebuild Positions" button and entire "Position Management" section
- ❌ **Position Dashboard:** "Re-import Deleted Trades" button and CSV file selector
- ❌ **Upload Page:** Manual "Select CSV File" upload form
- ❌ **Upload Page:** "Upload" button for manual CSV submission
- ❌ **Upload Page:** "Process NT Executions Export" button
- ❌ **Trades Page:** Step 1 and Step 2 manual import workflow (if exists)
- ❌ **Backend:** All associated API endpoints for manual upload and rebuild

### What Remains:
- ✅ **Automatic file watching** - Primary import method (background service)
- ✅ **CSV Manager page** - Single UI for import status and manual "Process Now" trigger
- ✅ **Status monitoring** - Visibility into import activity without manual controls

**See [sub-specs/ui-cleanup-spec.md](sub-specs/ui-cleanup-spec.md) for complete removal checklist with specific line numbers and code blocks.**

## User Stories

### Automatic CSV Import

As a trader, I want CSV files to be automatically imported when I place them in the data directory, so that I don't need to manually navigate multiple UI options or remember which import method to use for different file types.

**Workflow:** Trader exports execution data from NinjaTrader to the watched data directory. The unified import service detects the new file, automatically determines its format (NT Grid CSV, TradeLog CSV, or raw executions), processes it, deduplicates against existing data, imports executions into the database, triggers position rebuilding, and archives the processed file - all without manual intervention.

### Simple Manual Processing

As a trader, I want a single "Process Now" button when I need to manually trigger CSV processing, so that I can force immediate import without waiting for the automatic check interval.

**Workflow:** Trader places a CSV file in the data directory and wants immediate processing. They navigate to the CSV Manager page and click "Process Now". The system immediately scans for new files, processes them using the unified pipeline, and displays the results.

### Import Status Visibility

As a trader, I want to see the current status of CSV imports and recent processing history, so that I can verify my data is being imported correctly and troubleshoot any issues.

**Workflow:** Trader navigates to the CSV Manager dashboard and sees: file watcher running status, last import timestamp, files currently in queue, recent processing history with success/failure status, and any error messages. This provides complete visibility into the import system without technical knowledge required.

## Spec Scope

1. **Unified Import Service** - Create a single service that consolidates all CSV import logic with automatic format detection, deduplication, and position rebuilding.
2. **Automatic File Watching** - Background service monitors the data directory for new/modified CSV files with debouncing to handle NinjaTrader's frequent file writes.
3. **Format Auto-Detection** - Automatically detect and process NT Grid CSV, TradeLog CSV, and raw execution CSV formats without user specification.
4. **UI Consolidation** - Remove all redundant import UI elements and replace with a single CSV Manager dashboard showing status and manual trigger option.
5. **Automatic Position Rebuilding** - Trigger position rebuilding automatically after successful CSV imports without manual intervention.

## Out of Scope

- Real-time streaming imports (file watching with debouncing is sufficient)
- CSV format conversion tools (formats are auto-detected, not converted)
- Multi-file simultaneous upload UI (single automatic processing is sufficient)
- CSV editing or validation UI (files are processed as-is with error reporting)
- Historical data migration tools (existing data remains unchanged)

## Expected Deliverable

1. Traders can place any supported CSV file in the data directory and it will be automatically imported within 5 minutes (or immediately with "Process Now").
2. The CSV Manager page at `/csv-manager` shows real-time import status, processing history, and provides a manual "Process Now" trigger.
3. All previous import UI elements (Rebuild Positions, Re-import Trades, Step 1/Step 2, manual file upload) are removed and replaced with automatic processing.
