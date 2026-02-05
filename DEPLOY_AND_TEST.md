# Quick Deploy and Test Guide

## 1. Deploy to NinjaTrader

### Option A: PowerShell Script
```powershell
# Copy modified file to NinjaTrader
Copy-Item "C:\Projects\FuturesTradingLog\ninjascript\ExecutionExporter.cs" `
          "C:\Users\qsoren\Documents\NinjaTrader 8\bin\Custom\Indicators\ExecutionExporter.cs" `
          -Force

Write-Host "✓ File deployed to NinjaTrader" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Open NinjaScript Editor (F11 in NinjaTrader)"
Write-Host "2. Press F5 to compile"
Write-Host "3. Remove and re-add ExecutionExporter indicator on your chart"
```

### Option B: Manual Copy
1. Open File Explorer
2. Copy: `C:\Projects\FuturesTradingLog\ninjascript\ExecutionExporter.cs`
3. Paste to: `C:\Users\qsoren\Documents\NinjaTrader 8\bin\Custom\Indicators\`
4. Replace existing file

## 2. Compile in NinjaTrader

1. **Open NinjaScript Editor**: Press `F11` in NinjaTrader
2. **Select ExecutionExporter** in the indicator list
3. **Compile**: Press `F5` or click Compile button
4. **Check Output window** for any errors:
   - ✅ Should see: "Compiled successfully"
   - ❌ If errors, check the VALIDATION_FIX_SUMMARY.md troubleshooting section

## 3. Reload Indicator on Chart

1. **Right-click chart** → Indicators
2. **Remove** ExecutionExporter if already loaded
3. **Add** ExecutionExporter from list
4. **Configure settings** (if needed):
   - EnableValidationTracking = ✅ true
   - EnableOrderBlocking = ✅ true (or false to test queue feature)
   - GracePeriodSeconds = 0
5. **Click OK**

## 4. Quick Test - Validation Flow

### Step 1: Create Test Position
1. **Go long** with 1 contract (any instrument)
2. **Close position** immediately (go flat)

### Step 2: Validate Position
1. **Validation panel appears** on right side of chart
2. **Click "✗ Invalid"** button
3. **Check Output window:**
   ```
   ✗ Position marked as INVALID: 2026-02-04T[time]_[instrument]_[account]
   ```

### Step 3: Trigger CSV Write
1. **Close another position** (or wait for next execution)
2. **Check CSV file:**
   ```powershell
   # PowerShell
   $csvFile = Get-ChildItem "C:\Projects\FuturesTradingLog\data\NinjaTrader_Executions_*.csv" |
              Sort-Object LastWriteTime -Descending |
              Select-Object -First 1

   Get-Content $csvFile.FullName | Select-Object -Last 10
   ```

### Step 4: Verify Validation in CSV
Look for the **TradeValidation** column (last column):
```csv
...,Invalid   ← Should appear on ALL executions in the position
...,Invalid
...,Invalid
```

**✅ Success Criteria:**
- TradeValidation column has "Invalid" for ALL executions (entry + exits)
- Not just the final closing execution

## 5. Quick Test - Queue Feature

### Step 1: Disable Order Blocking
1. **Right-click chart** → Indicators → ExecutionExporter
2. **Set EnableOrderBlocking = false**
3. **Click OK**

### Step 2: Create Multiple Unvalidated Positions
1. **Close 3 positions** without validating
2. **Check panel title**: Should show "Trade Validation (3 queued)"
3. **Output window should show:**
   ```
   ✓ Position queued (blocking disabled): [positionId] (Total queued: 3)
   ```

### Step 3: Validate and Check Queue
1. **Click "✓ Valid"** on first position
2. **Panel title updates**: "Trade Validation (2 queued)"
3. **Output window shows:**
   ```
   ✓ Position marked as VALID: [positionId] (Removed from queue, 2 remain)
   ```

**✅ Success Criteria:**
- Queue count decrements as positions are validated
- Can continue trading (orders NOT blocked)
- Panel title updates in real-time

## 6. Verify Debug Logging

### Check NinjaTrader Output Window
You should see messages like:

```
✓ Position closed - Added to validation tracker: 2026-02-04T13:22:00_MNQ MAR26_Sim101
✓ Unvalidated positions: 1
✗ Position marked as INVALID: 2026-02-04T13:22:00_MNQ MAR26_Sim101
Found validation via time window search (offset: 0s): Invalid
```

**Key indicators of success:**
- "Position closed - Added to validation tracker" ✅
- "Position marked as VALID/INVALID" ✅
- "Found validation via time window search" ✅ (for non-closing executions)

## 7. Check Validation State File

```powershell
# PowerShell
Get-Content "C:\Users\qsoren\Documents\FuturesTradingLog\trade_validation_state.txt" |
  Select-Object -Last 5
