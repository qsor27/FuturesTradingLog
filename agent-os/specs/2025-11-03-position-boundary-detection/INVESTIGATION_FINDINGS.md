# Position Building Investigation Findings
**Date:** 2025-11-12
**Investigation:** Position Building Logic Issues

## Executive Summary

Critical bugs discovered in position building logic affecting:
1. **Short position calculation** - Average entry price showing 0.00, causing massive negative P&L
2. **Open position rebuild behavior** - Open positions destroyed and recreated with new IDs during CSV imports
3. **Dashboard state management** - Statistics not resetting properly when positions are rebuilt

## Issues Discovered

### 🔴 CRITICAL: Bug #1 - Short Position Entry Price Calculation
**Severity:** Critical
**Impact:** Catastrophic P&L calculation errors

**Observed Behavior:**
- Position #241 (Short MNQ DEC25):
  - Average Entry Price: **0.00** (WRONG!)
  - Average Exit Price: 25565.50
  - Points P&L: **-1,380,537.00 pts** (catastrophic)
  - Gross P&L: **$-2,761,074.00** (massive fake loss)
  - Peak Position Size: 54 contracts (incorrect aggregation)
  - Executions: 1 Sell (entry) + 4 BuyToCover (exits)

**Expected Behavior:**
- Average Entry Price should be calculated from the **Sell** execution (opens short)
- Average Exit Price should be calculated from **BuyToCover** executions (closes short)
- For a short with Sell @ 25561.50 and BuyToCover @ 25565.50, the P&L should be **negative** (loss) but small

**Root Cause Analysis:**

