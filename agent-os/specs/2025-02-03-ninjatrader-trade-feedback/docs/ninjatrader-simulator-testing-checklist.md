# NinjaTrader Simulator Testing Checklist

## Purpose

This checklist guides manual testing of the Trade Feedback feature in NinjaTrader Simulator environment. Complete all items before deploying to live trading.

## ⚠️ Important: What to Expect

**The TradeFeedbackAddOn is a BACKGROUND SERVICE - there is NO visible chart panel UI.**

The AddOn provides feedback through:
- ✅ **Output window messages** - Check the Output tab in Control Center for position tracking messages
- ✅ **Modal dialog alerts** - Popup warnings when you try to place orders with unvalidated positions
- ✅ **CSV export data** - Validation status written to exported CSV files
- ❌ **NO visual panel on chart** - The AddOn runs invisibly in the background

What you'll see on your chart:
- Normal price chart
- ExecutionExporter indicator panel at the bottom (separate from TradeFeedbackAddOn)
- **No validation buttons or panels on the right side of the chart**

## Prerequisites

- [ ] NinjaTrader 8 installed with Simulator account configured
- [ ] TradeFeedbackAddOn.cs compiled without errors
- [ ] ExecutionExporter.cs updated and compiled without errors
- [ ] FuturesTradingLog application running and accessible
- [ ] Database migration 004 successfully applied

## Test Environment Setup

### 1. Verify AddOn Installation

- [ ] Open NinjaTrader
- [ ] Go to Tools > NinjaScript Editor
- [ ] Verify TradeFeedbackAddOn.cs is in AddOns folder
- [ ] Click Compile - verify no errors
- [ ] Verify no compilation errors in Output window
- [ ] Restart NinjaTrader for AddOn to load

### 2. Verify AddOn is Running

**IMPORTANT:** The TradeFeedbackAddOn is a **background service** with **no visible chart UI**. It runs invisibly and provides feedback through Output messages and modal dialogs.

- [ ] After restart, go to Control Center
- [ ] Click on **Output** tab at the bottom of the Control Center window
- [ ] Look for message: "TradeFeedbackAddOn initialized successfully"
- [ ] Look for message: "Order blocking: ENABLED"
- [ ] Look for message: "Grace period: 0 seconds"

If you see these messages, the AddOn is running correctly.

**Note:** The AddOn uses default settings:
- Enable Order Blocking: **True** (default)
- Validation Grace Period: **0 seconds** (default)
- Auto-Show Panel: **True** (default)
- Bypass Automated Strategies: **True** (default)
- Emergency Override: **True** (default)
- Max Positions Display: **5** (default)

To change settings, modify the default values in TradeFeedbackAddOn.cs State.SetDefaults section and recompile.

### 3. Setup Chart and Instruments

- [ ] Open a chart for MNQ or ES (simulator data feed)
- [ ] Set chart to 1-minute timeframe
- [ ] Add ExecutionExporter indicator to chart if not already loaded
- [ ] Verify ExecutionExporter is running (check indicator panel)

**Note:** The chart panel UI was simplified due to NinjaTrader API limitations. Validation feedback is provided through:
- Output window messages when positions close
- Modal dialogs when order blocking is triggered
- Direct validation status in the exported CSV file

## Feature Testing

### Test Group 1: Position Tracking

#### 1.1 Position Close Detection

- [ ] Place a simulated trade (Buy 1 MNQ at market)
- [ ] Close position with stop loss or manually
- [ ] Check Output window for message: "Position closed: MNQ P&L: X.XX - Requires validation: True/False"
- [ ] Verify position was added to tracker

#### 1.2 P&L Calculation

- [ ] Place trade and close with profit
- [ ] Check Output window shows positive P&L
- [ ] Check "Requires validation: False" for profitable trade (by default)
- [ ] Place trade and close with loss
- [ ] Check Output window shows negative P&L
- [ ] Check "Requires validation: True" for losing trade

#### 1.3 Multiple Positions

- [ ] Place and close 3 separate positions on different instruments
- [ ] Check Output window shows all 3 positions tracked
- [ ] Verify each position has unique position ID logged
- [ ] Check state file: `Documents\FuturesTradingLog\trade_feedback_state.txt`
- [ ] Verify state file contains position entries

### Test Group 2: State Persistence

#### 2.1 State Saving

- [ ] Place and close 2 positions
- [ ] Check state file exists at: `Documents\FuturesTradingLog\trade_feedback_state.txt`
- [ ] Open state file and verify position data is saved
- [ ] Format should be: `positionId|timestamp|instrument|pnl|status|requiresValidation`

#### 2.2 State Loading

- [ ] Close NinjaTrader completely
- [ ] Restart NinjaTrader
- [ ] Check Output window for: "State loaded successfully: X positions"
- [ ] Verify previously tracked positions are restored

### Test Group 3: Order Blocking Alerts

