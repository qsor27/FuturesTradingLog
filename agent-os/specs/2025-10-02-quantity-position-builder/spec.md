# Spec Requirements Document

> Spec: Quantity-Based Position Builder with Open Position Detection
> Created: 2025-10-02

## Overview

Enhance the position builder to accurately detect open positions based on current CSV data and running quantity balance, while updating all documentation to explicitly support and explain the quantity-based (0 → +/- → 0) position building methodology.

## User Stories

### Trader with Open Position

As a futures trader, I want the system to correctly identify when I have an open position based on today's trade data, so that I can see my current market exposure and manage risk appropriately.

When a trader imports today's CSV file from NinjaTrader, the position builder should:
1. Deduplicate executions by `entry_execution_id` to prevent counting the same execution multiple times
2. Track the running quantity balance across all executions chronologically
3. Mark a position as OPEN when the quantity balance is non-zero at the end of the most recent execution
4. Mark a position as CLOSED when the quantity balance returns to 0
5. Display open positions prominently in the UI with current quantity and average entry price

### Developer Understanding Position Logic

As a developer maintaining the codebase, I want comprehensive documentation of the quantity flow algorithm, so that I can understand, debug, and extend the position building logic without breaking existing functionality.

The documentation should explain:
- Why we use quantity flow (0 → +/- → 0) instead of matching individual entry/exit trades
- How duplicate executions are detected and merged by `entry_execution_id`
- The complete position lifecycle: position_start → position_modify → position_close/position_reversal
- How P&L is calculated using FIFO methodology for aggregated executions
- Edge cases like position reversals and partial closes

### Data Analyst Verifying Accuracy

As a data analyst, I want clear technical specifications of how positions are built from raw executions, so that I can verify the accuracy of position aggregation and P&L calculations.

The technical documentation should include:
- Database schema showing the relationship between trades, positions, and position_executions
- Exact deduplication logic: grouping by `entry_execution_id` and summing quantities
- Quantity flow state machine with all possible transitions
- P&L calculation formulas showing FIFO matching algorithm
- Examples of real trade sequences and their resulting positions

## Spec Scope

1. **Execution Deduplication by ID** - Update `_deduplicate_trades()` to group by `entry_execution_id` instead of timestamp/price/side, summing quantities for duplicate imports
2. **Open Position Detection** - Enhance position builder to mark positions as OPEN when running quantity ≠ 0 at end of processing, with accurate current quantity tracking
3. **Developer Documentation** - Create comprehensive docs explaining quantity flow algorithm, deduplication logic, and position lifecycle in `docs/architecture/position-builder.md`
4. **Technical Specification** - Document the complete technical implementation including state machines, algorithms, and database schema in spec sub-docs
5. **Code Comments Enhancement** - Add detailed inline comments to `position_builder.py`, `quantity_flow_analyzer.py`, and `enhanced_position_service_v2.py` explaining critical logic

## Out of Scope

- UI changes to position display (will be handled separately)
- Historical position recalculation or migration (existing positions remain unchanged)
- Real-time position tracking during active trading sessions
- Integration with broker APIs for live position data
- Position P&L calculations for open positions (current average entry price is sufficient for this spec)

## Expected Deliverable

1. **Accurate Open Position Detection**: Running the rebuild with today's data shows correct OPEN vs CLOSED status, with open positions displaying current quantity and average entry price
2. **No Duplicate Execution Counting**: Positions built from CSV files with duplicate execution records correctly sum quantities by `entry_execution_id`, reducing position count to match actual trading activity
3. **Comprehensive Documentation**: Developer can read `docs/architecture/position-builder.md` and understand the complete quantity flow algorithm, deduplication strategy, and position lifecycle without reading source code