Looking at [pnl_calculator.py:44-56](domain/services/pnl_calculator.py#L44-L56):

```python
for execution in executions:
    if position.position_type == PositionType.LONG:
        # Long position: Buy actions are entries, Sell actions are exits
        if execution.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
            entries.append(self._trade_to_dict(execution))
        elif execution.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
            exits.append(self._trade_to_dict(execution))
    else:  # Short position
        # Short position: Sell actions are entries, Buy actions are exits
        if execution.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
            entries.append(self._trade_to_dict(execution))
        elif execution.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
            exits.append(self._trade_to_dict(execution))
```

**The logic LOOKS correct**, but there's a problem:

Checking [quantity_flow_analyzer.py:85-100](domain/services/quantity_flow_analyzer.py#L85-L100):

```python
def _get_signed_quantity_change(self, trade: Trade) -> int:
    """
    Get signed quantity change for a trade

    Buy actions: +quantity (increase position)
    Sell actions: -quantity (decrease position)
    """
    quantity = abs(trade.quantity)

    if trade.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
        return quantity  # Buying contracts (+)
    elif trade.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
        return -quantity  # Selling contracts (-)
```

**THE BUG:** The quantity flow analyzer treats:
- **Sell** as `-quantity` (moving quantity negative)
- **BuyToCover** as `+quantity` (moving quantity back to zero)

This is CORRECT for tracking position lifecycle (0 → -6 → 0 for short position).

**However**, when the short position closes, the position type is being determined as SHORT based on `running_quantity < 0`, but then when calculating the P&L:
- The initial **Sell** execution is correctly identified as entry
- The **BuyToCover** executions are correctly identified as exits

**BUT** - The issue is that `BuyToCover` is being mapped to the WRONG side for the calculation. Let me check the MarketSide enum...

**HYPOTHESIS:** The `side_of_market` field in the database for short positions may be stored as:
- `"Sell"` for opening (correct)
- `"BuyToCover"` for closing (correct)

But the MarketSide enum might not include `BUY_TO_COVER` as a recognized value, causing it to:
1. Not match the entry condition for short positions
2. Not match the exit condition properly
3. Result in average entry price = 0.00 (no entries found)

**VERIFICATION NEEDED:** Check what `side_of_market` values are actually stored in the database for position #241's executions.

---

### 🟡 MEDIUM: Bug #2 - Open Position Rebuild Behavior
**Severity:** Medium
**Impact:** Loss of position continuity, new position IDs break references

**Observed Behavior:**
- Position #242 (Long MNQ DEC25) - Currently **OPEN**
- 22 executions spanning multiple imports
- Entry Period: 2025-11-12 (today)
- Position Status: Still Open

**Problem:**
When new CSV files are imported while a position is still open:
1. The position is **deleted** from the database
2. A **new position is created** with a different ID
3. The dashboard doesn't reset statistics properly
4. References to the old position ID are broken

**Root Cause:**

Looking at [enhanced_position_service_v2.py:725-758](services/enhanced_position_service_v2.py#L725-L758):

```python
def rebuild_positions_for_account_instrument(self, account: str, instrument: str) -> Dict[str, Any]:
    """
    Rebuild positions for a specific account/instrument combination
    """
    logger.info(f"Rebuilding positions for {account}/{instrument}")

    # Remove existing positions for this account/instrument
    self._clear_positions_for_account_instrument(account, instrument)

    # Get all trades for this account/instrument
    self.cursor.execute("""
        SELECT * FROM trades
        WHERE account = ? AND instrument = ? AND (deleted = 0 OR deleted IS NULL)
        ORDER BY entry_time
    """, (account, instrument))
```

**THE ISSUE:** The `_clear_positions_for_account_instrument()` method **deletes ALL positions** for the account/instrument, including open ones. This means:
1. Every time a new CSV is imported during an active trading session
2. The open position is destroyed
3. A new position is created with a new ID
4. Historical continuity is lost

**Impact on Dashboard:**
- Total P&L calculations become incorrect (position IDs change)
- Position statistics don't reset properly
- Users lose ability to track a position across its lifecycle

---

### 🟡 MEDIUM: Bug #3 - Dashboard Statistics Not Resetting
**Severity:** Medium
**Impact:** Incorrect aggregate statistics shown to users

**Observed Behavior:**
From the dashboard screenshot:
- **Total Positions:** 97
- **Total P&L:** $-15,684,865.50 (obviously wrong!)
- **Win Rate:** 13.4%
- **Avg Executions/Position:** 0.0 (suspicious)

**Root Cause:**
The dashboard is aggregating P&L from positions that include:
1. The short position with catastrophic P&L (Bug #1)
2. Potentially duplicate positions from rebuilds (Bug #2)
3. No cache invalidation after rebuilds

**Related Code:**

The cache invalidation happens in [ninjatrader_import_service.py:477-501](services/ninjatrader_import_service.py#L477-L501), but may not cover all dashboard keys.

---

### 🔵 INFO: Bug #4 - Peak Position Size Calculation
**Severity:** Low
**Impact:** Incorrect peak position size display

**Observed Behavior:**
- Position #241: Peak Position Size = 54 contracts (for only 6 contract position)
- Position #257: Peak Position Size = 66 contracts (for only 6 contract position)

**Root Cause:**
The `max_quantity` is being calculated incorrectly in the position builder. Looking at [position_builder.py:149-152](domain/services/position_builder.py#L149-L152):

```python
elif event.event_type == 'position_modify':
    # Modifying existing position
    if current_position:
        current_executions.append(event.trade)
        current_position.max_quantity = max(current_position.max_quantity, abs(event.running_quantity))
        current_position.total_quantity = abs(event.running_quantity)  # Update running quantity
```

The `max_quantity` is tracking the cumulative quantity flow, not the actual peak number of contracts held at any one time. This should track the **absolute maximum position size** during the position lifecycle.

---

## Recommendations

### Priority 1: Fix Short Position P&L Calculation (Bug #1)
**Action Items:**
1. Add database query to check actual `side_of_market` values for position #241 executions
2. Verify MarketSide enum mapping is correct for BuyToCover
3. Add debug logging to PnL calculator to show entry/exit classification
4. Create test case with: Sell 6 @ 25561.50 → BuyToCover 6 @ 25565.50
5. Verify P&L calculation produces correct negative P&L (loss of ~$20)

**Testing Strategy:**
```python
# Test case for short position P&L
trades = [
    Trade(side_of_market=MarketSide.SELL, quantity=6, entry_price=25561.50, ...),
    Trade(side_of_market=MarketSide.BUY_TO_COVER, quantity=6, entry_price=25565.50, ...),
]
position = build_position(trades)
# Expected: P&L ≈ -$20 (loss: sold at 25561.50, bought back at 25565.50)
# Current: P&L = massive negative due to avg_entry_price = 0.00
```

### Priority 2: Implement Incremental Position Updates (Bug #2)
**Action Items:**
1. Modify `rebuild_positions_for_account_instrument()` to:
   - Check if any open positions exist for the account/instrument
   - If open position exists, **UPDATE** it instead of deleting and recreating
   - Only delete and rebuild **closed** positions
2. Add position ID preservation logic
3. Update cache invalidation to handle partial updates

**Alternative Approach:**
Don't import trades until they're complete (have exit data). This would:
- Prevent open positions from being rebuilt constantly
- Maintain position ID continuity
- Simplify the rebuild logic

**Trade-offs:**
- Pro: Cleaner, simpler logic
- Con: Users don't see open positions until they close
- Con: Delay in position visibility

### Priority 3: Fix Dashboard Cache and Statistics (Bug #3)
**Action Items:**
1. Expand cache invalidation to include all dashboard-related keys
2. Add cache key for global statistics: `statistics:global`
3. Verify Redis cache is properly connected and working
4. Add cache debugging to show which keys are invalidated

### Priority 4: Fix Peak Position Size Calculation (Bug #4)
**Action Items:**
1. Review position_builder logic for max_quantity tracking
2. Ensure it tracks actual peak contracts held, not cumulative flow
3. Add test case verifying peak calculation

---

## Better Method for Ongoing Positions

### Option A: Don't Import Until Closed ✅ RECOMMENDED
**Approach:** Only import trades that have both entry and exit data

**Pros:**
- Clean position boundaries (0 → +/- → 0)
- No position ID churn
- Simpler rebuild logic
- No risk of destroying open positions

**Cons:**
- Users don't see open positions in real-time
- Slight delay in position visibility
- Requires filtering CSV rows by completion status

**Implementation:**
```python
# In CSV import logic
for row in csv_rows:
    # Skip if no exit data (position still open)
    if not row.get('Exit Price') or not row.get('Exit Time'):
        logger.info(f"Skipping open execution: {row['Execution ID']}")
        continue

    # Import only completed executions
    import_trade(row)
```

### Option B: Incremental Update for Open Positions
**Approach:** Update existing open positions instead of recreating them

**Pros:**
- Real-time position visibility
- Position ID preserved
- Full historical view

**Cons:**
- More complex logic
- Risk of position state corruption
- Requires careful position state management

**Implementation:**
```python
def rebuild_positions_for_account_instrument(self, account: str, instrument: str):
    # Check for existing open position
    existing_open = self._get_open_position(account, instrument)

    if existing_open:
        # Update the open position with new trades
        self._update_open_position(existing_open, new_trades)
    else:
        # Rebuild closed positions normally
        self._rebuild_closed_positions(account, instrument)
```

---

## Testing Requirements

### Test Case 1: Short Position P&L
```python
def test_short_position_pnl_calculation():
    """Verify short position P&L calculates correctly"""
    trades = [
        Trade(side_of_market=MarketSide.SELL, quantity=6, entry_price=25561.50),
        Trade(side_of_market=MarketSide.BUY_TO_COVER, quantity=6, entry_price=25565.50),
    ]

    position = build_position(trades, account="Test", instrument="MNQ DEC25")

    assert position.position_type == PositionType.SHORT
    assert position.average_entry_price == 25561.50  # Currently returns 0.00!
    assert position.average_exit_price == 25565.50
    assert position.total_points_pnl < 0  # Loss
    assert abs(position.total_points_pnl - (-4.0)) < 0.01  # ~-4 points loss
```

### Test Case 2: Open Position Rebuild
```python
def test_open_position_rebuild_preserves_id():
    """Verify open position ID is preserved during rebuild"""
    # Create initial open position
    initial_position = create_position(trades=[
        Trade(side=MarketSide.BUY, quantity=6, entry_price=25500)
    ])
    initial_id = initial_position.id

    # Import additional trades (simulating new CSV)
    import_trades([
        Trade(side=MarketSide.BUY, quantity=2, entry_price=25510)
    ])

    # Rebuild positions
    rebuild_positions_for_account_instrument(account, instrument)

    # Verify position ID unchanged
    updated_position = get_position(initial_id)
    assert updated_position is not None
    assert updated_position.id == initial_id
    assert updated_position.total_quantity == 8  # 6 + 2
```

### Test Case 3: Short Position Quantity Flow
```python
def test_short_position_quantity_flow():
    """Verify short position quantity flow is correct"""
    trades = [
        Trade(side=MarketSide.SELL, quantity=6),      # 0 → -6 (open short)
        Trade(side=MarketSide.BUY_TO_COVER, quantity=2),  # -6 → -4 (reduce short)
        Trade(side=MarketSide.BUY_TO_COVER, quantity=4),  # -4 → 0 (close short)
    ]

    flow_events = analyze_quantity_flow(trades)

    assert flow_events[0].event_type == 'position_start'
    assert flow_events[0].running_quantity == -6
    assert flow_events[1].event_type == 'position_modify'
    assert flow_events[1].running_quantity == -4
    assert flow_events[2].event_type == 'position_close'
    assert flow_events[2].running_quantity == 0
```

---

## Next Steps

1. **Investigate Bug #1** - Add database query to check position #241 execution data
2. **Create Test Cases** - Implement the 3 test cases above
3. **Fix Short Position P&L** - Address the entry price calculation bug
4. **Decide on Open Position Strategy** - Choose between Option A (recommended) or Option B
5. **Update Tasks** - Add these bugs to the position boundary detection spec tasks

---

## Database Queries for Investigation

### Query 1: Check Position #241 Execution Details
```sql
SELECT
    t.id,
    t.side_of_market,
    t.quantity,
    t.entry_price,
    t.exit_price,
    t.entry_time,
    pe.execution_order
FROM position_executions pe
JOIN trades t ON pe.trade_id = t.id
WHERE pe.position_id = 241
ORDER BY pe.execution_order;
```

### Query 2: Check All Short Positions with Zero Entry Price
```sql
SELECT
    id,
    instrument,
    account,
    position_type,
    average_entry_price,
    average_exit_price,
    total_points_pnl,
    total_dollars_pnl,
    execution_count
FROM positions
WHERE position_type = 'Short'
    AND (average_entry_price = 0 OR average_entry_price IS NULL)
ORDER BY id;
```

### Query 3: Check Dashboard Aggregate Statistics
```sql
SELECT
    COUNT(*) as total_positions,
    SUM(total_dollars_pnl) as total_pnl,
    COUNT(CASE WHEN position_status = 'open' THEN 1 END) as open_positions,
    COUNT(CASE WHEN position_status = 'closed' THEN 1 END) as closed_positions,
    AVG(execution_count) as avg_executions
FROM positions;
```

---

## File References

**Affected Files:**
- [domain/services/pnl_calculator.py](domain/services/pnl_calculator.py) - P&L calculation logic
- [domain/services/position_builder.py](domain/services/position_builder.py) - Position building logic
- [domain/services/quantity_flow_analyzer.py](domain/services/quantity_flow_analyzer.py) - Quantity flow tracking
- [services/enhanced_position_service_v2.py](services/enhanced_position_service_v2.py) - Position rebuild logic
- [services/ninjatrader_import_service.py](services/ninjatrader_import_service.py) - CSV import and rebuild triggers

**Test Files to Create:**
- `tests/test_short_position_pnl.py` - Short position P&L tests
- `tests/test_open_position_rebuild.py` - Open position rebuild tests
- `tests/test_position_dashboard_statistics.py` - Dashboard statistics tests
