# Spec Requirements Document

> Spec: Import Logging Page
> Created: 2026-01-22

## Overview

Create a comprehensive import logging page that replaces the existing CSV Manager, providing full visibility into all CSV import executions with detailed row-by-row processing logs, failure highlighting, and actionable controls for retry, rollback, and troubleshooting. This feature will significantly reduce time spent diagnosing import failures and enable users to quickly identify and fix data issues.

## User Stories

### Import Troubleshooting

As a trader, I want to see detailed logs of every CSV import execution including which rows succeeded, which failed, and why, so that I can quickly identify and fix data quality issues in my source files without hunting through log files or database records.

**Workflow**: User navigates to the Import Logs page and sees a chronological list of all import executions. Failed imports are highlighted in red with error badges. User clicks on a failed import to expand full details showing row-by-row processing results. User identifies specific rows that failed validation, sees the exact error messages, and can download the problematic rows as a CSV for correction. User fixes the source file and clicks "Retry Import" to reprocess.

### Import History Auditing

As a trader, I want to view a complete history of all imports with metadata about what was imported when, so that I can track down when specific trades entered the system and understand the data lineage.

**Workflow**: User views the Import Logs page showing all imports with timestamps, file names, row counts, and affected accounts. User filters by date range or account to narrow results. User clicks "View Affected Trades" on a specific import to see the exact trades that were created from that import batch, allowing verification of data integrity.

### Failed Import Recovery

As a trader, I want to easily retry failed imports or rollback successful imports that contained incorrect data, so that I can maintain clean and accurate trading records without manual database manipulation.

**Workflow**: User identifies a failed import on the Import Logs page. User clicks "Retry Failed Import" which moves the file from the error folder back to the data folder and triggers reprocessing. Alternatively, user realizes an import contained incorrect data and clicks "Rollback Import" which deletes all trades associated with that import batch and moves the file back to allow re-import with corrected data.

## Spec Scope

1. **Full Debug Logging Display** - Show row-by-row processing logs with rejected rows, validation errors, and specific failure reasons for each import execution
2. **Import History Table** - Chronological list of all imports with file name, timestamp, status, row counts (total/success/failed), affected accounts, and processing time
3. **Failure Highlighting** - Red background rows for failed imports combined with status badges (success/warning/error icons) for maximum visibility
4. **Retry Failed Imports** - Action button to retry processing failed import files directly from the logging page
5. **View/Download Error Logs** - Ability to view detailed error messages in expandable sections and download error logs as text files
6. **Rollback Imports** - Action button to delete all trades from a specific import batch and prepare file for re-import
7. **View Affected Trades** - Link to filtered trades view showing only trades created by a specific import batch
8. **Expandable Detail Rows** - Click to expand each import row showing full processing details, validation results, and error messages
9. **Filtering and Search** - Filter by date range, status (success/partial/failed), account, and search by filename

## Out of Scope

- Real-time streaming logs (logs are displayed after import completion)
- User authentication and role-based access control for import operations
- Automated email alerts for import failures
- Integration with external monitoring services (Datadog, New Relic)
- Comparison of import files before/after correction
- Bulk retry of multiple failed imports simultaneously

## Expected Deliverable

1. Import Logs page accessible from main navigation (replacing CSV Manager) displays comprehensive import history with full debug details and failure highlighting
2. Users can expand any import row to view row-by-row processing logs, validation errors, and rejected rows with specific error messages
3. Action buttons (Retry, Rollback, View Trades, Download Logs) function correctly and update the UI immediately
4. Failed imports are clearly highlighted with red backgrounds and error status badges, making them immediately identifiable

## Spec Documentation

- Tasks: @.agent-os/specs/2026-01-22-import-logging-page/tasks.md
- Technical Specification: @.agent-os/specs/2026-01-22-import-logging-page/sub-specs/technical-spec.md
