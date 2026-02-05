# NinjaTrader Trade Feedback - User Guide

## Overview

The NinjaTrader Trade Feedback feature is a **background service (AddOn)** that tracks your closed positions and integrates validation data with FuturesTradingLog for performance analysis based on trade quality.

**Important:** This AddOn runs invisibly in the background with **no visual chart UI**. It provides feedback through Output window messages, alert dialogs, and CSV export data.

## Features

- Automatic tracking of closed positions in the background
- Alert dialogs when attempting to place orders with unvalidated positions (optional enforcement)
- Emergency override mechanism (Ctrl+Shift) for urgent trading situations
- Automated strategy bypass (won't interfere with algorithmic trading)
- Automatic export of validation data in CSV format via ExecutionExporter
- Filter positions by validation status in FuturesTradingLog web interface
- Performance statistics grouped by trade quality in the web dashboard

## Installation

### Prerequisites

- NinjaTrader 8 installed and working
- FuturesTradingLog application installed
- ExecutionExporter indicator already configured (for CSV export)

### Step 1: Install TradeFeedbackAddOn

1. Copy `TradeFeedbackAddOn.cs` to your NinjaTrader scripts folder:
   ```
   Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```

2. Open NinjaTrader

3. Go to **Tools > Options > NinjaScript**

4. Click **Compile** to compile the AddOn

5. Verify no compilation errors appear

6. Restart NinjaTrader to activate the AddOn

### Step 2: Verify ExecutionExporter Update

The ExecutionExporter indicator has been updated to include a `TradeValidation` column in exported CSVs.

1. Open any chart in NinjaTrader

2. Right-click chart > **Indicators**

3. Verify ExecutionExporter is present in your indicators list

4. If not already added, add ExecutionExporter to your chart

5. Configure export path (default: `Documents\FuturesTradingLog\`)

### Step 3: Configure FuturesTradingLog Database

The database migration adds two new columns:
- `trade_validation` in the `trades` table
- `validation_status` in the `positions` table

Migration should run automatically on application startup. To verify:

1. Open FuturesTradingLog application

2. Check logs for migration success message

3. Or manually run migration:
   ```bash
   python scripts/migrations/migration_004_add_trade_validation_fields.py --db-path data/db/trading_log.db
   ```

## Usage

### How Trade Validation Works

The TradeFeedbackAddOn runs as a **background service** with no visible chart UI.

#### Position Tracking

1. Open NinjaTrader and ensure the AddOn compiled successfully

2. When a position closes, the AddOn automatically:
   - Detects the closed position
   - Calculates P&L
   - Logs to the Output window:
     ```
     Position closed: MNQ P&L: -25.00 - Requires validation: True
     ```
   - Tracks position in memory
   - Saves to state file: `Documents\FuturesTradingLog\trade_feedback_state.txt`

3. Check the **Output** tab (bottom of Control Center) to monitor position tracking

#### Where Validation Happens

**Validation occurs in the FuturesTradingLog web interface, not in NinjaTrader:**

1. Execute trades in NinjaTrader (AddOn tracks in background)
2. ExecutionExporter exports trades to CSV (includes empty TradeValidation column)
3. Import CSV into FuturesTradingLog
4. Use web interface to filter and view positions by validation status
5. Manually mark positions as Valid/Invalid using the PATCH API or frontend UI

**Note:** Direct NinjaTrader validation UI was simplified due to API limitations. All validation is done post-trading in the web interface.

### Order Blocking Feature

By default, the AddOn blocks new orders until you validate closed positions. This enforces disciplined post-trade review.

#### When Order Blocking Activates

- A position closes (e.g., stop loss hit)
- You attempt to place a new order
- A modal dialog appears: "Position validation required before placing new order"

#### Validation and Continue Workflow

1. Modal shows list of unvalidated positions
2. Click Valid or Invalid for each position
3. After all validated, your pending order is allowed
4. Or close modal to cancel the order

#### Emergency Override

If you need to place an urgent order without validation:

1. Hold **Ctrl+Shift** while placing the order
2. Order bypasses validation requirement
3. Override usage is logged for audit trail

**Warning**: Use emergency override sparingly, as it defeats the purpose of disciplined review.

#### Automated Strategy Bypass

Automated trading strategies automatically bypass validation requirements. This is enabled by default to prevent interference with algorithmic trading.

### Viewing Validation Data in FuturesTradingLog

#### Filter Positions by Validation Status

1. Open FuturesTradingLog web interface

2. Navigate to **Positions** view

3. Use the **Validation Status** dropdown:
   - **All**: Show all positions
   - **Valid**: Show only valid trades
   - **Invalid**: Show only invalid trades
   - **Mixed**: Show positions with both valid and invalid executions
   - **Unreviewed**: Show positions not yet validated

4. Filter persists in session storage

#### Position Detail View

1. Click any position to view details

2. Validation status shown prominently:
   - Badge with color coding (green/red/yellow/gray)
   - Summary: "X of Y executions validated"

3. Execution breakdown table shows per-trade validation

#### Statistics by Validation

1. Navigate to **Statistics** view

2. View performance metrics grouped by validation status:
   - Total trades per status
   - Win rate per status
   - Average P&L per status
   - Total P&L per status

3. Compare Valid vs Invalid trade performance to identify rule violations

### Manual Validation Updates

You can manually update trade validation through the web interface:

1. Open a position detail view

2. Click on an execution in the breakdown table

3. Change validation status via dropdown (if enabled)

4. Position validation_status automatically recalculates

Or use the API:

```bash
curl -X PATCH http://localhost:5000/api/trades/{trade_id} \
  -H "Content-Type: application/json" \
  -d '{"trade_validation": "Valid"}'
```

## Settings

### AddOn Settings (NinjaTrader)

Access via **Tools > Options > NinjaTrader AddOns > Trade Feedback**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Enable Order Blocking Until Validation | Checkbox | True | Block orders until trades are validated |
| Validation Grace Period | Numeric (0-300s) | 0 | Delay before blocking activates after position close |
| Auto-Show Panel on Position Close | Checkbox | True | Automatically show panel when position closes |
| Bypass Validation for Automated Strategies | Checkbox | True | Allow automated strategies to skip validation |
| Enable Emergency Override Shortcut | Checkbox | True | Allow Ctrl+Shift override for urgent orders |
| Maximum Unvalidated Positions to Display | Numeric (1-10) | 5 | Max positions shown in panel before scrolling |

### Recommended Settings

**For Disciplined Review (Strict)**
- Enable Order Blocking: True
- Validation Grace Period: 0 seconds
- Auto-Show Panel: True
- Emergency Override: True (for emergencies only)

**For Casual Review (Flexible)**
- Enable Order Blocking: False
- Validation Grace Period: 60 seconds
- Auto-Show Panel: True
- Emergency Override: True

**For Live Trading with Automation**
- Enable Order Blocking: True
- Bypass Automated Strategies: True
- Emergency Override: True
- Grace Period: 10 seconds (time to think)

## Troubleshooting

### Panel Not Appearing

**Problem**: Trade Feedback panel doesn't show after position closes

**Note:** There is no visible chart panel UI. The AddOn runs in the background.

**Solutions**:
1. Verify AddOn is compiled: Tools > NinjaScript Editor > Compile
2. Check Output window for: "TradeFeedbackAddOn initialized successfully"
3. Check Output window for position tracking messages when you close positions
4. Verify state file exists: `Documents\FuturesTradingLog\trade_feedback_state.txt`
5. Restart NinjaTrader if no Output messages appear

### Validation Data Not Exporting

**Problem**: CSV files don't include TradeValidation column

**Solutions**:
1. Verify ExecutionExporter is updated (should include TradeValidation column)
2. Check ExecutionExporter is active on chart
3. Verify export path is correct
4. Check NinjaTrader Output window for export errors
5. Manually export: Tools > ExecutionExporter > Export Now

### Validation Not Showing in FuturesTradingLog

**Problem**: Web interface doesn't show validation status

**Solutions**:
1. Verify CSV import successful (check import logs)
2. Check database migration applied: `SELECT validation_status FROM positions LIMIT 1`
3. Verify positions rebuilt after import
4. Clear browser cache
5. Check API endpoint: `GET /api/positions?validation_status=valid`

### Order Blocking Not Working

**Problem**: Orders not blocked even with unvalidated positions

**Solutions**:
1. Verify "Enable Order Blocking Until Validation" is checked in settings
2. Check grace period hasn't been set too high
3. Verify order is not from automated strategy (bypasses blocking by default)
4. Check NinjaTrader Output window for blocking events
5. Restart NinjaTrader and try again

### Database Migration Errors

**Problem**: Migration fails with "column already exists" error

**Solution**: Migration is idempotent and safe to re-run. The error can be ignored if columns exist.

**Problem**: Migration fails with CHECK constraint error

**Solution**: Database may have invalid data. Run rollback and re-apply:
```bash
python scripts/migrations/migration_004_add_trade_validation_fields.py --rollback --db-path data/db/trading_log.db
python scripts/migrations/migration_004_add_trade_validation_fields.py --db-path data/db/trading_log.db
```

## FAQ

**Q: Can I validate trades after the fact?**

A: Yes, use the manual validation API or web interface to update trade validation at any time.

**Q: What happens to trades I don't validate?**

A: They remain in "Unreviewed" status and can be filtered separately. They don't count as Valid or Invalid in statistics.

**Q: Can I change a validation status after marking it?**

A: Yes, validation can be updated at any time via the API or web interface.

**Q: Does order blocking work with automated strategies?**

A: No, automated strategies bypass validation by default (configurable in settings).

**Q: What if I have multiple unvalidated positions?**

A: The panel shows up to 5 positions (configurable). Scroll to see more. Modal dialog shows all unvalidated positions when blocking occurs.

**Q: Can I use this feature without order blocking?**

A: Yes, disable "Enable Order Blocking Until Validation" in settings. Panel still appears for voluntary validation.

**Q: Does this work with NinjaTrader 7?**

A: No, this feature requires NinjaTrader 8 for the AddOn framework.

**Q: What if CSV import fails?**

A: Check import logs. CSVs without TradeValidation column are backward compatible and import normally with NULL validation status.

**Q: How do I disable this feature entirely?**

A: Remove TradeFeedbackAddOn from NinjaTrader scripts folder and recompile, or disable all settings in AddOn configuration.

## Best Practices

1. **Be Honest**: Mark trades Invalid even if profitable but rule-breaking
2. **Validate Immediately**: Review trades while context is fresh
3. **Review Statistics Weekly**: Compare Valid vs Invalid performance
4. **Adjust Rules**: If Invalid trades outperform Valid, revisit your rules
5. **Use Emergency Override Sparingly**: Defeats purpose of disciplined review
6. **Export Daily**: Ensure CSV exports run daily for up-to-date data
7. **Backup Database**: Before running migrations or bulk updates

## Support

For issues or questions:
- Check NinjaTrader Output window for error messages
- Review FuturesTradingLog application logs in `data/logs/`
- Verify CSV files contain TradeValidation column
- Test with small dataset first

## Version History

- **v1.0.0** (2025-02-04): Initial release
  - Background position tracking AddOn
  - Order blocking alerts (modal dialogs)
  - Emergency override (Ctrl+Shift)
  - Automated strategy bypass
  - CSV export with TradeValidation column
  - Web interface filters and statistics
  - State persistence across NinjaTrader restarts
