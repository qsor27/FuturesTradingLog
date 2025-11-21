# Spec Tasks

## Tasks

- [x] 1. Refactor ExecutionProcessing.py to output individual executions
  - [x] 1.1 Write tests for individual execution output format
  - [x] 1.2 Remove open_positions queue and FIFO pairing logic (lines 146-244)
  - [x] 1.3 Create execution record for each CSV row with proper field mapping
  - [x] 1.4 Ensure Entry executions have exit_price=None, exit_time=None
  - [x] 1.5 Ensure Exit executions are stored as individual records (not paired)
  - [x] 1.6 Maintain account separation in execution records
  - [x] 1.7 Verify tests pass for execution output format

- [ ] 2. Verify position builder handles individual executions correctly
  - [ ] 2.1 Review position_builder.py quantity flow analysis
  - [ ] 2.2 Review pnl_calculator.py entry/exit separation logic
  - [ ] 2.3 Review FIFOCalculator in pnl.py
  - [ ] 2.4 Confirm average price calculations work with individual executions
  - [ ] 2.5 Test with sample data (first 11 executions from CSV)

- [ ] 3. End-to-end integration testing
  - [ ] 3.1 Clear all data from database (trades, positions, imported_executions)
  - [ ] 3.2 Import NinjaTrader_Executions_20251003.csv via file watcher
  - [ ] 3.3 Verify 46 individual executions stored in trades table
  - [ ] 3.4 Verify positions table contains 2 closed positions (one per account)
  - [ ] 3.5 Verify average_entry_price = 24992.00 for both positions (first cycle)
  - [ ] 3.6 Verify average_exit_price = 24988.00 for both positions (first cycle)
  - [ ] 3.7 Verify total_dollars_pnl = -$48.00 for each account (first cycle)
  - [ ] 3.8 Open browser and verify positions page displays correct data

- [ ] 4. Regression testing
  - [ ] 4.1 Test deduplication system still works (re-import same CSV)
  - [ ] 4.2 Verify no duplicate executions imported
  - [ ] 4.3 Test with multiple CSV files from different days
  - [ ] 4.4 Verify all tests pass for position builder and P&L calculator
