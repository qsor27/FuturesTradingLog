# Trade Validation Tracking - Testing Checklist

## Quick Start Testing Guide

### Prerequisites
- [ ] NinjaTrader 8 running
- [ ] Sim account configured (e.g., Sim101)
- [ ] Chart open with any instrument (e.g., MNQ)

---

## Test 1: Install and Compile

### Steps
1. [ ] Copy updated ExecutionExporter.cs to NinjaTrader:
   ```powershell
   Copy-Item "C:\Projects\FuturesTradingLog\ninjascript\ExecutionExporter.cs" `
             "$HOME\Documents\NinjaTrader 8\bin\Custom\Indicators\ExecutionExporter.cs"
   ```

2. [ ] Open NinjaTrader → Tools → Edit NinjaScript → Indicator
3. [ ] Find `ExecutionExporter` in list
4. [ ] Press F5 or click **Compile**

### Expected Results
```
✅ Compiled successfully
✅ No errors in Output window
✅ No warnings (or only minor warnings about unused variables)
```

### If Failed
- Check for missing using statements
- Verify file copied correctly
- Try: Tools → Remove NinjaScript Assembly → Compile again

---

## Test 2: Baseline - Validation OFF (Default Behavior)

### Settings
1. [ ] Add ExecutionExporter to chart
2. [ ] Configure settings:
   - `Enable Validation Tracking = false` ← Default
   - All other settings: defaults

### Test Actions
1. [ ] Place a trade: Buy 1 contract
2. [ ] Close the position: Sell 1 contract (flatten)
3. [ ] Check Output window

### Expected Results
```
✅ CSV export continues working normally
✅ Execution exported to CSV file
✅ NO validation tracking messages (feature disabled)
✅ NO "Position closed - Added to validation tracker" messages
```

### Success Criteria
- CSV export works exactly as before
- No validation tracking (feature disabled by default)
- Backward compatibility confirmed

---

## Test 3: Position Close Detection - Validation ON, Blocking OFF

### Settings
1. [ ] Open ExecutionExporter settings
2. [ ] Configure:
   - `Enable Validation Tracking = true` ← Enable tracking
   - `Enable Order Blocking = false` ← No alerts yet
   - `Grace Period = 0`
   - Apply changes

### Test Actions
1. [ ] Place a trade: Buy 1 contract MNQ
2. [ ] Close the position: Sell 1 contract (flatten)
3. [ ] Check NinjaTrader Output window
4. [ ] Check state file

### Expected Output Window Messages
```
DetermineEntryExit - Key: Sim101_MNQ MAR26, Previous Position: 1, OrderAction: Sell
Updated position - Key: Sim101_MNQ MAR26, New Position: 0
✓ Position closed - Added to validation tracker: 2026-02-04T14:23:15_MNQ MAR26_Sim101
✓ Unvalidated positions: 1
Exported execution: [Sim101] MNQ MAR26 Exit 1@25019.5 - Position: 0
Validation tracking: ENABLED (Order blocking: OFF)
```

### Expected Files
```
✅ State file created: Documents\FuturesTradingLog\trade_validation_state.txt
✅ File contains position entry with pipe-delimited format
```

### State File Content Example
```
2026-02-04T14:23:15_MNQ MAR26_Sim101|2026-02-04T14:23:15.0000000|MNQ MAR26|0|None|True
```

### Success Criteria
- [x] "✓ Position closed" message appears
- [x] Position ID logged
- [x] Unvalidated count increments
- [x] State file created with valid entry
- [x] NO order blocking alerts (blocking disabled)

---

## Test 4: Order Blocking Alert

### Settings
1. [ ] Keep validation tracking enabled
2. [ ] Configure:
   - `Enable Validation Tracking = true`
   - `Enable Order Blocking = true` ← Enable alerts
   - `Grace Period = 0` ← Immediate enforcement
   - `Enable Emergency Override = true`

### Test Actions
1. [ ] Close a position (if not already unvalidated from Test 3)
2. [ ] Try to place a NEW order on same instrument
3. [ ] Observe alert dialog

### Expected Results
```
✅ Modal alert dialog appears
✅ Dialog title: "Validation Required"
✅ Dialog message lists unvalidated positions
✅ Shows timestamp and instrument
✅ Message: "Please validate in FuturesTradingLog web interface"
✅ Shows: "(Hold Ctrl+Shift to override)"
```

### Output Window Messages
```
⚠ VALIDATION REQUIRED: 1 unvalidated position(s) for MNQ MAR26
```

### Success Criteria
- Alert blocks order placement (shows warning)
- User is informed about unvalidated positions
- Emergency override hint displayed

---

## Test 5: Emergency Override (Ctrl+Shift Bypass)

### Settings
- Same as Test 4 (blocking enabled, grace period = 0)

### Test Actions
1. [ ] Ensure you have unvalidated positions
2. [ ] Hold down **Ctrl+Shift** keys
3. [ ] While holding, place a new order
4. [ ] Check Output window

### Expected Results
```
✅ NO alert dialog shown
✅ Order placed successfully
✅ Output window shows: "⚠ EMERGENCY OVERRIDE: Validation bypassed (Ctrl+Shift)"
```

### Success Criteria
- Emergency override works
- Ctrl+Shift allows bypassing validation
- Override action logged

---

## Test 6: Grace Period

### Settings
1. [ ] Configure:
   - `Enable Validation Tracking = true`
   - `Enable Order Blocking = true`
   - `Grace Period = 30` ← 30 seconds grace period

### Test Actions
1. [ ] Close a position
2. [ ] **Immediately** try to place a new order (within 30 seconds)
3. [ ] Wait 30 seconds
4. [ ] Try to place order again

### Expected Results

**Within Grace Period (0-30 seconds)**:
```
✅ NO alert shown
✅ Order allowed
✅ Grace period still active
```

**After Grace Period (30+ seconds)**:
```
✅ Alert dialog appears
✅ Validation enforcement activated
```

### Success Criteria
- Grace period delays enforcement
- Allows trading immediately after close
- Enforcement activates after grace period expires

---

## Test 7: State Persistence Across Restarts

### Test Actions
1. [ ] Close a position (ensure unvalidated)
2. [ ] Verify state file exists with entry
3. [ ] **Close NinjaTrader** (complete shutdown)
4. [ ] Check state file still exists
5. [ ] **Restart NinjaTrader**
6. [ ] Add ExecutionExporter to chart (validation enabled)
7. [ ] Try to place order on same instrument

### Expected Results
```
✅ State file persists after shutdown
✅ After restart, validation tracker reloads state
✅ Unvalidated positions still tracked
✅ Order blocking alert still appears
```

### Success Criteria
- State survives NinjaTrader restarts
- Validation tracking continues across sessions
- No data loss

---

## Test 8: Multiple Instruments

### Test Actions
1. [ ] Close position on **MNQ**
2. [ ] Close position on **NQ** (different instrument)
3. [ ] Try to place order on **MNQ**
4. [ ] Try to place order on **NQ**
5. [ ] Try to place order on **ES** (no closed positions)

### Expected Results
```
✅ MNQ order → Alert (unvalidated MNQ position)
✅ NQ order → Alert (unvalidated NQ position)
✅ ES order → NO alert (no unvalidated ES positions)
```

### Success Criteria
- Validation is instrument-specific
- Alerts only shown for instrument with unvalidated positions
- Other instruments not affected

---

## Test 9: Disable Validation - Return to Normal

### Test Actions
1. [ ] Ensure validation tracking enabled with unvalidated positions
2. [ ] Change settings:
   - `Enable Validation Tracking = false` ← Disable
   - Apply changes
3. [ ] Place orders on any instrument

### Expected Results
```
✅ NO validation tracking messages
✅ NO order blocking alerts
✅ CSV export continues normally
✅ Returns to baseline behavior
```

### Success Criteria
- Validation can be disabled without breaking anything
- Clean disable/enable toggle
- No residual effects

---

## Automated Strategy Bypass (Optional Test)

### If You Have Automated Strategy

1. [ ] Enable validation tracking and order blocking
2. [ ] Close a position manually
3. [ ] Run automated strategy on same instrument
4. [ ] Check Output window

### Expected Results
```
✅ Strategy orders bypass validation
✅ No alerts shown for strategy orders
✅ Log: "Order bypassed validation (automated)"
```

---

## Success Summary

### Core Functionality
- [ ] ✅ Compiles without errors
- [ ] ✅ Position close detection works (ExecutionUpdate events fire)
- [ ] ✅ Validation tracking optional (disabled by default)
- [ ] ✅ State persistence works
- [ ] ✅ Order blocking alerts work
- [ ] ✅ Emergency override works
- [ ] ✅ Grace period works
- [ ] ✅ Backward compatible (validation OFF = normal behavior)

### Edge Cases
- [ ] ✅ Multiple instruments tracked separately
- [ ] ✅ State survives restarts
- [ ] ✅ Can disable/enable without issues
- [ ] ✅ Automated strategies bypassed (if applicable)

---

## Troubleshooting

### Position Close Not Detected

**Symptoms**: No "✓ Position closed" message

**Checks**:
1. Validation tracking enabled? (should see "Validation tracking: ENABLED")
2. Position actually went to zero/flat?
3. Check Output window for "Updated position - New Position: 0"
4. If ExecutionUpdate events working, you should see DetermineEntryExit logs

### Alert Not Showing

**Symptoms**: Order placed but no alert

**Checks**:
1. Order blocking enabled?
2. Unvalidated position for that specific instrument?
3. Grace period expired? (check timestamp vs current time)
4. Emergency override (Ctrl+Shift) held down?
5. Automated strategy order? (bypassed by default)

### State File Not Created

**Symptoms**: File doesn't exist

**Checks**:
1. Path: `%USERPROFILE%\Documents\FuturesTradingLog\trade_validation_state.txt`
2. Folder permissions OK?
3. Validation tracking enabled?
4. Position closed with tracking enabled?

---

## Next Steps After Testing

1. ✅ **If all tests pass**: Ready for production use
2. 📊 **Integration**: Connect to FuturesTradingLog web interface
3. 🔄 **Mark Positions**: Implement Valid/Invalid marking in web UI
4. 📈 **CSV Export**: Populate TradeValidation column from SharedValidationMap

---

## Questions?

If you encounter issues:
1. Check NinjaTrader Output window for error messages
2. Verify settings are configured correctly
3. Ensure state file path is accessible
4. Review VALIDATION_TRACKING_IMPLEMENTATION.md for details
