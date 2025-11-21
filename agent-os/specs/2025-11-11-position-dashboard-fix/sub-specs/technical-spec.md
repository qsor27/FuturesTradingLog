# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-11-11-position-dashboard-fix/spec.md

## Technical Requirements

### 1. Position Building Algorithm Fixes

**File:** `domain/services/quantity_flow_analyzer.py`

- Fix the `_identify_position_boundaries()` method to correctly detect when quantity returns to zero
- Ensure partial fills are properly aggregated into single positions
- Add validation to prevent position boundaries from being detected mid-execution sequence
- Implement proper handling of Buy-to-Cover and Sell-to-Close execution types
- Add logging for position boundary detection decisions

**File:** `services/enhanced_position_service_v2.py`

- Fix the `build_positions_from_executions()` method to properly handle execution ordering
- Ensure execution timestamps are correctly used for position entry/exit times
- Add validation for minimum execution count per position (must be >= 1)
- Implement deduplication logic to prevent duplicate position creation

### 2. Execution Data Integrity

**Files:** `domain/models/trade.py`, `scripts/ExecutionProcessing.py`

- Ensure `entry_price` field is properly populated from execution data (never 0.00 unless legitimate)
- Fix CSV parsing to correctly extract price data from all execution types
- Add validation to reject executions with missing required fields
- Implement data sanitization to prevent malformed price data

### 3. P&L Calculation Engine Fixes

**File:** `domain/services/pnl_calculator.py`

- Fix `calculate_points_pnl()` to use correct entry/exit price logic
- Fix `calculate_dollar_pnl()` to apply proper instrument multipliers
- Ensure Long vs Short position P&L formulas are correctly applied:
  - Long: (Exit Price - Entry Price) × Quantity × Multiplier
  - Short: (Entry Price - Exit Price) × Quantity × Multiplier
- Add validation to prevent extreme P&L values (e.g., > $1M for micro contracts)
- Fix commission calculations to use actual commission data

**File:** `data/config/instrument_multipliers.json`

- Verify all instrument multipliers are correct (MNQ = 2, MES = 5, etc.)
- Add validation to ensure multipliers are loaded correctly

### 4. Dashboard Statistics Aggregation

**File:** `position_service.py`

- Fix `get_aggregate_statistics()` method to correctly sum P&L across all positions
- Fix Win Rate calculation: `(winning_positions / total_closed_positions) × 100`
- Fix Avg Executions/Position: `total_executions / total_positions`
- Add proper NULL/None handling for incomplete positions
- Ensure only closed positions are included in Win Rate calculations

**File:** `templates/positions/dashboard.html`

- Fix JavaScript formatting for large negative numbers
- Add client-side validation to detect and highlight anomalous values
- Implement proper decimal precision for currency display

### 5. Position State Validation

**File:** `domain/models/pnl.py`

- Add `validate_state()` method to Position model
- Implement checks:
  - Open positions must NOT have exit_time
  - Closed positions must have both entry_time and exit_time
  - Closed positions must have exit_price > 0
  - Position quantity must match sum of execution quantities
- Add `is_valid` property to Position model

**File:** `rebuild_positions.py`

- Add validation step before saving positions to database
- Log all validation failures for manual review
- Implement optional strict mode to reject invalid positions

### 6. Database Cleanup Utilities

**New File:** `scripts/cleanup_database.py`

- Provide `--delete-all-positions` flag to truncate positions table
- Provide `--delete-all-executions` flag to truncate executions table
- Provide `--delete-all-trades` flag to delete everything and reset
- Add confirmation prompts to prevent accidental deletion
- Display count of records before deletion
- Log deletion operations for audit trail

**Purpose:** Enable clean slate for re-importing CSV data after fixes are applied, rather than attempting to repair corrupted data

## External Dependencies

No new external dependencies required. All fixes use existing libraries:
- Pandas 2.1.4 for data manipulation
- SQLAlchemy for database operations
- Flask for web framework
