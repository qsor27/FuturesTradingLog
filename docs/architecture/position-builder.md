# Position Builder Architecture

## Overview

The Position Builder is the **most critical algorithm** in the Futures Trading Log application. It transforms raw execution data from NinjaTrader into meaningful trading positions using **quantity-based flow analysis**.

### Key Principle: Quantity Flow (0 → +/- → 0)

A position is defined by tracking the **running quantity balance**:
- Position **starts** when quantity goes from 0 to non-zero
- Position **continues** while quantity remains non-zero (same direction)
- Position **ends** when quantity returns to 0
- Position **reversal** occurs when quantity changes sign (long ↔ short)

This approach ignores pre-calculated P&L values on individual executions and instead recalculates P&L for the complete position using FIFO methodology.

### Why This Matters

NinjaTrader exports individual executions, not positions. The application must intelligently aggregate these executions to reconstruct the trader's actual positions. Getting this wrong means incorrect P&L, statistics, and trade analysis.

## Core Concepts

### Terminology

**Execution**: A single fill from the broker (e.g., "Buy 2 contracts at $25,000")
- Uniquely identified by `entry_execution_id` from NinjaTrader
- Represents one atomic trading action

**Position**: A complete trading cycle from flat (qty=0) to non-zero and back to flat
- Composed of multiple executions
- Has entry time, exit time (if closed), and calculated P&L
- Status: OPEN (running_qty ≠ 0) or CLOSED (running_qty = 0)

**Trade**: Generic term for either an execution or position depending on context
- In code: `Trade` model represents individual executions from CSV import
- In UI: "Trade" often refers to a complete position

### Running Quantity Balance

The algorithm maintains a running sum of signed quantities:
```
BUY 5 contracts  → running_qty = +5  (LONG position)
SELL 3 contracts → running_qty = +2  (still LONG, reduced)
SELL 2 contracts → running_qty = 0   (position CLOSED)
```

For short positions:
```
SELL 4 contracts → running_qty = -4  (SHORT position)
BUY 1 contract   → running_qty = -3  (still SHORT, reduced)
BUY 3 contracts  → running_qty = 0   (position CLOSED)
```

### Why We Ignore Pre-Calculated P&L

NinjaTrader's exported data may include P&L calculations on individual executions. The Position Builder **intentionally ignores these** because:

1. **Aggregation Required**: Individual execution P&L doesn't represent complete position P&L
2. **FIFO Matching**: We need to match specific entry executions with specific exit executions chronologically
3. **Accuracy**: Recalculating from raw price/quantity data ensures consistency
4. **Flexibility**: Allows us to apply different P&L calculation methods if needed

## Execution Deduplication Logic

### The Problem: CSV Import Duplicates

NinjaTrader's CSV export can create duplicate records for the same execution. When imported into the database, a single real execution might appear as multiple database rows:

```
Entry Execution ID: ABC123
Database records: [1, 1, 2, 2] quantities

Real execution: 1 fill of 6 contracts
Import artifact: 4 database rows totaling 6 contracts
```

### The Solution: Deduplication by execution_id

The `_deduplicate_trades()` method in `enhanced_position_service_v2.py` groups executions by their unique `entry_execution_id`:

```python
def _deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
    """
    Deduplicate trades by entry_execution_id from NinjaTrader.

    Groups trades with the same execution ID and keeps the representative
    execution with aggregated quantity.
    """
    trade_groups = defaultdict(list)

    for trade in trades:
        exec_id = trade.get('entry_execution_id')
        if exec_id:
            # Group by unique execution ID
            trade_groups[exec_id].append(trade)
        else:
            # Fallback for trades without execution ID
            key = (trade['entry_time'], trade['side_of_market'], trade.get('entry_price'))
            trade_groups[f"FALLBACK_{key}"].append(trade)

    # Keep one representative trade per group (with highest quantity)
    deduplicated = []
    for group_trades in trade_groups.values():
        representative = max(group_trades, key=lambda t: t.get('quantity', 0))
        deduplicated.append(representative)

    return deduplicated
```

### Fallback Strategy

For older data or imports without `entry_execution_id`, the algorithm falls back to grouping by:
- `entry_time` (timestamp of execution)
- `side_of_market` (BUY/SELL)
- `entry_price` (execution price)

This ensures the system works with both modern and legacy data.

### Deduplication Metrics

The service logs before/after counts to track deduplication effectiveness:

```
Before deduplication: 847 trades
After deduplication: 412 trades
Removed 435 duplicates (51.4%)
```

## Position Lifecycle State Machine

### States

The `QuantityFlowAnalyzer` tracks three quantity states:

