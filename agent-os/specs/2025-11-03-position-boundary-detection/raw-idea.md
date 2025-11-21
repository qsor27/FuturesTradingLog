# Raw Idea: Position Boundary Detection Fix

## Issue Description

Positions are being incorrectly combined across multiple separate trading sequences where the quantity should have returned to 0 and started a new position. This is causing inflated position quantities (e.g., 70-102 contracts instead of 6-12) and incorrect P&L calculations.

## Observed Problems

1. Positions show quantities like 70, 71, 84, 102 instead of correct 6-12 contracts
2. Multiple separate trading sequences (quantity going to 0 and restarting) are being combined into single positions
3. The quantity flow analyzer is not detecting position boundaries (when quantity returns to 0)
4. This affects all accounts: SimAccount1, SimAccount2, APEX1279810000057, APEX1279810000058
5. Execution breakdown shows 20+ executions in a single position that should be 3-4 separate positions

## Example from Browser Inspection

- Position for APEX1279810000057 shows quantity 70 with 20 executions
- Executions span from 11:27:23 AM to 1:19:05 PM
- Multiple "flat" moments (quantity = 0) where positions should have closed:
  - 11:27:32 AM: 6 sells after 6 buys = flat, then 11:27:36 AM: 6 buys = new position
  - 11:28:09 AM: 6 sells after 6 buys = flat, then 11:28:43 AM: 6 buys = new position
  - And continues throughout the day

## Root Cause

The QuantityFlowAnalyzer in `domain/services/quantity_flow_analyzer.py` is not correctly detecting when running quantity returns to 0, which should trigger a position_close event and start a new position.

## Current Implementation

- EnhancedPositionServiceV2 (`services/enhanced_position_service_v2.py`) rebuilds positions per account/instrument
- Uses QuantityFlowAnalyzer to track quantity flow and detect position boundaries
- Should detect: position_start (0 -> non-zero), position_close (returns to 0), position_modify (quantity changes)
