# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-10-07-execution-storage-fix/spec.md

## Technical Requirements

### 1. ExecutionProcessing.py Refactor

**Current Behavior (Lines 106-245):**
- Maintains `open_positions` queue per account
- Pairs entry executions with exit executions
- Calculates P&L during pairing
- Outputs complete round-trip trades with Entry Price, Exit Price, Entry Time, Exit Time

**Required Behavior:**
- Output each execution as an individual record
- For Entry executions (E/X = 'Entry'):
  - Set `entry_price` to the execution price
  - Set `exit_price` to None
  - Set `entry_time` to the execution timestamp
  - Set `exit_time` to None
  - Set `side_of_market` to 'Buy' or 'Sell'
  - Set `entry_execution_id` to the ID from CSV
- For Exit executions (E/X = 'Exit'):
  - Set `entry_price` to the execution price (the price at which exit occurred)
  - Set `exit_price` to None (this field is not used for individual executions)
  - Set `entry_time` to the execution timestamp
  - Set `exit_time` to None
  - Set `side_of_market` to 'Buy' or 'Sell'
  - Set `entry_execution_id` to the ID from CSV
- Remove FIFO pairing logic, open_positions queue, and P&L calculation
- Maintain account separation (each execution tagged with account)

### 2. Trade Data Structure

**Required Format for Individual Executions:**

```python
{
    'Instrument': 'MNQ DEC25',
    'Side of Market': 'Buy',  # or 'Sell'
    'Quantity': 6,
    'Entry Price': 24992.00,
    'Entry Time': datetime(2025, 10, 3, 13, 1, 58),
    'Exit Time': None,
    'Exit Price': None,
    'Result Gain/Loss in Points': 0.0,
    'Gain/Loss in Dollars': 0.0,
    'ID': '283532206773_1',  # execution_id from CSV
    'Commission': 0.0,
    'Account': 'APEX1279810000057'
}
```

### 3. Position Builder Integration

**Verification Requirements:**
- Confirm that `domain/services/position_builder.py` correctly processes individual executions
- Verify that `domain/services/pnl_calculator.py` separates entries from exits based on `side_of_market`
- Ensure `domain/models/pnl.py` FIFOCalculator handles individual executions
- Confirm that positions are built per account with correct running quantity tracking

### 4. Database Schema

**trades Table Fields Required:**
- `entry_execution_id` (TEXT) - unique execution ID from CSV
- `instrument` (TEXT)
- `account` (TEXT)
- `side_of_market` (TEXT) - 'Buy' or 'Sell'
- `quantity` (INTEGER)
- `entry_price` (REAL) - price at which execution occurred
- `exit_price` (REAL, nullable) - should be NULL for individual executions
- `entry_time` (TEXT/DATETIME)
- `exit_time` (TEXT/DATETIME, nullable) - should be NULL for individual executions
- `points_gain_loss` (REAL) - 0.0 for individual executions
- `dollars_gain_loss` (REAL) - 0.0 for individual executions
- `commission` (REAL)

### 5. Testing Requirements

- Clear database before test
- Import NinjaTrader_Executions_20251003.csv (46 executions, 2 accounts)
- Verify trades table contains 46 individual execution records
- Verify position builder creates 2 positions (one per account)
- Verify each position has correct average_entry_price, average_exit_price, total_dollars_pnl

**Expected Results for First Position Cycle:**
- Account APEX1279810000058: Entry @ 24992.00, Exit @ 24988.00, Quantity: 6, P&L: -$48.00
- Account APEX1279810000057: Entry @ 24992.00, Exit @ 24988.00, Quantity: 6, P&L: -$48.00
