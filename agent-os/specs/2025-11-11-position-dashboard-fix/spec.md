# Spec Requirements Document

> Spec: Position Building and Dashboard Statistics Fix
> Created: 2025-11-11

## Overview

Fix critical position building algorithm failures and dashboard calculation errors that are causing incorrect P&L calculations, missing execution data, and contradictory position states. This fix will restore data integrity and accurate performance tracking for the futures trading analytics platform.

## User Stories

### Accurate Position Tracking

As a trader, I want my positions to be correctly built from my execution data, so that I can trust the P&L calculations and performance metrics displayed on my dashboard.

**Workflow:** When NinjaTrader CSV files are imported, executions should be correctly grouped into positions based on quantity flow (0 → +/- → 0). Each position should have accurate entry/exit prices, correct P&L calculations, and proper state management (open vs closed).

### Reliable Dashboard Metrics

As a trader, I want the dashboard statistics to accurately reflect my trading performance, so that I can make informed decisions about my trading strategy.

**Workflow:** The dashboard should display correct Total P&L (not negative millions), accurate Win Rate percentages, proper Avg Executions/Position counts, and all statistics should update in real-time as new trades are imported.

### Data Integrity Validation

As a trader, I want the system to prevent and detect data integrity issues, so that I don't make decisions based on corrupt or incorrect data.

**Workflow:** The system should validate that positions don't have contradictory states (e.g., "Open" with an exit time), that execution prices are properly captured, and that position boundaries are correctly detected. Any anomalies should be logged and reported.

## Spec Scope

1. **Position Building Algorithm** - Fix the quantity flow analyzer to correctly detect position boundaries and prevent incorrect splitting/joining of positions
2. **Execution Data Integrity** - Ensure all execution entry/exit prices are properly captured and stored (fix 0.00 values)
3. **P&L Calculation Engine** - Fix the P&L calculator to properly compute points and dollar P&L using correct multipliers
4. **Dashboard Statistics Aggregation** - Fix Total P&L, Win Rate, and Avg Executions/Position calculations
5. **Position State Validation** - Add validation to prevent contradictory states (e.g., Open positions with exit times)
6. **Database Cleanup Utilities** - Provide utilities to delete all positions and executions for clean re-import

## Out of Scope

- Changes to the UI/UX design of the dashboard
- Adding new dashboard metrics or statistics
- Modifications to the CSV import file format
- Changes to the TradingView chart integration
- Performance optimizations (unless directly related to calculation accuracy)
- Migration or repair of existing broken data (delete and re-import instead)

## Expected Deliverable

1. Dashboard displays accurate Total P&L, Win Rate, and Avg Executions/Position metrics after fresh import
2. All newly imported positions have correct entry/exit prices and accurate P&L calculations
3. Position states are consistent (no contradictory Open/Closed states with exit times)
4. Database cleanup utility to delete all positions/executions and enable clean re-import
5. All calculation logic has comprehensive test coverage