- **QUANTITY_ZERO**: No active position (running_qty = 0)
- **QUANTITY_POSITIVE**: Long position (running_qty > 0)
- **QUANTITY_NEGATIVE**: Short position (running_qty < 0)

### Events and Transitions

```
┌─────────────────┐
│  QUANTITY_ZERO  │ ◄──────┐
└────────┬────────┘        │
         │                 │
    position_start    position_close
         │                 │
         ▼                 │
┌─────────────────────────┴──────┐
│                                │
│  QUANTITY_POSITIVE (Long)      │
│                                │
│  ┌──────────────┐              │
│  │ position_    │              │
│  │ modify       │              │
│  └──────────────┘              │
│                                │
└────────────┬───────────────────┘
             │
      position_reversal
             │
             ▼
┌────────────────────────────────┐
│                                │
│  QUANTITY_NEGATIVE (Short)     │
│                                │
│  ┌──────────────┐              │
│  │ position_    │              │
│  │ modify       │              │
│  └──────────────┘              │
│                                │
└────────────┬───────────────────┘
             │
      position_close
             │
             ▼
      [QUANTITY_ZERO]
```

### Event Types

**1. position_start**
- Trigger: Quantity goes from 0 to non-zero
- Action: Create new Position object with OPEN status
- Example: `BUY 5` when running_qty = 0

**2. position_modify**
- Trigger: Quantity changes but remains same sign
- Action: Update position's max_quantity and total_quantity
- Examples:
  - `BUY 3` when running_qty = +5 (add to long)
  - `SELL 2` when running_qty = +5 (reduce long)

**3. position_close**
- Trigger: Quantity returns to exactly 0
- Action: Mark position as CLOSED, calculate final P&L
- Example: `SELL 5` when running_qty = +5

**4. position_reversal**
- Trigger: Quantity changes sign without reaching 0
- Action: Close old position, immediately start new position in opposite direction
- Example: `SELL 8` when running_qty = +5 (closes long, opens short with qty=-3)

## FIFO P&L Calculation Methodology

### Overview

First-In-First-Out (FIFO) matching pairs exit executions with entry executions in chronological order to calculate accurate position P&L.

### Algorithm Steps

**1. Separate Entries and Exits**

For a LONG position:
- Entries: BUY, BUY_TO_COVER executions (increase position)
- Exits: SELL, SELL_SHORT executions (decrease position)

For a SHORT position:
- Entries: SELL, SELL_SHORT executions (increase position)
- Exits: BUY, BUY_TO_COVER executions (decrease position)

**2. Sort Chronologically**

Both entry and exit lists are sorted by `entry_time` to ensure FIFO matching.

**3. Match Quantities**

```python
while entry_idx < len(entries) and exit_idx < len(exits):
    entry = entries[entry_idx]
    exit = exits[exit_idx]

    # Match the smaller of remaining quantities
    match_qty = min(remaining_entry_qty, remaining_exit_qty)

    # Calculate P&L for this match
    if position_type == LONG:
        points_pnl = (exit_price - entry_price) * match_qty
    else:  # SHORT
        points_pnl = (entry_price - exit_price) * match_qty

    dollars_pnl = points_pnl * instrument_multiplier
```

**4. Aggregate Results**

- Total P&L = sum of all matched pairs
- Average entry price = weighted average of all entry executions
- Average exit price = weighted average of all exit executions

### FIFO Example: Scaled Entry/Exit

**Executions:**
```
10:00 - BUY 2 @ $25,000
10:05 - BUY 3 @ $25,010
10:15 - SELL 2 @ $25,030
10:20 - SELL 3 @ $25,040
```

**FIFO Matching:**
```
Match 1: 2 qty @ entry $25,000, exit $25,030
  → Points: (25,030 - 25,000) × 2 = 60 points

Match 2: 3 qty @ entry $25,010, exit $25,040
  → Points: (25,040 - 25,010) × 3 = 90 points

Total: 150 points (60 + 90)
```

**Why FIFO Matters:**

If we matched exits to entries in a different order:
```
Wrong Match: 3 qty @ entry $25,010, exit $25,030
  → Points: (25,030 - 25,010) × 3 = 60 points

Wrong Match: 2 qty @ entry $25,000, exit $25,040
  → Points: (25,040 - 25,000) × 2 = 80 points

Total: 140 points (INCORRECT)
```

FIFO ensures consistent, tax-compliant P&L calculation.

### Open Positions and P&L

For OPEN positions (running_qty ≠ 0):
- Only matched entry/exit pairs contribute to P&L
- Unmatched entry executions do not have P&L yet
- `average_entry_price` is calculated from all entries
- `average_exit_price` is `None` (no complete exit yet)
- `total_quantity` shows remaining open quantity

