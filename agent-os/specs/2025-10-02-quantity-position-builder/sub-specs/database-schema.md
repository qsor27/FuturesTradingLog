# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-10-02-quantity-position-builder/spec.md

## No Schema Changes Required

This spec does not require any database schema modifications. The existing schema already supports all required functionality:

### Existing Schema Support

**trades table:**
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    instrument TEXT,
    side_of_market TEXT,
    quantity INTEGER,
    entry_price REAL,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    exit_price REAL,
    points_gain_loss REAL,
    dollars_gain_loss REAL,
    commission REAL,
    account TEXT,
    entry_execution_id TEXT,  -- ✓ Already exists for deduplication
    -- ... other fields
);
```

**positions table:**
```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    instrument TEXT,
    account TEXT,
    position_type TEXT,  -- 'long' or 'short'
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,  -- NULL for open positions
    total_quantity INTEGER,
    average_entry_price REAL,
    average_exit_price REAL,  -- NULL for open positions
    total_points_pnl REAL,
    total_dollars_pnl REAL,
    total_commission REAL,
    position_status TEXT,  -- 'open' or 'closed' ✓ Already supports
    execution_count INTEGER,
    max_quantity INTEGER,
    risk_reward_ratio REAL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    soft_deleted INTEGER
);
```

**position_executions table:**
```sql
CREATE TABLE position_executions (
    id INTEGER PRIMARY KEY,
    position_id INTEGER NOT NULL,
    trade_id INTEGER NOT NULL,
    execution_order INTEGER NOT NULL,
    FOREIGN KEY (position_id) REFERENCES positions (id),
    FOREIGN KEY (trade_id) REFERENCES trades (id),
    UNIQUE(position_id, trade_id)
);
```

### Schema Validation

The existing schema supports:
- ✓ `entry_execution_id` field for deduplication
- ✓ `position_status` with 'open' and 'closed' values
- ✓ NULL `exit_time` and `exit_price` for open positions
- ✓ `position_executions` mapping for tracking which trades belong to which position

### Index Verification

**Existing indexes support efficient queries:**
```sql
-- For finding trades to deduplicate
CREATE INDEX IF NOT EXISTS idx_entry_execution_id ON trades(entry_execution_id);

-- For position queries
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(position_status);
CREATE INDEX IF NOT EXISTS idx_positions_account_instrument ON positions(account, instrument);

-- For execution mapping
CREATE INDEX IF NOT EXISTS idx_position_executions_position_id ON position_executions(position_id);
```

### Query Patterns

**Find all open positions:**
```sql
SELECT * FROM positions
WHERE position_status = 'open'
  AND soft_deleted = 0
ORDER BY entry_time DESC;
```

**Find trades with same execution ID:**
```sql
SELECT * FROM trades
WHERE entry_execution_id = ?
ORDER BY id;
```

**Find executions for a position:**
```sql
SELECT t.*
FROM trades t
JOIN position_executions pe ON t.id = pe.trade_id
WHERE pe.position_id = ?
ORDER BY pe.execution_order;
```

## Rationale

No schema changes are needed because:
1. The `entry_execution_id` field already exists in the trades table
2. The `position_status` enum already supports 'open' and 'closed'
3. Open positions can be represented by NULL `exit_time` and `exit_price`
4. All required indexes already exist for efficient queries

This spec focuses on application logic enhancements, not data model changes.