#### 3.1 Basic Order Alert

- [ ] Place a trade (Buy 1 MNQ at market)
- [ ] Close position with stop loss (should create loss)
- [ ] Check Output: "Position closed... Requires validation: True"
- [ ] Attempt to place new order for same instrument (Buy 1 MNQ)
- [ ] Check Output: "VALIDATION REQUIRED: X unvalidated position(s) for MNQ"
- [ ] Modal dialog appears: "Position validation required before placing new orders"
- [ ] Dialog lists unvalidated positions with instrument, timestamp, P&L
- [ ] Dialog mentions Ctrl+Shift override if enabled

#### 3.2 Emergency Override

- [ ] Have unvalidated position for MNQ
- [ ] Hold Ctrl+Shift while placing new MNQ order
- [ ] Check Output: "EMERGENCY OVERRIDE: Bypassing validation requirement"
- [ ] Order should place without blocking dialog
- [ ] Override action logged in Output window

#### 3.3 Same Instrument Blocking

- [ ] Close MNQ position (creates unvalidated entry)
- [ ] Try to place ES order (different instrument)
- [ ] Attempt to place MNQ order - **should be blocked**
- [ ] Attempt to place ES order (different instrument) - **should succeed**
- [ ] Validates instrument-specific blocking

#### 4.4 Grace Period

- [ ] Set Validation Grace Period to 30 seconds
- [ ] Close a position
- [ ] Immediately place new order - **should succeed** (within grace period)
- [ ] Wait 35 seconds
- [ ] Attempt to place order - **should be blocked**

#### 4.5 Emergency Override

