# Database Schema

This is the database schema implementation for the spec detailed in @agent-os/specs/2025-11-11-position-dashboard-fix/spec.md

## Schema Changes

### 1. Add Validation Fields to Positions Table

**Migration:** Add optional validation tracking columns

```sql
ALTER TABLE positions ADD COLUMN is_valid BOOLEAN DEFAULT 1;
ALTER TABLE positions ADD COLUMN validation_errors TEXT DEFAULT NULL;
ALTER TABLE positions ADD COLUMN last_validated_at TIMESTAMP DEFAULT NULL;
```

**Rationale:** Track which positions have been validated and store any validation error messages for debugging and data quality monitoring.

### 2. Add Indexes for Performance

**Migration:** Add indexes to speed up aggregate queries

```sql
CREATE INDEX IF NOT EXISTS idx_positions_status_account
ON positions(status, account_id);

CREATE INDEX IF NOT EXISTS idx_positions_pnl
ON positions(net_pnl) WHERE status = 'Closed';
```

**Rationale:** Dashboard statistics queries filter by status and account frequently. P&L aggregation queries will be faster with dedicated index.

### 3. Add Execution Validation Constraint

**Migration:** Add check constraint to prevent invalid execution data

```sql
-- Note: SQLite doesn't support adding constraints to existing tables,
-- so this would be enforced at the application level via validation

-- Conceptual constraint:
-- CHECK (entry_price > 0 OR side = 'BuyToCover' OR side = 'SellToClose')
```

**Rationale:** Prevent 0.00 entry prices from being stored except for covering/closing executions where it may be legitimate.

## Database Cleanup Operations

### Cleanup Script: `scripts/cleanup_database.py`

**Purpose:** Delete all positions and executions for clean re-import after fixes

**Operations:**

1. **Delete All Positions:**
   ```sql
   DELETE FROM positions;
   DELETE FROM sqlite_sequence WHERE name='positions';
   ```

2. **Delete All Executions:**
   ```sql
   DELETE FROM executions;
   DELETE FROM sqlite_sequence WHERE name='executions';
   ```

3. **Full Reset (All Trading Data):**
   ```sql
   DELETE FROM positions;
   DELETE FROM executions;
   DELETE FROM sqlite_sequence WHERE name IN ('positions', 'executions');
   VACUUM; -- Reclaim disk space
   ```

**Safety Features:**
- Require explicit `--confirm` flag to proceed
- Display count of records to be deleted
- Log all deletion operations with timestamp
- No automatic backups (user should backup manually if needed)

## Verification Queries

After re-import with fixes applied, run these queries to verify data integrity:

```sql
-- Should return 0: No open positions with exit times
SELECT COUNT(*) FROM positions
WHERE status = 'Open' AND exit_time IS NOT NULL;

-- Should return 0: No closed positions without exit times
SELECT COUNT(*) FROM positions
WHERE status = 'Closed' AND exit_time IS NULL;

-- Should return 0: No positions with 0.00 entry price (except covers/closes)
SELECT COUNT(*) FROM positions
WHERE avg_entry_price = 0 AND position_type NOT IN ('BuyToCover', 'SellToClose');

-- Should return reasonable value: Total P&L should be within expected range
SELECT SUM(net_pnl) as total_pnl FROM positions WHERE status = 'Closed';
-- Expected: Between -$100k and +$100k for typical trader

-- Should match: Total executions should equal sum of position execution counts
SELECT
  (SELECT COUNT(*) FROM executions) as total_executions,
  (SELECT SUM(execution_count) FROM positions) as position_executions;
```
