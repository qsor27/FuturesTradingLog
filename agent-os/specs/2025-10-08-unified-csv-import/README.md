# Unified CSV Import System - Spec Documentation

**Created:** 2025-10-08
**Status:** Ready for Implementation

## Quick Summary

This spec consolidates all CSV import methods (manual uploads, file watcher, NT executions processing, position rebuilding, trade re-importing) into a **single automatic background service** that detects, processes, and archives CSV files without user intervention.

## Problem Being Solved

Currently, the app has **multiple confusing CSV import entry points:**
- Position Dashboard: "Rebuild Positions" + "Re-import Trades" buttons
- Upload Page: Manual file upload form + "Process NT Executions" button
- Trades Page: Step 1 and Step 2 manual workflow
- Multiple backend endpoints for different import types

This creates confusion about which method to use and leads to inconsistent data processing.

## Solution

**One automatic pipeline:**
```
CSV File Detected → Auto-Format Detection → Parse & Validate →
Import to DB → Archive → Rebuild Positions → Done
```

**One UI:** CSV Manager dashboard at `/csv-manager` with status monitoring and "Process Now" button.

## File Structure

```
.agent-os/specs/2025-10-08-unified-csv-import/
├── README.md                          # This file
├── spec.md                            # Main requirements document
├── spec-lite.md                       # One-paragraph summary
├── tasks.md                           # Implementation task breakdown (7 major tasks)
└── sub-specs/
    ├── technical-spec.md              # Technical implementation details
    ├── api-spec.md                    # API endpoint specifications
    └── ui-cleanup-spec.md             # CRITICAL: Complete UI removal checklist
```

## Key Documents

### 1. [spec.md](spec.md)
Main requirements document with:
- Overview and problem statement
- **⚠️ CRITICAL UI Removal section** (must-read)
- 3 user stories
- Scope and deliverables

### 2. [tasks.md](tasks.md)
Implementation breakdown:
- **Task 1:** Create Unified CSV Import Service (8 subtasks)
- **Task 2:** Refactor File Watcher Service (5 subtasks)
- **Task 3:** Consolidate Backend Routes (8 subtasks)
- **Task 4:** Create CSV Manager Dashboard (8 subtasks)
- **Task 5:** Remove Redundant UI Elements (6 sections, 30+ removals) ⚠️ **CRITICAL**
- **Task 6:** Update App Configuration (6 subtasks)
- **Task 7:** Integration Testing (8 subtasks)

### 3. [sub-specs/ui-cleanup-spec.md](sub-specs/ui-cleanup-spec.md) ⚠️ **MUST READ**
**Complete checklist** of UI elements to remove with:
- Exact line numbers in templates
- HTML code blocks to delete
- JavaScript functions to remove
- API endpoints to eliminate
- Verification checklist
- Success/failure criteria

### 4. [sub-specs/technical-spec.md](sub-specs/technical-spec.md)
Technical implementation:
- Unified CSV Import Service architecture
- CSV format auto-detection logic
- Database transaction handling
- Route consolidation strategy
- Configuration settings

### 5. [sub-specs/api-spec.md](sub-specs/api-spec.md)
New API endpoints:
- `GET /api/csv/status` - System status
- `POST /api/csv/process-now` - Manual trigger
- `GET /api/csv/history` - Processing history

## ⚠️ CRITICAL: UI Removals

**The spec will FAIL if these UI elements are not removed:**

### Position Dashboard (`templates/positions/dashboard.html`)
- Remove lines 440-462: Entire "Position Management" section
- Remove 3 JavaScript functions (150+ lines)
- Remove 3 backend API endpoints

### Upload Page (`templates/upload.html`)
- Remove lines 40-54: Manual upload form
- Remove 2 JavaScript event handlers (100+ lines)
- Remove 2 backend endpoints

### Backend Routes
- `routes/positions.py`: Remove 3 endpoints
- `routes/upload.py`: Remove 2 endpoints

**See [sub-specs/ui-cleanup-spec.md](sub-specs/ui-cleanup-spec.md) for complete details.**

## Implementation Order

1. **Backend First:** Create unified service and refactor file watcher
2. **API Layer:** Consolidate routes and create new CSV management endpoints
3. **Frontend New:** Build CSV Manager dashboard
4. **Frontend Cleanup:** Remove old UI elements (use ui-cleanup-spec.md checklist)
5. **App Config:** Update configuration and startup
6. **Testing:** Integration tests and verification

## Success Criteria

✅ **Success when:**
- Users can ONLY import CSVs via: (a) automatic file watching, or (b) CSV Manager "Process Now"
- Position Dashboard has NO import buttons
- Upload Page has NO manual upload form
- All CSV formats are auto-detected and processed identically
- No JavaScript console errors
- All removed endpoints return 404

❌ **Failure if:**
- Any manual "Upload CSV" or "Rebuild" buttons remain
- Multiple import entry points still exist
- Old multi-step workflow is still functional

## Getting Started

1. Read [spec.md](spec.md) - especially the "Critical UI Removal" section
2. Review [sub-specs/ui-cleanup-spec.md](sub-specs/ui-cleanup-spec.md) - **mandatory**
3. Follow [tasks.md](tasks.md) in order
4. Reference [sub-specs/technical-spec.md](sub-specs/technical-spec.md) for implementation details
5. Use [sub-specs/api-spec.md](sub-specs/api-spec.md) for API contracts

## Questions?

See the main spec documents for details. The UI cleanup spec is particularly important and contains exact code blocks and line numbers for all removals.
