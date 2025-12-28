# Spec Tasks

## Tasks

- [ ] 1. Remove Upload Page and Blueprint
  - [ ] 1.1 Delete templates/upload.html
  - [ ] 1.2 Delete routes/upload.py
  - [ ] 1.3 Remove upload_bp import and registration from app.py
  - [ ] 1.4 Delete templates/components/import_section.html
  - [ ] 1.5 Verify /upload returns 404

- [ ] 2. Clean Up Trades Page (main.html)
  - [ ] 2.1 Remove .import-section and .import-step CSS styles
  - [ ] 2.2 Remove the import-section HTML (Step 1 and Step 2 forms)
  - [ ] 2.3 Remove processNTExport() JavaScript function
  - [ ] 2.4 Verify /trades page loads correctly without import UI

- [ ] 3. Remove Navigation Link
  - [ ] 3.1 Remove Upload link from base.html navigation
  - [ ] 3.2 Verify navigation renders correctly

- [ ] 4. Clean Up Dead Routes in main.py
  - [ ] 4.1 Remove upload_file() route handler
  - [ ] 4.2 Remove safe_move_file() helper function
  - [ ] 4.3 Remove process_nt_executions() route handler
  - [ ] 4.4 Clean up any unused imports

- [ ] 5. Verification
  - [ ] 5.1 Verify Daily Import Scheduler is unaffected (check /csv/daily-import/status)
  - [ ] 5.2 Run existing tests to check for regressions
  - [ ] 5.3 Manual verification of trades page functionality
