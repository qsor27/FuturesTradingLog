# Unified CSV Import - Final Verification Checklist

Use this checklist before marking the spec as complete. **ALL items must be checked.**

## 🚨 Critical UI Removals (Blocking)

### Position Dashboard
- [ ] Lines 440-462 deleted: `<div class="rebuild-section">` completely removed
- [ ] "Rebuild Positions" button does NOT exist in the page
- [ ] "Re-import Deleted Trades" button does NOT exist in the page
- [ ] `#csvFileSelect` dropdown does NOT exist in the page
- [ ] `rebuildPositions()` function removed from JavaScript (lines 622-655)
- [ ] `reimportTrades()` function removed from JavaScript (lines 657-703)
- [ ] `importSelectedFile()` function removed from JavaScript (lines 705-755)
- [ ] No console errors when viewing Position Dashboard
- [ ] Page loads successfully without the removed elements

### Upload Page
- [ ] Lines 40-54 deleted: `<form id="uploadForm">` completely removed
- [ ] "Select CSV File" input does NOT exist in the page
- [ ] "Upload" button does NOT exist in the page
- [ ] "Process NT Executions Export" button does NOT exist in the page
- [ ] Upload form JavaScript handler removed (lines 67-101)
- [ ] Process NT button handler removed (lines 143-178)
- [ ] "Automatic Import Active" banner still present and functional
- [ ] "Process Now" button still present and functional
- [ ] "Check Status" button still present and functional
- [ ] No console errors when viewing Upload page

### Backend Routes Removed
- [ ] `/positions/rebuild_positions` returns 404 or redirects
- [ ] `/positions/list_csv_files` returns 404 or redirects
- [ ] `/positions/reimport_csv` returns 404 or redirects
- [ ] `/upload` (manual upload) returns 404 or redirects
- [ ] `/process-nt-executions` returns 404 or redirects
- [ ] No broken endpoint references in JavaScript
- [ ] No server errors when accessing removed endpoints

## ✅ New Functionality Added

### Unified CSV Import Service
- [ ] File `services/unified_csv_import_service.py` exists
- [ ] Auto-detects NT Grid CSV format
- [ ] Auto-detects TradeLog CSV format
- [ ] Auto-detects raw executions CSV format
- [ ] Tracks processed files to prevent duplicates
- [ ] Wraps imports in database transactions
- [ ] Automatically rebuilds positions after import
- [ ] Archives processed files with timestamps
- [ ] Handles errors gracefully with rollback

### CSV Manager Page
- [ ] Page accessible at `/csv-manager`
- [ ] Shows file watcher status (running/stopped)
- [ ] Shows last import timestamp
- [ ] Shows files in processing queue
- [ ] Displays recent processing history (50 entries)
- [ ] "Process Now" button triggers immediate processing
- [ ] Page auto-refreshes every 30 seconds
- [ ] Displays error messages when processing fails

### New API Endpoints
- [ ] `GET /api/csv/status` returns correct status information
- [ ] `POST /api/csv/process-now` triggers processing
- [ ] `GET /api/csv/history` returns processing history
- [ ] All endpoints return proper JSON responses
- [ ] Error responses are handled gracefully

### File Watcher Integration
- [ ] File watcher monitors data directory
- [ ] Debounces file changes (5 seconds)
- [ ] Delegates processing to unified service
- [ ] Starts automatically with app (if enabled)
- [ ] Stops cleanly on app shutdown

## 🔧 Configuration & Setup

### App Configuration
- [ ] `CSV_AUTO_IMPORT_ENABLED` setting added to config
- [ ] `CSV_WATCH_DIRECTORY` setting configured
- [ ] `CSV_ARCHIVE_DIRECTORY` setting configured
- [ ] `CSV_CHECK_INTERVAL` setting configured
- [ ] `CSV_DEBOUNCE_SECONDS` setting configured

### App Startup
- [ ] Unified CSV import service initializes on startup
- [ ] File watcher starts if auto-import enabled
- [ ] CSV management blueprint registered
- [ ] Services cleanup properly on shutdown
- [ ] No startup errors in logs

### Navigation
- [ ] "CSV Manager" link added to main navigation
- [ ] Link appears in Position Dashboard header
- [ ] Link appears in Upload page header
- [ ] All links navigate to `/csv-manager` correctly

## 🧪 Testing Results

### Automatic Import Tests
- [ ] NT Grid CSV file auto-imports successfully
- [ ] TradeLog CSV file auto-imports successfully
- [ ] Raw executions CSV auto-imports successfully
- [ ] Duplicate files are skipped (no re-import)
- [ ] Files are archived after processing
- [ ] Positions rebuild automatically after import

### Manual Trigger Tests
- [ ] "Process Now" button processes new files
- [ ] Shows success message after processing
- [ ] Shows error message if processing fails
- [ ] Updates history table after processing
- [ ] Works from CSV Manager page
- [ ] Works from Upload page (if kept)

### Error Handling Tests
- [ ] Invalid CSV format shows error message
- [ ] Database errors trigger rollback
- [ ] File read errors are logged properly
- [ ] Network errors handled gracefully
- [ ] No data corruption on failed imports

### UI Navigation Tests
- [ ] Can navigate to CSV Manager from any page
- [ ] Position Dashboard works without removed elements
- [ ] Upload page works without removed elements
- [ ] No broken links anywhere in the app
- [ ] No 404 errors in browser console

## 🎯 User Experience Validation

### Single Import Method
- [ ] Only ONE way to trigger manual import: CSV Manager "Process Now"
- [ ] Automatic import is the PRIMARY method
- [ ] No confusion about "which import button to use"
- [ ] Clear status visibility on what's being imported

### Import Simplicity
- [ ] User drops CSV in data directory → auto-imports
- [ ] User can check import status easily
- [ ] User can trigger immediate import if needed
- [ ] No multi-step workflow required
- [ ] No need to specify CSV format

### No Redundancy
- [ ] No manual upload form anywhere
- [ ] No "rebuild positions" buttons
- [ ] No "re-import trades" functionality in UI
- [ ] No Step 1/Step 2 workflow
- [ ] Only CSV Manager exists for manual operations

## 📊 Final Verification

### Code Quality
- [ ] All tests pass
- [ ] No linting errors
- [ ] No console errors in browser
- [ ] No server errors in logs
- [ ] Code follows project conventions

### Documentation
- [ ] User documentation updated
- [ ] API documentation complete
- [ ] Inline code comments clear
- [ ] README files updated

### Performance
- [ ] File watcher doesn't consume excessive CPU
- [ ] Large CSV files import successfully
- [ ] Database queries are efficient
- [ ] Page load times acceptable

## ✍️ Sign-Off

**Implementation complete when ALL boxes above are checked.**

**Implemented by:** _________________

**Date:** _________________

**Verified by:** _________________

**Date:** _________________

---

## 🚫 Common Mistakes to Avoid

❌ **DO NOT:**
- Leave any "Rebuild Positions" or "Re-import Trades" buttons
- Leave any manual CSV upload forms
- Leave any removed API endpoints functional
- Create multiple ways to import CSVs
- Skip the UI cleanup checklist

✅ **DO:**
- Remove ALL redundant UI elements
- Test with real CSV files
- Verify automatic import works
- Check that CSV Manager is the ONLY manual option
- Follow the ui-cleanup-spec.md exactly
