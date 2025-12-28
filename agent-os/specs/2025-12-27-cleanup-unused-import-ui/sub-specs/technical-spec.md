# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-12-27-cleanup-unused-import-ui/spec.md

## Technical Requirements

### Template Changes

1. **templates/main.html**
   - Remove the entire `.import-section` div (lines ~60-106) containing:
     - Step 1: Process NT Executions form
     - Step 2: Import Trade Log form
     - `#processStatus` status indicator
   - Remove `.import-section` and `.import-step` CSS classes from `<style>` block
   - Remove the `processNTExport()` JavaScript function from the scripts block
   - Keep the page header, filters, trade table, and pagination sections

2. **templates/base.html**
   - Remove the Upload navigation link: `<a href="{{ url_for('upload.upload_form') }}" class="nav-link">Upload</a>`

3. **templates/upload.html**
   - Delete this file entirely

4. **templates/components/import_section.html**
   - Delete this file if not used elsewhere (it's a partial that references upload routes)

### Route Changes

1. **routes/upload.py**
   - Delete this file entirely (contains deprecated upload_bp blueprint)

2. **routes/main.py**
   - Remove `upload_file()` route handler (lines ~151-239) - POST to /upload
   - Remove `process_nt_executions()` route handler (lines ~264-end of function) - POST to /process-nt-executions
   - Remove `safe_move_file()` helper function (lines ~241-262) - only used by process_nt_executions
   - Keep: `trades_legacy()`, `delete_trades()`, and all other routes

3. **app.py**
   - Remove `from routes.upload import upload_bp` import (line ~12)
   - Remove `app.register_blueprint(upload_bp)` registration (line ~201)

### Files to Delete

| File | Reason |
|------|--------|
| templates/upload.html | Upload page template |
| templates/components/import_section.html | Upload component partial |
| routes/upload.py | Upload blueprint and routes |
| routes/__pycache__/upload.cpython-*.pyc | Compiled bytecode (multiple versions) |

### Code to Remove from Existing Files

| File | Lines/Section | Description |
|------|---------------|-------------|
| templates/main.html | Lines 13-29 (CSS) | .import-section, .import-step styles |
| templates/main.html | Lines 60-106 | Import section HTML |
| templates/main.html | Lines 116-149 | processNTExport() JS function |
| templates/base.html | Line 19 | Upload nav link |
| routes/main.py | Lines 151-262 | upload_file(), safe_move_file(), process_nt_executions() |
| app.py | Line 12 | upload_bp import |
| app.py | Line 201 | upload_bp registration |

## Verification Steps

1. Start the application and verify /trades page loads without import sections
2. Verify navigation bar does not contain "Upload" link
3. Verify /upload returns 404 Not Found
4. Verify Daily Import Scheduler status via /csv/daily-import/status endpoint
5. Run existing tests to ensure no regressions
