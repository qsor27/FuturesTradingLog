# Position Logic Fixes

## Problem
Position service incorrectly interpreting trade records:
- **Current**: Each trade = independent position
- **Reality**: Each trade = portion of a position that was closed
- **Example**: 18-contract position → 3 exit trades of 6 contracts each

## Required Fixes

### 1. Fix Position Building Logic
```python
# Current (WRONG): Treating trades as position changes
# Required: Group related trades into original positions
position_groups = group_related_trades(trades)
for group in position_groups:
    position = {
        'total_quantity': sum(trade['quantity'] for trade in group),
        'executions': group,
        # ... other calculations
    }
```

### 2. Group Related Trades
- **Execution chains**: Related execution IDs
- **Time proximity**: Trades close in time
- **Link groups**: Manually linked trades

### 3. Add Debug Logging
- Trade processing details
- Position grouping decisions
- Quantity calculations

### 4. Create Debug Endpoint
- Show raw trade data
- Show grouping decisions
- Manual position rebuilding

## Files to Modify
- `position_service.py` - Core position building
- `routes/positions.py` - Debug endpoints
- `templates/positions/debug.html` - Debug view

## Expected Result
6-contract positions should show `total_quantity = 6` with proper trade grouping.