## Code Architecture

### File Structure

```
domain/
├── services/
│   ├── position_builder.py          # Core position building algorithm
│   ├── quantity_flow_analyzer.py    # State machine for quantity flow
│   └── pnl_calculator.py            # FIFO P&L calculation
│
├── models/
│   ├── position.py                  # Position domain model
│   ├── trade.py                     # Trade/Execution domain model
│   └── pnl.py                       # P&L calculation result model
│
services/
└── enhanced_position_service_v2.py  # Integration layer with deduplication
```

### Key Classes

#### PositionBuilder (`domain/services/position_builder.py`)

**Purpose**: Pure domain service for building positions from trade executions

**Main Methods**:
- `build_positions_from_trades(trades, account, instrument)` - Entry point for position building
- `_aggregate_executions_into_positions(trades, account, instrument)` - Core algorithm using quantity flow
- `_calculate_position_totals_from_executions(position, executions)` - P&L calculation integration

**Key Responsibilities**:
- Coordinate with QuantityFlowAnalyzer for position lifecycle
- Track position state (OPEN/CLOSED)
- Update running quantities and max quantities
- Delegate P&L calculation to PnLCalculator
- Handle position reversals

#### QuantityFlowAnalyzer (`domain/services/quantity_flow_analyzer.py`)

**Purpose**: Analyze execution sequence to identify position lifecycle events

**Main Method**:
- `analyze_quantity_flow(trades)` - Returns list of QuantityFlowEvent objects

**Key Responsibilities**:
- Track running quantity balance across executions
- Detect state transitions (zero ↔ positive ↔ negative)
- Emit events: position_start, position_modify, position_close, position_reversal
- Maintain previous and current quantity state for comparison

#### PnLCalculator (`domain/services/pnl_calculator.py`)

**Purpose**: Calculate position P&L using FIFO methodology

**Main Method**:
- `calculate_position_pnl(position, executions)` - Returns PnLCalculation object

**Key Responsibilities**:
- Separate entries from exits based on position direction
- Perform FIFO matching of entry/exit pairs
- Calculate points and dollars P&L
- Apply instrument multipliers
- Calculate average entry/exit prices

#### EnhancedPositionServiceV2 (`services/enhanced_position_service_v2.py`)

**Purpose**: Application service integrating position building with data management

**Main Methods**:
- `rebuild_positions_for_account_instrument(account, instrument)` - Rebuild positions from database
- `_deduplicate_trades(trades)` - Remove duplicate executions by entry_execution_id

**Key Responsibilities**:
- Fetch trades from repository
- Deduplicate executions before building
- Save built positions to database
- Provide logging and metrics

### Data Flow

```
┌─────────────────┐
│  CSV Import     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Database (trades)      │
│  - May contain          │
│    duplicates           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  EnhancedPositionServiceV2      │
│  - Fetch trades                 │
│  - Deduplicate by exec_id       │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  PositionBuilder                │
│  - Coordinate position building │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  QuantityFlowAnalyzer           │
│  - Analyze execution sequence   │
│  - Emit lifecycle events        │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  PositionBuilder                │
│  - Create/update Position       │
│    objects based on events      │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  PnLCalculator                  │
│  - Calculate FIFO P&L           │
│  - Return PnLCalculation        │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  PositionBuilder                │
│  - Assign P&L to position       │
│  - Return completed positions   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  EnhancedPositionServiceV2      │
│  - Save positions to database   │
└─────────────────────────────────┘
```

## Real-World Examples

### Example 1: Simple Position (1 Entry, 1 Exit)

**Executions:**
```
BUY 5 @ $25,000 (10:00)
SELL 5 @ $25,050 (10:15)
```

**Position Building:**
```
Event 1: position_start
  - Running qty: 0 → +5
  - Create Position: LONG, qty=5, status=OPEN

Event 2: position_close
  - Running qty: +5 → 0
  - Update Position: status=CLOSED
```

**P&L Calculation:**
```
FIFO Match: 5 qty @ entry $25,000, exit $25,050
Points P&L: (25,050 - 25,000) × 5 = 250 points
Dollars P&L: 250 × $2 multiplier = $500
```

**Result:**
- 1 CLOSED position
- Total quantity: 5
- P&L: +$500

### Example 2: Scaled Entry/Exit

**Executions:**
```
BUY 2 @ $25,000 (10:00)
BUY 3 @ $25,010 (10:05)
SELL 2 @ $25,030 (10:15)
SELL 3 @ $25,040 (10:20)
```

