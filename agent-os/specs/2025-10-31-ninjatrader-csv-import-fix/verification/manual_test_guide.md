# Manual Testing Guide for NinjaTrader CSV Import

## Prerequisites

1. Application running: `python app.py`
2. Background import service started automatically
3. Redis server running (for execution deduplication)
4. Database at: `C:\Projects\FuturesTradingLog\data\trading.db`

## Test CSV Files

### Test File 1: Initial Import (2 accounts, complete positions)

**Filename:** `NinjaTrader_Executions_20251101.csv`

**Location:** Copy this file to `C:\Projects\FuturesTradingLog\data\`

```csv
Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection
MNQ 12-25,Buy,2,21000.00,11/1/2025 9:30:00 AM,test_001,E,2 L,ord_001,TestTrader,$4.20,$2.10,APEX1279810000057,Sim101
MNQ 12-25,Sell,2,21010.00,11/1/2025 9:35:00 AM,test_002,X,-,ord_002,TestTrader,$4.20,$2.10,APEX1279810000057,Sim101
MNQ 12-25,Buy,3,21005.00,11/1/2025 9:32:00 AM,test_003,E,3 L,ord_003,TestTrader,$6.30,$2.10,APEX1279810000058,Sim101
MNQ 12-25,Sell,3,21015.00,11/1/2025 9:37:00 AM,test_004,X,-,ord_004,TestTrader,$6.30,$2.10,APEX1279810000058,Sim101
```

**Expected Results:**
- 4 executions inserted into `trades` table
- 2 positions created in `positions` table (one per account)
- Position 1: APEX1279810000057, MNQ 12-25, quantity=2, status=closed, profit=(21010-21000)*2*2 = $40 (minus commission)
- Position 2: APEX1279810000058, MNQ 12-25, quantity=3, status=closed, profit=(21015-21005)*3*2 = $60 (minus commission)

### Test File 2: Incremental Update (append to existing file)

After first import succeeds, append these rows to the same file:

```csv
MNQ 12-25,Buy,1,21020.00,11/1/2025 10:30:00 AM,test_005,E,1 L,ord_005,TestTrader,$2.10,$2.10,APEX1279810000057,Sim101
MNQ 12-25,Sell,1,21025.00,11/1/2025 10:35:00 AM,test_006,X,-,ord_006,TestTrader,$2.10,$2.10,APEX1279810000057,Sim101
```

**Expected Results:**
- Only 2 new executions inserted (IDs: test_005, test_006)
- Previous 4 executions NOT duplicated
- New position created for APEX1279810000057
- Total executions in database: 6
- Total positions for APEX1279810000057: 2 (original + new)

### Test File 3: Multiple Instruments

**Filename:** `NinjaTrader_Executions_20251102.csv`

```csv
Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection
MNQ 12-25,Buy,1,21000.00,11/2/2025 9:30:00 AM,test_007,E,1 L,ord_007,TestTrader,$2.10,$2.10,APEX_ACCT1,Sim101
MNQ 12-25,Sell,1,21010.00,11/2/2025 9:35:00 AM,test_008,X,-,ord_008,TestTrader,$2.10,$2.10,APEX_ACCT1,Sim101
ES 12-25,Buy,1,5800.00,11/2/2025 9:31:00 AM,test_009,E,1 L,ord_009,TestTrader,$2.40,$1.20,APEX_ACCT1,Sim101
ES 12-25,Sell,1,5810.00,11/2/2025 9:36:00 AM,test_010,X,-,ord_010,TestTrader,$2.40,$1.20,APEX_ACCT1,Sim101
MNQ 12-25,Buy,2,21005.00,11/2/2025 9:32:00 AM,test_011,E,2 L,ord_011,TestTrader,$4.20,$2.10,APEX_ACCT2,Sim101
MNQ 12-25,Sell,2,21015.00,11/2/2025 9:37:00 AM,test_012,X,-,ord_012,TestTrader,$4.20,$2.10,APEX_ACCT2,Sim101
```

**Expected Results:**
- 6 executions inserted
- 3 positions created:
  1. APEX_ACCT1 + MNQ 12-25
  2. APEX_ACCT1 + ES 12-25
  3. APEX_ACCT2 + MNQ 12-25
- Each position has correct instrument multiplier applied to P&L

## Manual Test Procedures

### Test 1: Automatic File Detection (Task 8.4)

**Duration:** 2-3 minutes

1. **Start Application**
   ```bash
   cd C:\Projects\FuturesTradingLog
   python app.py
   ```

2. **Verify Background Service Started**
   - Check console output for: "Background watcher started. Polling every 30 seconds."
   - Check logs: `data\logs\import.log` for "NinjaTrader import service initialized"

3. **Copy Test File**
   - Copy Test File 1 to: `C:\Projects\FuturesTradingLog\data\NinjaTrader_Executions_20251101.csv`

4. **Wait for Detection**
   - Maximum wait: 60 seconds (30s poll + 5s stability + processing time)
   - Watch console or logs for processing messages

5. **Verify Import**
   - Check `data\logs\import.log` for:
     ```
     INFO - Starting processing of NinjaTrader_Executions_20251101.csv
     INFO - Processed NinjaTrader_Executions_20251101.csv: 4 new, 0 skipped
     INFO - Rebuilt positions for APEX1279810000057/MNQ 12-25
     INFO - Rebuilt positions for APEX1279810000058/MNQ 12-25
     ```

6. **Query Database**
   ```bash
   python
   >>> import sqlite3
   >>> conn = sqlite3.connect('data/trading.db')
   >>> cursor = conn.cursor()
   >>> cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_execution_id LIKE 'test_%'").fetchone()
   (4,)
   >>> cursor.execute("SELECT account, instrument, total_quantity, position_status FROM positions WHERE account LIKE 'APEX1279810%'").fetchall()
   [('APEX1279810000057', 'MNQ 12-25', 2, 'closed'), ('APEX1279810000058', 'MNQ 12-25', 3, 'closed')]
   >>> conn.close()
   ```

7. **Verify File Remains in Data Folder**
   - File should still be at: `data\NinjaTrader_Executions_20251101.csv`
   - NOT in archive (same day rule)

**Expected Duration:** File processed within 60 seconds of copying

---

### Test 2: Incremental Processing (Task 8.5)

**Duration:** 2-3 minutes

1. **Append New Rows to Existing File**
   - Open `data\NinjaTrader_Executions_20251101.csv`
   - Append rows from Test File 2 (test_005, test_006)
   - Save file

2. **Wait for Detection**
   - Background service detects modification
   - Wait up to 60 seconds

3. **Verify Only New Executions Imported**
   ```python
   import sqlite3
   conn = sqlite3.connect('data/trading.db')
   cursor = conn.cursor()

   # Check total executions
   cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_execution_id LIKE 'test_%'").fetchone()
   # Expected: (6,) - not (10,) which would indicate duplicates

   # Check for duplicates
   cursor.execute("""
       SELECT entry_execution_id, COUNT(*) as count
       FROM trades
       WHERE entry_execution_id LIKE 'test_%'
       GROUP BY entry_execution_id
       HAVING count > 1
   """).fetchall()
   # Expected: [] - no duplicates

   conn.close()
   ```

4. **Check Redis Cache**
   ```bash
   python
   >>> import redis
   >>> r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
   >>> executions = r.smembers('processed_executions:20251101')
   >>> print(sorted(executions))
   ['test_001', 'test_002', 'test_003', 'test_004', 'test_005', 'test_006']
   >>> r.close()
   ```

5. **Verify Positions Updated**
   - Check that new position was created for APEX1279810000057
   - Total positions for this account should be 2 now

**Expected Duration:** Update processed within 60 seconds

---

### Test 3: Multi-Account Position Tracking (Task 8.8)

**Duration:** 5 minutes

1. **Query All Positions for MNQ**
   ```python
   import sqlite3
   conn = sqlite3.connect('data/trading.db')
   cursor = conn.cursor()

   cursor.execute("""
       SELECT
           account,
           instrument,
           total_quantity,
           position_status,
           avg_entry_price,
           avg_exit_price,
           total_points_pnl,
           total_dollar_pnl
       FROM positions
       WHERE instrument LIKE '%MNQ%'
       ORDER BY account, entry_time
   """)

   positions = cursor.fetchall()
   for pos in positions:
       print(f"Account: {pos[0]}, Instrument: {pos[1]}, Qty: {pos[2]}, Status: {pos[3]}")
       print(f"  Entry: {pos[4]}, Exit: {pos[5]}, P&L: ${pos[7]}")

   conn.close()
   ```

2. **Verify Account Separation**
   - Each account should have separate position records
   - Positions should NOT be combined across accounts
   - Each position should have:
     - Correct account identifier
     - Correct quantity
     - Correct entry/exit prices for that account
     - Independent P&L calculation

3. **Verify Position Details**

   **Expected for APEX1279810000057 (first position):**
   - Quantity: 2
   - Entry Price: 21000.00
   - Exit Price: 21010.00
   - Points P&L: 20.00 (10 points * 2 contracts)
   - Dollar P&L: $40.00 (20 points * $2 multiplier for MNQ) minus commission

   **Expected for APEX1279810000058:**
   - Quantity: 3
   - Entry Price: 21005.00
   - Exit Price: 21015.00
   - Points P&L: 30.00 (10 points * 3 contracts)
   - Dollar P&L: $60.00 (30 points * $2 multiplier) minus commission

4. **Cross-Check Against Trades Table**
   ```python
   cursor.execute("""
       SELECT account, instrument, COUNT(*) as trade_count
       FROM trades
       WHERE instrument LIKE '%MNQ%'
       GROUP BY account, instrument
       ORDER BY account
   """)

   # Should show separate trade counts per account
   ```

**Acceptance Criteria:**
- ✓ Separate positions exist for each account
- ✓ Quantities, prices, and P&L are correct per account
- ✓ Positions are NOT combined across accounts
- ✓ Each position maps to correct trades for that account

---

### Test 4: File Archival Next Day (Task 8.6)

**Duration:** Variable (depends on testing approach)

**Option A: Wait for Next Day (Recommended for Production Validation)**

1. **Leave CSV File in Data Folder Overnight**
   - File: `NinjaTrader_Executions_20251101.csv`
   - Should remain in `data` folder until next calendar day

2. **Next Morning: Create New CSV for Current Day**
   - Copy Test File 3 as: `NinjaTrader_Executions_20251102.csv`
   - Place in `data` folder

3. **Verify Archival**
   - Previous day's file should move to `data\archive\`
   - Check: `data\archive\NinjaTrader_Executions_20251101.csv` exists
   - Original location: `data\NinjaTrader_Executions_20251101.csv` should be empty/gone

4. **Check Logs**
   ```
   INFO - Archiving file: NinjaTrader_Executions_20251101.csv
   INFO - File archived successfully to: data\archive\
   ```

**Option B: Simulated Test (For Immediate Validation)**

1. **Manually Trigger Archival Check**
   ```python
   from services.ninjatrader_import_service import ninjatrader_import_service
   from pathlib import Path
   from datetime import datetime, timedelta

   # Get yesterday's file
   yesterday = datetime.now() - timedelta(days=1)
   yesterday_str = yesterday.strftime('%Y%m%d')
   test_file = Path(f'data/NinjaTrader_Executions_{yesterday_str}.csv')

   # Check if should archive
   should_archive = ninjatrader_import_service._should_archive_file(test_file, import_success=True)
   print(f"Should archive: {should_archive}")  # Should be True

   # Archive it
   if should_archive:
       ninjatrader_import_service._archive_file(test_file)
       print("File archived")
   ```

2. **Verify File Moved**
   - Check archive folder for file
   - Verify original location is empty

**Acceptance Criteria:**
- ✓ File remains in `data` folder on same day
- ✓ File moves to `data\archive` on next day after successful import
- ✓ Filename preserved (no timestamp modifications)
- ✓ Archival logged

---

### Test 5: Historical Re-Import (Task 8.7)

**Duration:** 5-10 minutes

1. **Prepare Archive Folder**
   - Ensure you have CSV files in `data\archive\`
   - If not, manually copy Test Files 1-3 there with proper date names

2. **Run Dry-Run Preview**
   ```bash
   cd C:\Projects\FuturesTradingLog
   python scripts\reimport_historical_csvs.py --dry-run
   ```

3. **Verify Dry-Run Output**
   Expected console output:
   ```
   ========================================
   Historical CSV Re-Import - DRY RUN MODE
   ========================================

   Archive folder: C:\Projects\FuturesTradingLog\data\archive

   Found 3 CSV files:
   - NinjaTrader_Executions_20251101.csv (Date: 2025-11-01)
   - NinjaTrader_Executions_20251102.csv (Date: 2025-11-02)
   - NinjaTrader_Executions_20251103.csv (Date: 2025-11-03)

   Date range: 2025-11-01 to 2025-11-03

   DRY RUN - No changes will be made to database

   Would process 3 files in chronological order
   ```

4. **Run Actual Re-Import**
   ```bash
   python scripts\reimport_historical_csvs.py --force
   ```

5. **Verify Re-Import Output**
   Expected:
   ```
   ========================================
   Historical CSV Re-Import
   ========================================

   WARNING: This will DELETE all existing trades and positions!
   Type 'yes' to continue: yes

   Clearing database tables...
   - Deleted 0 position_executions
   - Deleted 0 positions
   - Deleted 0 trades

   Processing 3 files chronologically...

   [1/3] Processing NinjaTrader_Executions_20251101.csv...
   - Imported 4 executions
   - Created 2 positions
   - Accounts: APEX1279810000057, APEX1279810000058

   [2/3] Processing NinjaTrader_Executions_20251102.csv...
   - Imported 6 executions
   - Created 3 positions
   - Accounts: APEX_ACCT1, APEX_ACCT2

   [3/3] Processing NinjaTrader_Executions_20251103.csv...
   ...

   ========================================
   Re-Import Complete
   ========================================

   Summary:
   - Files processed: 3
   - Total executions: 16
   - Total positions: 8
   - Unique accounts: 4
   - Processing time: 12.5 seconds
   ```

6. **Verify Database State**
   ```python
   import sqlite3
   conn = sqlite3.connect('data/trading.db')
   cursor = conn.cursor()

   # Count positions per account
   cursor.execute("""
       SELECT account, COUNT(*) as position_count
       FROM positions
       GROUP BY account
       ORDER BY account
   """).fetchall()

   # Verify all positions have account field populated
   cursor.execute("""
       SELECT COUNT(*) FROM positions WHERE account IS NULL OR account = ''
   """).fetchone()
   # Expected: (0,) - no positions without account

   conn.close()
   ```

**Acceptance Criteria:**
- ✓ Dry-run shows preview without modifying database
- ✓ Actual import rebuilds all positions from scratch
- ✓ All positions have correct account separation
- ✓ Summary statistics accurate
- ✓ No positions without account assignment

---

### Test 6: Dashboard Verification (Task 8.8 continued)

**Duration:** 5 minutes

1. **Open Dashboard in Browser**
   ```
   http://localhost:5000/dashboard
   ```

2. **Verify Multi-Account Display**
   - Check if account information is visible in:
     - Statistics summary
     - Position list table
     - P&L calculations

3. **Test Account Filtering**
   - If filter/dropdown exists, test filtering by account
   - Verify only positions for selected account shown

4. **Verify P&L Calculations**
   - Check that P&L matches database values
   - Ensure P&L is NOT combined across accounts

5. **Check Position Details Page**
   - Click on a position to view details
   - Verify account shown in position details
   - Check that execution list only shows executions for that account

**Acceptance Criteria:**
- ✓ Dashboard displays account information
- ✓ Statistics calculated per account (not combined)
- ✓ Position list shows account column
- ✓ Filtering by account works correctly
- ✓ P&L calculations accurate per account

---

## Troubleshooting Guide

### Issue: Background service not detecting files

**Symptoms:**
- File copied to `data` folder but not processed after 60+ seconds
- No log entries in `data\logs\import.log`

**Debugging Steps:**
1. Check if service is running:
   ```python
   from services.ninjatrader_import_service import ninjatrader_import_service
   status = ninjatrader_import_service.get_status()
   print(status)
   ```
   Expected: `{'running': True, ...}`

2. Check poll interval:
   ```python
   print(ninjatrader_import_service.poll_interval)
   ```
   Default: 30 seconds

3. Manually trigger processing:
   ```python
   from pathlib import Path
   result = ninjatrader_import_service.process_csv_file(Path('data/NinjaTrader_Executions_20251101.csv'))
   print(result)
   ```

### Issue: Duplicate executions inserted

**Symptoms:**
- Same execution appears multiple times in trades table
- Execution count higher than expected

**Debugging Steps:**
1. Check Redis connection:
   ```python
   from services.ninjatrader_import_service import ninjatrader_import_service
   print(f"Redis connected: {ninjatrader_import_service.redis_client is not None}")
   ```

2. Check Redis cache:
   ```python
   import redis
   r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
   executions = r.smembers('processed_executions:20251101')
   print(f"Cached execution count: {len(executions)}")
   ```

3. Verify execution IDs in CSV are unique

### Issue: Positions combined across accounts

**Symptoms:**
- Single position for instrument but trades from multiple accounts
- P&L doesn't match individual account trades

**Debugging Steps:**
1. Check position records:
   ```python
   import sqlite3
   conn = sqlite3.connect('data/trading.db')
   cursor = conn.cursor()
   cursor.execute("""
       SELECT id, account, instrument, total_quantity
       FROM positions
       WHERE instrument = 'MNQ 12-25'
   """)
   print(cursor.fetchall())
   ```

2. Check position_executions mapping:
   ```python
   cursor.execute("""
       SELECT pe.position_id, p.account, t.account
       FROM position_executions pe
       JOIN positions p ON pe.position_id = p.id
       JOIN trades t ON pe.trade_id = t.id
       WHERE p.account != t.account
   """)
   cross_account = cursor.fetchall()
   print(f"Cross-account mappings (should be 0): {len(cross_account)}")
   ```

### Issue: File not archived next day

**Symptoms:**
- File remains in `data` folder on next day
- No archival log entries

**Debugging Steps:**
1. Check file date parsing:
   ```python
   from pathlib import Path
   from datetime import datetime
   import re

   file_path = Path('data/NinjaTrader_Executions_20251101.csv')
   pattern = r'NinjaTrader_Executions_(\d{8})\.csv'
   match = re.search(pattern, file_path.name)
   if match:
       file_date_str = match.group(1)
       file_date = datetime.strptime(file_date_str, '%Y%m%d')
       print(f"File date: {file_date}")
       print(f"Today: {datetime.now()}")
       print(f"Is next day: {datetime.now().date() > file_date.date()}")
   ```

2. Manually check archival condition:
   ```python
   from services.ninjatrader_import_service import ninjatrader_import_service
   should_archive = ninjatrader_import_service._should_archive_file(file_path, import_success=True)
   print(f"Should archive: {should_archive}")
   ```

## Success Criteria Summary

All manual tests should pass with these results:

- [x] File detected and processed within 60 seconds
- [x] Incremental processing prevents duplicates
- [x] Multi-account positions completely separate
- [x] File archival works (next day + successful import)
- [x] Historical re-import rebuilds all positions correctly
- [x] Dashboard shows accurate multi-account data

## Sign-Off

After completing all manual tests successfully:

**Tester Name:** _________________

**Date:** _________________

**Results:** Pass / Fail (circle one)

**Notes:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**Ready to proceed to Task Group 9 (UI Removal):** Yes / No (circle one)

**Signature:** _________________
