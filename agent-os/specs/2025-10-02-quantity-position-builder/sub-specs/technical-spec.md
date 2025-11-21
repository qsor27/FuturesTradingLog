# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-10-02-quantity-position-builder/spec.md

## Technical Requirements

### 1. Execution Deduplication by ID

**Current Implementation:**
```python
def _deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
    # Groups by (entry_time, side_of_market, entry_price)
    trade_groups = defaultdict(list)
    for trade in trades:
        key = (trade['entry_time'], trade['side_of_market'], trade.get('entry_price'))
        trade_groups[key].append(trade)
```

**Required Change:**
```python
def _deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
    # Group by entry_execution_id (unique identifier from NinjaTrader)
    trade_groups = defaultdict(list)
    for trade in trades:
        exec_id = trade.get('entry_execution_id')
        if exec_id:
            trade_groups[exec_id].append(trade)
        else:
            # Fallback for trades without execution ID
            key = (trade['entry_time'], trade['side_of_market'], trade.get('entry_price'))
            trade_groups[f"FALLBACK_{key}"].append(trade)
```

**Rationale:** The `entry_execution_id` field uniquely identifies each execution from NinjaTrader. CSV import creates multiple database records (1,1,2,2 quantities) for the same execution due to how fills are recorded. Grouping by execution ID ensures each real execution is counted exactly once.

### 2. Open Position Detection

**Current Implementation:**
Position status is determined during position building but doesn't properly track the final quantity state.

**Required Enhancement:**

In `position_builder.py`, the `_aggregate_executions_into_positions()` method already handles open positions (line 201-206):
```python
# Handle any remaining open position
if current_position:
    current_position.position_status = PositionStatus.OPEN
    self._calculate_position_totals_from_executions(current_position, current_executions)
    positions.append(current_position)
```

**Additional Logic Needed:**
- Ensure `current_position.total_quantity` reflects the accurate running quantity at position end
- For open positions, calculate average entry price but leave exit price as None
- Add validation that OPEN positions have non-zero running quantity

### 3. Position Lifecycle State Machine

**States:**
- `QUANTITY_ZERO` - No active position (running_quantity = 0)
- `QUANTITY_POSITIVE` - Long position (running_quantity > 0)
- `QUANTITY_NEGATIVE` - Short position (running_quantity < 0)

**Events:**
- `position_start` - Transition from ZERO to POSITIVE/NEGATIVE
- `position_modify` - Remain in same state but change quantity
- `position_close` - Transition to ZERO (position complete)
- `position_reversal` - Direct transition from POSITIVE to NEGATIVE or vice versa (close old, start new)

**Implementation:**
Already implemented in `quantity_flow_analyzer.py` lines 99-130. Documentation should explain this state machine clearly.

### 4. FIFO P&L Calculation

**Algorithm:**
1. Separate executions into entries (increasing position) and exits (decreasing position)
2. Match exit quantities to entry quantities in chronological order (FIFO)
3. Calculate points P&L: (exit_price - entry_price) × quantity × multiplier
4. Sum all matched pairs for total position P&L

**Current Implementation:**
Located in `pnl_calculator.py` (referenced in position_builder.py line 243)

**Documentation Required:**
Detailed explanation of FIFO matching with examples showing multi-execution positions

### 5. Documentation Structure

**New File:** `docs/architecture/position-builder.md`

**Sections:**
1. **Overview**: Purpose and importance of quantity-based position building
2. **Core Concepts**:
   - Quantity flow analysis (0 → +/- → 0)
   - Execution vs Position vs Trade terminology
   - Why we ignore pre-calculated P&L on individual trades
3. **Deduplication Logic**:
   - entry_execution_id as unique identifier
   - How CSV imports create duplicates
   - Fallback strategy for missing execution IDs
4. **Position Lifecycle**:
   - State machine diagram (ASCII or mermaid)
   - Event types and transitions
   - Examples of each event type
5. **P&L Calculation**:
   - FIFO methodology explanation
   - Entry/exit matching algorithm
   - Commission and points multiplier handling
6. **Code Architecture**:
   - File structure and responsibilities
   - Key classes: PositionBuilder, QuantityFlowAnalyzer, PnLCalculator
   - Data flow from CSV → Trades → Positions
7. **Examples**:
   - Simple position: 1 entry, 1 exit
   - Scaled position: multiple entries, multiple exits
   - Position reversal: long → flat → short
   - Open position: entries without complete exit

### 6. Code Comments Enhancement

**Files to enhance:**
- `domain/services/position_builder.py` - Add method-level and critical logic comments
- `domain/services/quantity_flow_analyzer.py` - Document state transitions
- `services/enhanced_position_service_v2.py` - Explain deduplication and integration

**Comment Standards:**
- Every public method: Purpose, parameters, return value, example usage
- Critical algorithms: Step-by-step explanation of logic
- Edge cases: Why specific handling exists
- TODOs: Mark known limitations or future improvements

## Performance Considerations

- Deduplication by execution ID is O(n) operation - acceptable for typical dataset sizes (100-1000 trades)
- Sorting by entry_time remains O(n log n) - required for chronological processing
- Position building is O(n) after sorting - scales linearly with execution count

## Testing Requirements

1. **Unit Tests** for `_deduplicate_trades()`:
   - Multiple trades with same execution_id
   - Trades without execution_id (fallback)
   - Mixed scenario with both

2. **Integration Tests** for position building:
   - Closed position (0 → +qty → 0)
   - Open position (0 → +qty)
   - Position reversal (+qty → -qty)
   - Scaled entry and exit

3. **Data Validation Tests**:
   - Verify duplicate counts before/after deduplication
   - Verify position counts match expected based on quantity flow
   - Verify open positions have correct status and quantity

## External Dependencies

No new external dependencies required. All functionality can be implemented with existing stack:
- Python 3.11 standard library
- Existing domain models and services
- SQLite database (no schema changes needed)