**Position Building:**
```
Event 1: position_start
  - Running qty: 0 → +2
  - Create Position: LONG, qty=2, max=2, status=OPEN

Event 2: position_modify
  - Running qty: +2 → +5
  - Update Position: qty=5, max=5

Event 3: position_modify
  - Running qty: +5 → +3
  - Update Position: qty=3, max=5 (max unchanged)

Event 4: position_close
  - Running qty: +3 → 0
  - Update Position: status=CLOSED
```

**P&L Calculation:**
```
FIFO Match 1: 2 qty @ entry $25,000, exit $25,030
  Points: (25,030 - 25,000) × 2 = 60 points

FIFO Match 2: 3 qty @ entry $25,010, exit $25,040
  Points: (25,040 - 25,010) × 3 = 90 points

Total: 150 points = $300
```

**Result:**
- 1 CLOSED position
- Total quantity: 5
- Max quantity: 5
- Execution count: 4
- P&L: +$300

### Example 3: Position Reversal (Long → Short)

**Executions:**
```
BUY 5 @ $25,000 (10:00)
SELL 8 @ $25,050 (10:15)
```

**Position Building:**
```
Event 1: position_start
  - Running qty: 0 → +5
  - Create Position 1: LONG, qty=5, status=OPEN

Event 2: position_reversal
  - Running qty: +5 → -3
  - Close Position 1: status=CLOSED
  - Create Position 2: SHORT, qty=3, status=OPEN
```

**P&L Calculation (Position 1 - LONG):**
```
FIFO Match: 5 qty @ entry $25,000, exit $25,050
Points P&L: (25,050 - 25,000) × 5 = 250 points
Dollars P&L: 250 × $2 = $500
```

**Result:**
- 2 positions created
- Position 1: CLOSED LONG, qty=5, P&L=+$500
- Position 2: OPEN SHORT, qty=3, P&L=undefined (still open)

### Example 4: Open Position

**Executions:**
```
BUY 2 @ $25,000 (10:00)
BUY 3 @ $25,010 (10:05)
SELL 2 @ $25,030 (10:15)
[End of day - no more executions]
```

**Position Building:**
```
Event 1: position_start
  - Running qty: 0 → +2
  - Create Position: LONG, qty=2, max=2, status=OPEN

Event 2: position_modify
  - Running qty: +2 → +5
  - Update Position: qty=5, max=5

Event 3: position_modify
  - Running qty: +5 → +3
  - Update Position: qty=3, max=5

[End of processing - position remains OPEN]
```

**P&L Calculation:**
```
Entries: 2 @ $25,000, 3 @ $25,010
Exits: 2 @ $25,030

FIFO Match: 2 qty @ entry $25,000, exit $25,030
  Points: (25,030 - 25,000) × 2 = 60 points
  Dollars: $120

Unmatched: 3 qty @ $25,010 (no exit yet)
  No P&L contribution
```

**Result:**
- 1 OPEN position
- Total quantity: 3 (remaining open)
- Max quantity: 5 (peak position size)
- Execution count: 3
- Partial P&L: +$120 (from 2 contracts closed)
- Average entry price: $25,006 (weighted average)
- Average exit price: None (position still open)

### Example 5: Duplicates with Deduplication

**Raw CSV Import (with duplicates):**
```
Entry Exec ID: ABC123, BUY 1 @ $25,000 (10:00)
Entry Exec ID: ABC123, BUY 1 @ $25,000 (10:00)
Entry Exec ID: ABC123, BUY 2 @ $25,000 (10:00)
Entry Exec ID: ABC123, BUY 2 @ $25,000 (10:00)

Entry Exec ID: DEF456, SELL 6 @ $25,050 (10:15)
```

**After Deduplication:**
```
Entry Exec ID: ABC123, BUY 2 @ $25,000 (10:00)  [kept highest qty]
Entry Exec ID: DEF456, SELL 6 @ $25,050 (10:15)
```

**Position Building:**
```
Event 1: position_start
  - Running qty: 0 → +2
  - Create Position: LONG, qty=2, status=OPEN

Event 2: position_reversal
  - Running qty: +2 → -4
  - Close Position 1: LONG, qty=2, status=CLOSED
  - Create Position 2: SHORT, qty=4, status=OPEN
```

**Key Insight:**
Without deduplication, the system would see 4 BUY executions totaling 6 contracts, leading to incorrect position tracking. Deduplication ensures accuracy.

## Validation and Edge Cases

### Open Position Validation

All OPEN positions **must** satisfy:
- `position_status == PositionStatus.OPEN`
- `total_quantity > 0` (non-zero running quantity)
- `exit_time is None` (no complete exit yet)
- `average_exit_price is None` (no complete exit yet)

