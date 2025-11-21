# Spec Tasks

These are the tasks to be completed for the spec detailed in @agent-os/specs/2025-11-11-position-dashboard-fix/spec.md

> Created: 2025-11-11
> Status: Ready for Implementation

## Tasks

- [ ] 1. Fix Position Building Algorithm
  - [ ] 1.1 Write tests for position boundary detection in quantity_flow_analyzer.py
  - [ ] 1.2 Fix _identify_position_boundaries() method to correctly detect quantity returning to zero
  - [ ] 1.3 Fix partial fill aggregation logic
  - [ ] 1.4 Add proper handling for Buy-to-Cover and Sell-to-Close execution types
  - [ ] 1.5 Fix build_positions_from_executions() in enhanced_position_service_v2.py
  - [ ] 1.6 Add validation for minimum execution count and deduplication
  - [ ] 1.7 Add logging for position boundary detection decisions
  - [ ] 1.8 Verify all position building tests pass

- [ ] 2. Fix Execution Data Integrity
  - [ ] 2.1 Write tests for execution data parsing and validation
  - [ ] 2.2 Fix entry_price field population in domain/models/trade.py
  - [ ] 2.3 Fix CSV parsing in scripts/ExecutionProcessing.py to correctly extract prices
  - [ ] 2.4 Add validation to reject executions with missing required fields
  - [ ] 2.5 Implement data sanitization for price data
  - [ ] 2.6 Verify all execution data integrity tests pass

- [ ] 3. Fix P&L Calculation Engine
  - [ ] 3.1 Write tests for P&L calculations (Long and Short positions)
  - [ ] 3.2 Fix calculate_points_pnl() in domain/services/pnl_calculator.py
  - [ ] 3.3 Fix calculate_dollar_pnl() with correct instrument multipliers
  - [ ] 3.4 Verify instrument_multipliers.json has correct values (MNQ=2, MES=5)
  - [ ] 3.5 Add validation to prevent extreme P&L values
  - [ ] 3.6 Fix commission calculations
  - [ ] 3.7 Verify all P&L calculation tests pass

- [ ] 4. Fix Dashboard Statistics Aggregation
  - [ ] 4.1 Write tests for dashboard statistics calculations
  - [ ] 4.2 Fix get_aggregate_statistics() in position_service.py for Total P&L
  - [ ] 4.3 Fix Win Rate calculation formula
  - [ ] 4.4 Fix Avg Executions/Position calculation
  - [ ] 4.5 Add proper NULL/None handling for incomplete positions
  - [ ] 4.6 Fix JavaScript number formatting in templates/positions/dashboard.html
  - [ ] 4.7 Verify all dashboard statistics tests pass

- [ ] 5. Add Position State Validation
  - [ ] 5.1 Write tests for position state validation
  - [ ] 5.2 Add validate_state() method to Position model in domain/models/pnl.py
  - [ ] 5.3 Implement validation checks (Open positions, Closed positions, quantities)
  - [ ] 5.4 Add is_valid property to Position model
  - [ ] 5.5 Add validation step to rebuild_positions.py before saving
  - [ ] 5.6 Implement optional strict mode to reject invalid positions
  - [ ] 5.7 Verify all validation tests pass

- [ ] 6. Create Database Cleanup Utilities
  - [ ] 6.1 Write tests for cleanup operations
  - [ ] 6.2 Create scripts/cleanup_database.py with CLI interface
  - [ ] 6.3 Implement --delete-all-positions flag
  - [ ] 6.4 Implement --delete-all-executions flag
  - [ ] 6.5 Implement --delete-all-trades flag for full reset
  - [ ] 6.6 Add confirmation prompts and record count display
  - [ ] 6.7 Add logging for audit trail
  - [ ] 6.8 Verify all cleanup utility tests pass

- [ ] 7. Add Database Schema Changes
  - [ ] 7.1 Create migration script for validation fields (is_valid, validation_errors, last_validated_at)
  - [ ] 7.2 Add performance indexes (idx_positions_status_account, idx_positions_pnl)
  - [ ] 7.3 Run migration on development database
  - [ ] 7.4 Verify schema changes with verification queries

- [ ] 8. Create API Endpoints
  - [ ] 8.1 Write tests for validation and cleanup API endpoints
  - [ ] 8.2 Create GET /api/positions/validate endpoint
  - [ ] 8.3 Create POST /api/database/cleanup endpoint
  - [ ] 8.4 Update GET /api/statistics/dashboard with validation metrics
  - [ ] 8.5 Create PositionValidationController
  - [ ] 8.6 Create DatabaseCleanupController
  - [ ] 8.7 Verify all API endpoint tests pass

- [ ] 9. Integration Testing and Validation
  - [ ] 9.1 Delete all existing positions and executions using cleanup utility
  - [ ] 9.2 Re-import NinjaTrader CSV files with fixed code
  - [ ] 9.3 Run verification queries to check data integrity
  - [ ] 9.4 Verify dashboard displays correct Total P&L, Win Rate, and Avg Executions
  - [ ] 9.5 Verify no positions have contradictory states
  - [ ] 9.6 Verify all positions have correct entry/exit prices
  - [ ] 9.7 Run full test suite and ensure all tests pass