- [ ] Close a position (don't validate)
- [ ] Hold Ctrl+Shift keys
- [ ] While holding, place new order
- [ ] Order should succeed (bypass validation)
- [ ] NinjaTrader Output window logs emergency override usage

#### 4.6 Automated Strategy Bypass

- [ ] Enable an automated strategy on chart
- [ ] Strategy places orders automatically
- [ ] Orders should **not be blocked** even with unvalidated positions
- [ ] Manual orders still blocked

### Test Group 5: State Persistence

#### 5.1 State Persistence on Restart

- [ ] Close 2 positions, don't validate
- [ ] Exit NinjaTrader completely
- [ ] Restart NinjaTrader
- [ ] Open chart with TradeFeedbackAddOn
- [ ] Verify 2 unvalidated positions still in panel
- [ ] Validates state file persistence

#### 5.2 State File Location

- [ ] Navigate to Documents\FuturesTradingLog\
- [ ] Verify `trade_feedback_state.json` file exists
- [ ] Open file - verify JSON format with position data

### Test Group 6: CSV Export Integration

#### 6.1 TradeValidation Column Export

- [ ] Validate a position as "Valid"
- [ ] Validate another position as "Invalid"
- [ ] Leave one position unvalidated
- [ ] Wait for ExecutionExporter to export (or trigger manually)
- [ ] Open exported CSV file
- [ ] Verify TradeValidation column exists as last column
- [ ] Verify Valid position has "Valid" in TradeValidation column
- [ ] Verify Invalid position has "Invalid" in TradeValidation column
- [ ] Verify unvalidated position has empty TradeValidation value

#### 6.2 CSV Header Format

- [ ] Open CSV file in text editor
- [ ] Verify header row ends with: `...,Account,Connection,TradeValidation`
- [ ] Verify no extra commas or formatting issues

### Test Group 7: Settings Configuration

#### 7.1 Disable Order Blocking

- [ ] Set "Enable Order Blocking Until Validation" to **False**
- [ ] Close a position
- [ ] Attempt to place new order
- [ ] Order should **succeed** (no blocking)
- [ ] Panel still shows unvalidated position

#### 7.2 Disable Auto-Show Panel

- [ ] Set "Auto-Show Panel on Position Close" to **False**
- [ ] Close a position
- [ ] Panel should **not** automatically appear
- [ ] Manually toggle panel to see unvalidated position

#### 7.3 Max Display Count

- [ ] Set "Maximum Unvalidated Positions to Display" to **3**
- [ ] Close 5 positions without validating
- [ ] Panel should show scrollbar for 5 positions
- [ ] Only 3 visible without scrolling

### Test Group 8: Edge Cases and Error Handling

#### 8.1 Multiple Unvalidated Positions

- [ ] Close 5 positions without validating
- [ ] Attempt to place order
- [ ] Modal shows all 5 unvalidated positions
- [ ] Validate all 5 in modal
- [ ] Modal closes after last validation

#### 8.2 Rapid Order Placement

- [ ] Close position
- [ ] Rapidly attempt to place 3 orders
- [ ] All 3 should be blocked
- [ ] No crashes or errors

#### 8.3 Large P&L Values

- [ ] Close position with very large profit (e.g., +$5000)
- [ ] Panel displays value correctly (no overflow)
- [ ] Close position with very large loss (e.g., -$3000)
- [ ] Panel displays value correctly in red

#### 8.4 Long Instrument Names

- [ ] Test with instrument like "MES 03-25" (longer name)
- [ ] Panel displays full name without truncation

#### 8.5 AddOn Unload/Reload

- [ ] Remove TradeFeedbackAddOn from chart
- [ ] Re-add TradeFeedbackAddOn to chart
- [ ] Verify state persists (unvalidated positions still shown)

## Integration Testing with FuturesTradingLog

### Test Group 9: CSV Import and Display

#### 9.1 CSV Import with Validation

- [ ] Export CSV from NinjaTrader with validation data
- [ ] Copy CSV to FuturesTradingLog import directory
- [ ] Trigger import (automatic or manual)
- [ ] Check import logs for success
- [ ] Verify no errors in application logs

#### 9.2 Database Verification

- [ ] Open database: data\db\trading_log.db
- [ ] Query: `SELECT trade_validation, COUNT(*) FROM trades GROUP BY trade_validation`
- [ ] Verify Valid and Invalid counts match exported data
- [ ] Query: `SELECT validation_status, COUNT(*) FROM positions GROUP BY validation_status`
- [ ] Verify position aggregation correct

#### 9.3 Web UI Display

- [ ] Open FuturesTradingLog web interface
- [ ] Navigate to Positions view
- [ ] Verify Validation Status filter dropdown exists
- [ ] Filter by "Valid" - verify correct positions shown
- [ ] Filter by "Invalid" - verify correct positions shown
- [ ] Verify badge colors: green for Valid, red for Invalid

#### 9.4 Position Detail

- [ ] Click on a Valid position
- [ ] Verify validation badge displayed
- [ ] Verify "X of Y executions validated" summary shown
- [ ] Verify execution breakdown table shows per-trade validation

#### 9.5 Statistics

- [ ] Navigate to Statistics view
- [ ] Select "Statistics by Validation" (if available)
- [ ] Verify Valid trades show separate metrics
- [ ] Verify Invalid trades show separate metrics
- [ ] Compare win rates between Valid and Invalid

### Test Group 10: Manual Validation Update

#### 10.1 Update via Web Interface

- [ ] Open position detail for unvalidated position
- [ ] Change validation status to "Valid" (if UI allows)
- [ ] Verify position validation_status updates
- [ ] Verify change persists after page refresh

#### 10.2 Update via API

- [ ] Get trade ID from database
- [ ] Send PATCH request:
  ```bash
  curl -X PATCH http://localhost:5000/api/trades/{id} \
    -H "Content-Type: application/json" \
    -d '{"trade_validation": "Valid"}'
  ```
- [ ] Verify 200 OK response
- [ ] Verify database updated
- [ ] Verify position validation_status recalculated

## Backward Compatibility Testing

### Test Group 11: Legacy Data

#### 11.1 CSV Without TradeValidation Column

- [ ] Create CSV without TradeValidation column (legacy format)
- [ ] Import CSV into FuturesTradingLog
- [ ] Verify import succeeds
- [ ] Verify trades have NULL validation status
- [ ] Verify positions have NULL validation_status

#### 11.2 Existing Positions

- [ ] Query database for positions created before migration
- [ ] Verify NULL validation_status doesn't cause errors
- [ ] Verify positions display as "Unreviewed" in UI
- [ ] Verify filtering by "null" returns these positions

## Performance Testing

### Test Group 12: High Volume

#### 12.1 Many Positions

- [ ] Close 50+ positions in Simulator
- [ ] Verify panel performance (no lag or freezing)
- [ ] Verify scrolling smooth
- [ ] Verify validation actions responsive

#### 12.2 Large CSV Export

- [ ] Export CSV with 500+ executions
- [ ] Verify TradeValidation column present for all rows
- [ ] Verify import completes successfully
- [ ] Verify web UI filter performance acceptable

## Defect Tracking

| Test | Result | Notes | Action Required |
|------|--------|-------|----------------|
|      | Pass/Fail |       |                |

## Sign-Off

- [ ] All critical tests passed
- [ ] All defects documented and triaged
- [ ] Performance acceptable for live trading
- [ ] Documentation complete and accurate

**Tested By**: ___________________

**Date**: ___________________

**NinjaTrader Version**: ___________________

**FuturesTradingLog Version**: ___________________

**Notes**:

---

## Known Limitations

Document any limitations discovered during testing:

1. Order cancellation timing not guaranteed 100% (best effort)
2. Panel may not display correctly on very small monitors (<1280px width)
3. State persistence limited to 100 positions (file size consideration)
4. Validation data not synced in real-time (requires CSV export cycle)

## Next Steps

After testing completion:

1. Review defect log and prioritize fixes
2. Update documentation based on testing findings
3. Deploy to production environment
4. Monitor for issues in first week of use
5. Collect user feedback for future enhancements
