# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-10-03-csv-import-reliability/spec.md

> Created: 2025-10-03
> Version: 1.0.0

## Schema Changes

### New Table: imported_executions

**Purpose:** Track all imported execution IDs to prevent duplicate imports when CSV files are re-processed or deleted trades are re-imported.

**Table Definition:**
```sql
CREATE TABLE imported_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id VARCHAR(255) NOT NULL UNIQUE,
    csv_filename VARCHAR(255) NOT NULL,
    import_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    account VARCHAR(50),
    instrument VARCHAR(50),
    UNIQUE(execution_id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_imported_executions_exec_id ON imported_executions(execution_id);
CREATE INDEX idx_imported_executions_csv_file ON imported_executions(csv_filename);
CREATE INDEX idx_imported_executions_timestamp ON imported_executions(import_timestamp);
```

**Field Descriptions:**
- `id`: Auto-increment primary key
- `execution_id`: Unique execution identifier from NinjaTrader CSV (e.g., "abc123def456")
- `csv_filename`: Source CSV file where this execution was imported from (for audit trail)
- `import_timestamp`: When this execution was first imported
- `account`: Trading account name (for quick filtering)
- `instrument`: Trading instrument/symbol (for quick filtering)

**Constraints:**
- `execution_id` must be unique (prevents duplicate imports)
- `execution_id` cannot be NULL
- `csv_filename` cannot be NULL

**SQLAlchemy Model:**
```python
from datetime import datetime
from app.database import db

class ImportedExecution(db.Model):
    __tablename__ = 'imported_executions'

    id = db.Column(db.Integer, primary_key=True)
    execution_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
    csv_filename = db.Column(db.String(255), nullable=False, index=True)
    import_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    account = db.Column(db.String(50))
    instrument = db.Column(db.String(50))

    def __repr__(self):
        return f"<ImportedExecution {self.execution_id} from {self.csv_filename}>"
```

## Migrations

### Migration: Add imported_executions table

**Migration File:** `migrations/versions/xxx_add_imported_executions_table.py`

**Upgrade:**
```python
def upgrade():
    # Create imported_executions table
    op.create_table(
        'imported_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.String(length=255), nullable=False),
        sa.Column('csv_filename', sa.String(length=255), nullable=False),
        sa.Column('import_timestamp', sa.DateTime(), nullable=False),
        sa.Column('account', sa.String(length=50), nullable=True),
        sa.Column('instrument', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('execution_id')
    )

    # Create indexes
    op.create_index('idx_imported_executions_exec_id', 'imported_executions', ['execution_id'])
    op.create_index('idx_imported_executions_csv_file', 'imported_executions', ['csv_filename'])
    op.create_index('idx_imported_executions_timestamp', 'imported_executions', ['import_timestamp'])
```

**Downgrade:**
```python
def downgrade():
    # Drop indexes
    op.drop_index('idx_imported_executions_timestamp', table_name='imported_executions')
    op.drop_index('idx_imported_executions_csv_file', table_name='imported_executions')
    op.drop_index('idx_imported_executions_exec_id', table_name='imported_executions')

    # Drop table
    op.drop_table('imported_executions')
```

### Data Migration: Backfill existing trades

**Purpose:** Populate imported_executions table with execution IDs from existing trades to prevent re-import of historical data.

**Migration File:** `migrations/versions/xxx_backfill_imported_executions.py`

**Upgrade:**
```python
def upgrade():
    # Backfill imported_executions from existing trades
    connection = op.get_bind()

    # Get all existing trades with execution_id
    trades = connection.execute("""
        SELECT
            execution_id,
            account,
            instrument,
            entry_time as import_timestamp
        FROM trades
        WHERE execution_id IS NOT NULL
        ORDER BY entry_time ASC
    """).fetchall()

    # Insert into imported_executions (ignore duplicates)
    for trade in trades:
        try:
            connection.execute("""
                INSERT OR IGNORE INTO imported_executions
                (execution_id, csv_filename, import_timestamp, account, instrument)
                VALUES (?, 'BACKFILL', ?, ?, ?)
            """, (
                trade.execution_id,
                trade.import_timestamp,
                trade.account,
                trade.instrument
            ))
        except Exception as e:
            # Log error but continue with other trades
            print(f"Error backfilling execution {trade.execution_id}: {e}")

    print(f"Backfilled {len(trades)} execution IDs into imported_executions table")
```

**Downgrade:**
```python
def downgrade():
    # Remove backfilled records
    connection = op.get_bind()
    connection.execute("DELETE FROM imported_executions WHERE csv_filename = 'BACKFILL'")
```

### Notes

1. **Execution ID Format:** NinjaTrader execution IDs are typically alphanumeric strings (e.g., "abc123def456789"). Verify exact format from actual CSV files.

2. **Backfill Strategy:** The backfill migration uses 'BACKFILL' as csv_filename to distinguish historical records from newly imported ones.

3. **Index Performance:** The execution_id index ensures O(1) duplicate checking during import. Critical for real-time performance.

4. **Audit Trail:** The csv_filename field enables tracking which CSV file each execution came from, useful for debugging import issues.

5. **Cleanup Strategy:** Consider adding a cleanup job to archive/delete imported_executions records older than 1 year (future enhancement).