The position builder validates these invariants when marking a position as OPEN.

### Position Reversal Detection

A reversal is detected when:
```python
(previous_quantity > 0 and running_quantity < 0) or
(previous_quantity < 0 and running_quantity > 0)
```

The algorithm **must**:
1. Close the old position (even though qty ≠ 0)
2. Calculate P&L for the matched portion
3. Immediately start a new position in opposite direction
4. Set new position quantity to `abs(running_quantity)`

### Zero Quantity Handling

When `running_quantity == 0`:
- If position was OPEN → mark as CLOSED
- If no position exists → no action (waiting for next position_start)
- Never create a position with quantity = 0

### Missing Execution IDs

For trades without `entry_execution_id`:
- Fall back to grouping by (entry_time, side_of_market, entry_price)
- Log a warning for visibility
- Continue processing (don't fail)

This ensures backward compatibility with older data exports.

## Performance Characteristics

- **Deduplication**: O(n) where n = number of trades
- **Sorting**: O(n log n) for chronological ordering
- **Position Building**: O(n) after sorting
- **FIFO Matching**: O(m × e) where m = matched pairs, e = exits

For typical datasets (100-1000 trades), total processing time: <100ms

## Common Pitfalls

### ❌ Pitfall 1: Using Pre-Calculated P&L
**Wrong**: Trust `dollars_gain_loss` from individual trade records
**Right**: Ignore it and recalculate using FIFO matching

### ❌ Pitfall 2: Skipping Deduplication
**Wrong**: Build positions directly from CSV import
**Right**: Always deduplicate by `entry_execution_id` first

### ❌ Pitfall 3: Ignoring Position Reversals
**Wrong**: Treat reversal as simple position_modify
**Right**: Close old position, create new position in opposite direction

### ❌ Pitfall 4: Marking Open Positions as Closed
**Wrong**: Set status=CLOSED when processing ends
**Right**: Check if running_qty == 0, only then mark CLOSED

### ❌ Pitfall 5: Incorrect FIFO Matching
**Wrong**: Match exits to entries in database order
**Right**: Sort by entry_time before matching

## Testing Strategy

### Unit Tests

1. **Deduplication**:
   - Multiple trades with same execution_id → keep one
   - Trades without execution_id → fallback grouping
   - Mixed scenario → both strategies work

2. **Quantity Flow Analysis**:
   - Simple position (0 → +5 → 0) → position_start, position_close
   - Scaled entry → position_start, position_modify events
   - Reversal → position_reversal event

3. **FIFO P&L**:
   - Single entry/exit → correct P&L
   - Multiple entries/exits → FIFO order respected
   - Partial fill matching → correct quantity distribution

### Integration Tests

1. **End-to-End Position Rebuild**:
   - Import CSV with duplicates
   - Deduplicate executions
   - Build positions
   - Verify position count, status, quantities

2. **Real Data Validation**:
   - Process actual NinjaTrader export
   - Compare position count before/after deduplication
   - Verify open positions have correct status

3. **Edge Case Coverage**:
   - Position reversal creates 2 positions
   - Partial close leaves position OPEN
   - Empty execution list → no positions

## Future Enhancements

### Potential Improvements

1. **Performance**: Cache deduplication results to avoid re-processing
2. **Validation**: Add integrity checks comparing execution totals to position totals
3. **Reporting**: Generate deduplication metrics dashboard
4. **Alternative P&L**: Support LIFO or average-cost calculation methods
5. **Multi-Instrument**: Optimize batch processing for multiple instruments

### Known Limitations

1. **Timezone**: Assumes all timestamps are in same timezone
2. **Partial Fills**: Treats each fill as separate execution (correct for NinjaTrader)
3. **Currency**: Hardcoded USD for dollar P&L calculations
4. **Multiplier**: Requires manual configuration in `instrument_multipliers.json`

## Conclusion

The Position Builder is a sophisticated algorithm that transforms raw execution data into meaningful trading positions. Understanding the **quantity flow model**, **FIFO P&L calculation**, and **deduplication strategy** is essential for maintaining and enhancing this critical system component.

Key takeaways:
- Positions are defined by quantity flow (0 → +/- → 0)
- Deduplication by execution_id prevents double-counting
- FIFO matching ensures accurate, tax-compliant P&L
- Open positions have running_qty ≠ 0 and status = OPEN
- The state machine (QuantityFlowAnalyzer) drives position lifecycle

For questions or clarifications, refer to the source code comments in:
- `domain/services/position_builder.py`
- `domain/services/quantity_flow_analyzer.py`
- `domain/services/pnl_calculator.py`
