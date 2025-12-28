# Spec Requirements Document

> Spec: Cleanup Unused Import UI
> Created: 2025-12-27

## Overview

Remove deprecated manual import UI elements and the upload page to streamline the interface, since all trade imports now happen automatically via the Daily Import Scheduler at 2:05pm PT.

## User Stories

### Cleaner Trades Page Experience

As a trader, I want the /trades page to focus on viewing and managing trades without manual import steps, so that the interface is less cluttered and reflects the automated import workflow.

The current trades page (main.html) displays "Step 1: Process NT Executions" and "Step 2: Import Trade Log" sections that are no longer needed since the Daily Import Scheduler handles all imports automatically at market close. Removing these elements will provide a cleaner, more focused view of trade data.

### Simplified Navigation

As a user, I want the navigation bar to only show relevant pages, so that I don't encounter deprecated functionality.

The navigation currently includes an "Upload" link that leads to a deprecated page. Removing this link and the underlying page prevents confusion about import workflows.

## Spec Scope

1. **Remove Import Steps from Trades Page** - Delete the "Step 1" and "Step 2" import sections from /trades (main.html), including the file upload forms and associated JavaScript
2. **Remove Upload Page** - Delete the /upload route, template (upload.html), and blueprint (upload_bp)
3. **Update Navigation** - Remove the "Upload" link from base.html navigation
4. **Clean Up Dead Code** - Remove unused route handlers (upload_file, process_nt_executions in main.py) that are no longer reachable from the UI

## Out of Scope

- The Daily Import Scheduler (services/daily_import_scheduler.py) - this must remain unchanged
- The CSV Manager page (/unified-csv-manager) - this provides useful manual import capability when needed
- Any backend import services used by the Daily Import Scheduler
- The delete_trades route in main.py (still used by the trades table)
- The trades_legacy route that renders the trades page (only removing import UI from it)

## Expected Deliverable

1. The /trades page loads without any "Step 1" or "Step 2" import forms visible
2. The navigation bar no longer shows an "Upload" link
3. Navigating to /upload returns a 404 (page removed)
4. The Daily Import Scheduler at 2:05pm PT continues to function correctly (verify by checking scheduler status)
