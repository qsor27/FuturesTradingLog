# Spec Requirements Document

> Spec: Execution Storage Architecture Fix
> Created: 2025-10-07

## Overview

Fix the execution storage architecture to store individual executions instead of pre-paired trades, ensuring the position builder can correctly track running quantity balances and build positions using FIFO methodology per account. This resolves the position builder failure where average entry/exit prices show as 0.0 and P&L calculations fail.

## User Stories

### Trade Importer - Store Individual Executions

As a trader, I want the system to store each execution (entry or exit) as a separate record, so that the position builder can accurately track my running position quantities and calculate P&L using proper FIFO matching.

**Workflow:** When I export a NinjaTrader execution CSV file and place it in the data directory, the system should import each execution as an individual record with its timestamp, price, quantity, and action (Buy/Sell). The system should NOT pre-pair executions into complete trades during import. Each account's executions are tracked separately.

### Position Builder - Calculate from Executions

As a trader, I want the position builder to calculate my positions from individual executions using FIFO methodology, so that I see accurate average entry prices, average exit prices, and P&L for each position per account.

**Workflow:** After importing executions, the position builder analyzes all executions chronologically per account, tracks running quantity (0 → +/- → 0), matches entry executions with exit executions using FIFO, and creates position records with correct average prices and P&L calculations.

## Spec Scope

1. **Refactor ExecutionProcessing.py** - Remove the trade pairing logic (lines 106-245) and output individual executions instead of complete round-trip trades
2. **Store Individual Executions** - Ensure each execution is stored in the trades table as a separate record with entry_price set and exit_price=None for entries, or exit_price set for exits
3. **Account Separation** - Maintain strict account separation during execution storage and position building (each account has independent position tracking)
4. **Position Builder Verification** - Verify the existing position builder correctly processes individual executions and calculates positions with accurate average prices and P&L
5. **Database Schema Alignment** - Ensure the trades table schema supports storing individual executions with proper fields (entry_execution_id, entry_price, exit_price nullable, quantity, side_of_market)

## Out of Scope

- Changes to the position builder algorithm (quantity flow analysis)
- Changes to the FIFO P&L calculator
- UI/UX modifications to the positions page
- Modifications to the file watcher or import service
- Changes to the deduplication system (already implemented in 2025-10-03 spec)

## Expected Deliverable

1. Import a NinjaTrader execution CSV file and verify that individual executions are stored in the trades table (not pre-paired trades)
2. Open the positions page in the browser and verify that positions show correct average_entry_price, average_exit_price, and total_dollars_pnl values (not 0.0)
3. Verify that two separate accounts in the same CSV file produce two separate positions with independent P&L calculations
