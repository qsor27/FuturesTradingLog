# UI Cleanup Specification

This document provides a comprehensive checklist of all UI elements, buttons, forms, and JavaScript functions that must be removed as part of the Unified CSV Import consolidation.

## Critical Importance

⚠️ **These removals are MANDATORY and CRITICAL to the success of this spec.**

The entire purpose of this refactoring is to eliminate confusion from multiple CSV import entry points. Failing to remove these UI elements would defeat the purpose of the consolidation.

---

## Position Dashboard Cleanup

**File:** `templates/positions/dashboard.html`

### HTML Elements to Remove

**Lines 440-462: Entire "Position Management" Section**

```html
<!-- REMOVE THIS ENTIRE SECTION -->
<div class="rebuild-section">
    <h3>Position Management</h3>
    <p>Positions are automatically aggregated from your trade executions. Use these tools to manage your trading data.</p>

    <div class="management-actions">
        <div class="action-group">
            <h4>Rebuild Positions</h4>
            <p>Rebuild all positions from existing trade data.</p>
            <button onclick="rebuildPositions()" class="btn" id="rebuildBtn">Rebuild Positions</button>
        </div>

        <div class="action-group">
            <h4>Re-import Deleted Trades</h4>
            <p>Scan for archived CSV files and re-import any missing trades.</p>
            <button onclick="reimportTrades()" class="btn" id="reimportBtn">Re-import Trades</button>
            <select id="csvFileSelect" style="margin-left: 10px; display: none;">
                <option value="">Select CSV file...</option>
            </select>
        </div>
    </div>

    <div id="managementStatus" style="margin-top: 10px;"></div>
</div>
<!-- END REMOVAL -->
```

### JavaScript Functions to Remove

**Lines 622-655: `rebuildPositions()` function**
```javascript
// REMOVE THIS ENTIRE FUNCTION
function rebuildPositions() {
    const btn = document.getElementById('rebuildBtn');
    const status = document.getElementById('managementStatus');

    btn.disabled = true;
    btn.textContent = 'Rebuilding...';
    status.innerHTML = '<div style="color: #6b7280;">Rebuilding positions from trade data...</div>';

    fetch('{{ url_for("positions.rebuild_positions") }}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            status.innerHTML = `<div style="color: #059669;">${data.message}</div>`;
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            status.innerHTML = `<div style="color: #dc2626;">Error: ${data.message}</div>`;
        }
    })
    .catch(error => {
        status.innerHTML = `<div style="color: #dc2626;">Error: ${error.message}</div>`;
    })
    .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Rebuild Positions';
    });
}
```

**Lines 657-703: `reimportTrades()` function**
```javascript
// REMOVE THIS ENTIRE FUNCTION
function reimportTrades() { /* ... */ }
```

**Lines 705-755: `importSelectedFile()` function**
```javascript
// REMOVE THIS ENTIRE FUNCTION
function importSelectedFile() { /* ... */ }
```

### Optional Replacement

Add a small, unobtrusive status indicator:

```html
<div class="info-banner" style="background: #1a2a1a; padding: 12px; border-left: 4px solid #4ade80; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 10px;">
        <i class="fas fa-check-circle" style="color: #4ade80;"></i>
        <span>CSV Auto-Import: <strong>Active</strong></span>
        <a href="/csv-manager" style="margin-left: auto; color: #4ade80;">Manage Imports →</a>
    </div>
</div>
```

---

## Upload Page Cleanup

**File:** `templates/upload.html`

### HTML Elements to Remove

**Lines 40-54: Manual File Upload Form**

```html
<!-- REMOVE THIS ENTIRE FORM -->
<form id="uploadForm" style="margin-top: 20px;">
    <div class="form-field">
        <label for="csvFile">Select CSV File</label>
        <input type="file" id="csvFile" name="file" accept=".csv" style="width: 100%;">
    </div>

    <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
        <button type="button" id="processNTButton" class="btn btn-success">
            Process NT Executions Export
        </button>
        <button type="submit" class="btn btn-primary">
            Upload
        </button>
    </div>
</form>
<!-- END REMOVAL -->
```

### JavaScript Functions to Remove

**Lines 67-101: Upload form submission handler**
```javascript
// REMOVE THIS ENTIRE HANDLER
document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData();
    const fileInput = document.getElementById('csvFile');
    const statusDiv = document.getElementById('uploadStatus');
    const statusText = document.getElementById('statusText');

    if (fileInput.files.length === 0) {
        alert('Please select a file');
        return;
    }

    formData.append('file', fileInput.files[0]);
    statusDiv.classList.remove('hidden');
    statusText.textContent = 'Uploading...';

    fetch('{{ url_for("main.upload_file") }}', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '{{ url_for("main.index") }}';
        } else {
            return response.text().then(text => {
                throw new Error(text);
            });
        }
    })
    .catch(error => {
        alert('Error: ' + error.message);
        statusDiv.classList.add('hidden');
    });
});
```

