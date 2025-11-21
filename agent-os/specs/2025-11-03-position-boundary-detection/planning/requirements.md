# Position Boundary Detection Fix - Requirements

## Problem Statement

The position building system is incorrectly combining multiple separate trading sequences into single positions when the quantity returns to zero between sequences. This causes inflated position quantities (70-102 contracts instead of 6-12) and incorrect P&L calculations.

## Evidence

From browser inspection of production data on 2025-11-03:
- Position for APEX1279810000057 shows **quantity 70** with 20 executions
- Should be 3-4 separate positions of 6 contracts each
- Clear "flat" moments (quantity = 0) where new positions should start:
  - 11:27:23 AM: Buy 6 (qty = 6)
  - 11:27:32 AM: Sell 1,1,2,2 = Sell 6 total (qty = 0) ✅ FLAT
  - 11:27:36 AM: Buy 6 (qty = 6) ← **Should start NEW position**
  - Pattern repeats throughout the day

## Root Cause Analysis

Based on code analysis and user confirmation:

1. **Database Trade Records**: ✅ CORRECT - Each execution has unique record with proper IDs
2. **QuantityFlowAnalyzer**: ✅ CORRECT - Properly detects `position_close` events when qty = 0 (line 153-154)
3. **Bug Location**: ❌ `EnhancedPositionServiceV2._build_positions_with_trade_mapping()` (lines 341-389)
   - When `position_close` event occurs, the `current_trade_ids` list is NOT being cleared
   - Next `position_start` event inherits trade IDs from previous position
   - Result: Multiple separate positions are combined into one mega-position

## Requirements

### 1. Fix Position Boundary Detection
- **MUST**: Clear `current_trade_ids` list when `position_close` event is detected
- **MUST**: Ensure each new `position_start` begins with empty trade list
- **MUST**: Only modify boundary detection logic - no changes to P&L, commissions, or other calculations
- **MUST**: Handle all position lifecycle events correctly:
  - `position_start`: quantity 0 → non-zero
  - `position_modify`: quantity changes but doesn't reach 0
  - `position_close`: quantity returns to 0
  - `position_reverse`: quantity changes sign without reaching 0

### 2. Test Coverage
- **MUST**: Create test reproducing exact scenario:
  - Buy 6 → Sell 6 (flat) → Buy 6 → Sell 6
  - Expected: 2 separate positions
  - Current bug: 1 position with combined data
- **MUST**: Add test to existing test suite for position building
- **SHOULD**: Test with real execution data from CSV lines 14-43

### 3. Database Rebuild
- **MUST**: Provide script to rebuild existing incorrectly-combined positions
- **MUST**: Script should:
  - Clear positions and position_executions tables for affected account/instrument pairs
  - Re-run position building with fixed logic
  - Report: positions before/after, accounts affected, execution count
  - Support dry-run mode to preview changes

### 4. Universal Fix
- **MUST**: Fix applies to all accounts (not account-specific logic)
- **MUST**: Preserve existing account separation (already working correctly)
- **MUST**: Maintain chronological timestamp ordering (already working correctly)

## Out of Scope

- ❌ Changes to P&L calculation logic
- ❌ Changes to commission tracking
- ❌ Changes to execution ID deduplication
- ❌ Changes to quantity flow analyzer (already correct)
- ❌ Changes to trade data integrity (already correct)

## Acceptance Criteria

1. **Test passes**: Buy 6 → Sell 6 (flat) → Buy 6 → Sell 6 creates 2 positions
2. **Production fix**: APEX1279810000057 position with quantity 70 splits into 3-4 positions of 6 contracts each after rebuild
3. **All affected accounts fixed**: SimAccount1, SimAccount2, APEX1279810000057, APEX1279810000058
4. **No regressions**: Existing position building tests continue to pass
5. **Rebuild script works**: User can run script to fix historical data

## Technical Details

### Files to Modify
1. `services/enhanced_position_service_v2.py` - Fix `_build_positions_with_trade_mapping()` method (lines 341-389)
2. Create new test in position building test suite
3. Create `scripts/rebuild_position_boundaries.py` - Rebuild script for historical data

### Key Code Location
```python
# File: services/enhanced_position_service_v2.py
# Method: _build_positions_with_trade_mapping() (lines 341-389)
# Issue: current_trade_ids not cleared on position_close
```

### Expected Fix Pattern
```python
for event in flow_events:
    if event['type'] == 'position_close':
        # Save current position with accumulated trade_ids
        positions.append(create_position(current_trade_ids))
        # BUG FIX: Clear trade_ids for next position
        current_trade_ids = []  # ← ADD THIS LINE
    elif event['type'] == 'position_start':
        # Start new position (should have empty trade_ids from previous close)
        current_trade_ids = [event['trade_id']]
```

## Success Metrics

- Positions correctly split at quantity = 0 boundaries
- Average position size returns to realistic 6-12 contracts
- P&L calculations accurate for individual position sequences
- No duplicate positions created
- Historical data corrected via rebuild script