```

**Expected format:**
```
PositionId|CloseTimestamp|Instrument|PnL|ValidationStatus|RequiresValidation
2026-02-04T18:00:14_MNQ MAR26_Sim101|2026-02-04T18:00:14.0763739|MNQ MAR26|0|Valid|False
```

## 8. End-to-End Integration Test

### Step 1: Check CSV Has Validation Data
```powershell
# Find latest CSV
$csv = Get-ChildItem "C:\Projects\FuturesTradingLog\data\NinjaTrader_Executions_*.csv" |
       Sort-Object LastWriteTime -Descending |
       Select-Object -First 1

# Count lines with validation
(Get-Content $csv.FullName | Select-String -Pattern ",Valid$|,Invalid$").Count
```

**✅ Should return > 0** if validation is flowing to CSV

### Step 2: Import to Web Interface
```bash
# Check if Docker container is running
docker ps --filter "name=futurestradinglog"

# Check import service logs
docker logs futurestradinglog --tail 50 | grep -i validation
```

### Step 3: Query Database
```bash
# Check trades table for validation
docker exec futurestradinglog sqlite3 /app/data/db/trading_log.db \
  "SELECT time, instrument, action, price, trade_validation
   FROM trades
   WHERE trade_validation IS NOT NULL
   LIMIT 10;"
```

**Expected output:**
```
2026-02-04 18:00:14|MNQ MAR26|Sell|25122.75|Invalid
2026-02-04 18:00:14|MNQ MAR26|Sell|25123.00|Invalid
```

### Step 4: Check Web Interface
1. **Open browser**: http://localhost:5000
2. **Filter positions**: Select "Invalid" from validation filter
3. **Click on position**: Should see "Invalid" badge
4. **View position detail**: All trades should show validation status

## 9. Troubleshooting

### Problem: Compile errors in NinjaScript Editor

**Fix:**
1. Check Output window for specific line number
2. Common issues:
   - Missing semicolon
   - Mismatched braces
   - Incorrect static/instance field access

**Verify syntax:**
```powershell
# Check for balanced braces
$content = Get-Content "C:\Projects\FuturesTradingLog\ninjascript\ExecutionExporter.cs" -Raw
$openBraces = ($content.ToCharArray() | Where-Object {$_ -eq '{'}).Count
$closeBraces = ($content.ToCharArray() | Where-Object {$_ -eq '}'}).Count
Write-Host "Open braces: $openBraces, Close braces: $closeBraces"
```

### Problem: Validation not appearing in CSV

**Debug steps:**
1. Check validation state file has entries
2. Verify SharedValidationMap is populated (Output window messages)
3. Ensure CSV has TradeValidation column (column 15)
4. Try closing another position to trigger CSV write

**Add debug logging:**
In GetTradeValidationStatus, add:
```csharp
LogMessage($"Looking up validation for: {positionId}");
```

### Problem: Panel not showing queue count

**Check:**
1. EnableOrderBlocking = false in settings
2. titleText field is initialized
3. RefreshPositions is called after validation

**Verify:**
```csharp
// In RefreshPositions, should see:
var queuedCount = ExecutionExporter.QueuedPositionsMap.Count;
titleText.Text = $"Trade Validation ({queuedCount} queued)";
```

### Problem: Orders still being cancelled when blocking disabled

**Check:**
1. OnOrderUpdate event handler respects EnableOrderBlocking setting
2. Output window shows "Position queued (blocking disabled)" message
3. Verify EnableOrderBlocking = false in indicator settings

## 10. Success Checklist

Before considering the fix complete:

- [ ] Indicator compiles successfully
- [ ] Validation panel appears when position closes
- [ ] Can mark positions as Valid/Invalid
- [ ] CSV file shows validation in TradeValidation column for ALL executions
- [ ] Queue count shows in panel title when blocking disabled
- [ ] Database has trade_validation data after CSV import
- [ ] Web interface shows validation badges
- [ ] Filter by validation status works
- [ ] No console errors in browser or Docker logs

## 11. Next Actions After Testing

If all tests pass:

1. **Update user documentation** with validation workflow
2. **Test edge cases**:
   - Multiple positions per day on same instrument
   - Partial exits
   - Position reversals
   - NinjaTrader restart persistence
3. **Performance test** with high-frequency trading
4. **Commit to GitHub** (when user approves)

## Quick Commands Reference

### Check CSV
```powershell
$csv = Get-ChildItem "C:\Projects\FuturesTradingLog\data\NinjaTrader_Executions_*.csv" |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $csv.FullName | Select-Object -Last 20
```

### Check State File
```powershell
Get-Content "C:\Users\qsoren\Documents\FuturesTradingLog\trade_validation_state.txt" | Select-Object -Last 10
```

### Check Database
```bash
docker exec futurestradinglog sqlite3 /app/data/db/trading_log.db \
  "SELECT * FROM trades WHERE trade_validation IS NOT NULL LIMIT 5;"
```

### Check Docker Logs
```bash
docker logs futurestradinglog --tail 50 | grep -i validation
```

---

**Ready to deploy!** 🚀

Start with the deployment steps above, then run through the tests to verify everything works.