**Lines 143-178: Process NT button handler**
```javascript
// REMOVE THIS ENTIRE HANDLER
document.getElementById('processNTButton').addEventListener('click', function() {
    const fileInput = document.getElementById('csvFile');
    const statusDiv = document.getElementById('uploadStatus');
    const statusText = document.getElementById('statusText');

    if (fileInput.files.length === 0) {
        alert('Please select a NinjaTrader Grid CSV file');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    statusDiv.classList.remove('hidden');
    statusText.textContent = 'Processing NT Executions...';

    fetch('{{ url_for("main.process_nt_executions") }}', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            statusText.textContent = 'Processing complete! You can now upload the processed TradeLog.csv';
            fileInput.value = '';
        } else {
            return response.text().then(text => {
                throw new Error(text);
            });
        }
    })
    .catch(error => {
        alert('Error: ' + error.message);
        statusDiv.classList.add('hidden');
    });
});
```

### Elements to Keep

**Lines 18-38: Auto-Import Status Banner**
```html
<!-- KEEP THIS -->
<div id="autoImportStatus" class="import-section">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h3 style="color: var(--link-color); margin: 0 0 8px 0;">
                Automatic Import Active
            </h3>
            <p style="margin: 0; color: var(--text-color);">
                The app is automatically monitoring for new NinjaTrader execution files and importing them every 5 minutes.
            </p>
        </div>
        <div style="display: flex; gap: 10px;">
            <button id="triggerProcessBtn" class="btn btn-primary btn-small">
                Process Now
            </button>
            <button id="checkStatusBtn" class="btn btn-secondary btn-small">
                Check Status
            </button>
        </div>
    </div>
</div>
```

### Elements to Add

```html
<div style="margin-top: 20px;">
    <h3>Recent Import Activity</h3>
    <div id="recentImports">
        <p style="color: #999;">Loading recent imports...</p>
    </div>
</div>

<div style="margin-top: 20px; padding: 15px; background: #2a2a2a; border-radius: 8px;">
    <p style="margin: 0; color: #999;">
        Need to manage CSV imports?
        <a href="/csv-manager" style="color: #4ade80;">Go to CSV Manager →</a>
    </p>
</div>
```

---

## Trades Page Cleanup

**File:** `templates/trades/index.html` (if it exists)

**Note:** This file was not found in the initial scan. If it exists and contains Step 1/Step 2 sections, they must be removed.

### Elements to Look For and Remove

- Any section titled "Step 1: Process NT Executions"
- Any section titled "Step 2: Import Trade Log"
- File upload forms for trade logs
- NT execution processing buttons
- Associated JavaScript handlers for multi-step import process

---

## Backend Route Removals

### From `routes/positions.py`

**Remove these endpoints:**

```python
# REMOVE THIS ENDPOINT
@positions_bp.route('/rebuild_positions', methods=['POST'])
def rebuild_positions():
    """Rebuild all positions from trade data"""
    # ... implementation ...

# REMOVE THIS ENDPOINT
@positions_bp.route('/list_csv_files')
def list_csv_files():
    """List available CSV files for re-import"""
    # ... implementation ...

# REMOVE THIS ENDPOINT
@positions_bp.route('/reimport_csv', methods=['POST'])
def reimport_csv():
    """Re-import a specific CSV file"""
    # ... implementation ...
```

### From `routes/upload.py`

**Remove these endpoints:**

```python
# REMOVE THIS ENDPOINT (if exists)
@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle manual CSV file upload"""
    # ... implementation ...

# REMOVE THIS ENDPOINT
@upload_bp.route('/process-nt-executions', methods=['POST'])
def process_nt_executions():
    """Process NinjaTrader execution export"""
    # ... implementation ...
```

### From `routes/main.py`

**Verify and remove any redundant CSV processing routes:**
- Check for manual upload handlers
- Remove any duplicate import endpoints
- Update routes to redirect to CSV Manager where appropriate

---

## Navigation Updates

### Add to Main Navigation

**File:** `templates/base.html`

Add CSV Manager link to the main navigation menu:

```html
<a href="/csv-manager" class="nav-link">CSV Manager</a>
```

### Update Page Header Buttons

**Position Dashboard:** Update header buttons to include CSV Manager
**Upload Page:** Redirect or add link to CSV Manager

---

## Verification Checklist

After implementing all removals, verify:

- [ ] Position Dashboard has NO manual rebuild or re-import buttons
- [ ] Upload Page has NO file upload form or manual processing buttons
- [ ] Trades Page has NO Step 1/Step 2 sections (if applicable)
- [ ] All removed JavaScript functions are deleted and do not cause console errors
- [ ] All removed API endpoints return 404 or redirect appropriately
- [ ] Navigation includes link to new CSV Manager page
- [ ] Users can ONLY trigger imports via:
  1. Automatic file watching (primary method)
  2. CSV Manager "Process Now" button (manual fallback)
- [ ] No other CSV import entry points exist in the UI

---

## Success Criteria

✅ **The refactoring is complete when:**

1. A user looking for "how to import CSV data" finds ONLY the CSV Manager page
2. The Position Dashboard is purely for viewing and filtering positions
3. The Upload Page is purely for monitoring auto-import status
4. All CSV processing happens automatically or via CSV Manager
5. The UI is clean, simple, and not confusing

❌ **The refactoring has FAILED if:**

1. Any manual "Upload CSV" or "Rebuild Positions" buttons remain
2. Users can still import CSVs through multiple different UI paths
3. The old multi-step import workflow still exists
4. JavaScript console shows errors from removed functions
