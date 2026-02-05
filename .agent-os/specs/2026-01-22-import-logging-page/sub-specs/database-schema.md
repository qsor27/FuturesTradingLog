# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2026-01-22-import-logging-page/spec.md

## New Tables

### import_execution_logs

Stores metadata for each import execution with summary statistics.

```sql
CREATE TABLE IF NOT EXISTS import_execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('success', 'partial', 'failed')),
    total_rows INTEGER NOT NULL DEFAULT 0,
    success_rows INTEGER NOT NULL DEFAULT 0,
    failed_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    processing_time_ms INTEGER,
    affected_accounts TEXT, -- JSON array of account names
    error_summary TEXT, -- High-level error description
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX IF NOT EXISTS idx_import_execution_logs_batch_id
    ON import_execution_logs(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_import_execution_logs_status
    ON import_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_import_execution_logs_import_time
    ON import_execution_logs(import_time DESC);
CREATE INDEX IF NOT EXISTS idx_import_execution_logs_file_name
    ON import_execution_logs(file_name);
```

**Rationale:**
- Provides fast summary view for import logs page
- import_batch_id links to existing import_history table and trades.import_batch_id
- Status enum enforces data integrity
- JSON storage for accounts_affected allows flexible querying
- Descending time index optimizes "most recent first" queries

### import_execution_row_logs

Stores detailed row-by-row processing results for debugging and troubleshooting.

```sql
CREATE TABLE IF NOT EXISTS import_execution_row_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'failed', 'skipped')),
    error_message TEXT,
    error_category TEXT CHECK(error_category IN ('validation_error', 'parsing_error', 'duplicate_error', 'database_error', 'business_logic_error', NULL)),
    raw_row_data TEXT, -- JSON representation of CSV row
    validation_errors TEXT, -- JSON array of validation error objects
    created_trade_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_batch_id) REFERENCES import_execution_logs(import_batch_id) ON DELETE CASCADE,
    FOREIGN KEY (created_trade_id) REFERENCES trades(id) ON DELETE SET NULL
);
```

**Indexes:**
```sql
CREATE INDEX IF NOT EXISTS idx_import_row_logs_batch_id
    ON import_execution_row_logs(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_import_row_logs_status
    ON import_execution_row_logs(status);
CREATE INDEX IF NOT EXISTS idx_import_row_logs_trade_id
    ON import_execution_row_logs(created_trade_id);
```

**Rationale:**
- Detailed row-level logging for debugging import issues
- Foreign key to import_execution_logs enables cascade delete for cleanup
- Foreign key to trades enables tracing which row created which trade
- JSON storage for raw_row_data and validation_errors preserves full context
- Error category classification enables filtering by error type
- Batch ID index critical for "expand details" query performance

## Modified Tables

### trades (existing table - new column)

Add column to enable linking trades back to row-level logs:

```sql
ALTER TABLE trades ADD COLUMN import_row_log_id INTEGER REFERENCES import_execution_row_logs(id) ON DELETE SET NULL;
```

**Index:**
```sql
CREATE INDEX IF NOT EXISTS idx_trades_import_row_log_id ON trades(import_row_log_id);
```

**Rationale:**
- Enables bidirectional linking: row log → trade and trade → row log
- SET NULL on delete preserves trade data even if logs are archived/deleted
- Optional column (can be NULL for existing trades)

## Migration Strategy

### Migration 1: Create import_execution_logs table

```python
def upgrade_import_execution_logs(cursor):
    """Create import_execution_logs table"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL CHECK(status IN ('success', 'partial', 'failed')),
            total_rows INTEGER NOT NULL DEFAULT 0,
            success_rows INTEGER NOT NULL DEFAULT 0,
            failed_rows INTEGER NOT NULL DEFAULT 0,
            skipped_rows INTEGER NOT NULL DEFAULT 0,
            processing_time_ms INTEGER,
            affected_accounts TEXT,
            error_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_execution_logs_batch_id ON import_execution_logs(import_batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_execution_logs_status ON import_execution_logs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_execution_logs_import_time ON import_execution_logs(import_time DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_execution_logs_file_name ON import_execution_logs(file_name)")
```

### Migration 2: Create import_execution_row_logs table

```python
def upgrade_import_execution_row_logs(cursor):
    """Create import_execution_row_logs table"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_execution_row_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('success', 'failed', 'skipped')),
            error_message TEXT,
            error_category TEXT CHECK(error_category IN ('validation_error', 'parsing_error', 'duplicate_error', 'database_error', 'business_logic_error', NULL)),
            raw_row_data TEXT,
            validation_errors TEXT,
            created_trade_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (import_batch_id) REFERENCES import_execution_logs(import_batch_id) ON DELETE CASCADE,
            FOREIGN KEY (created_trade_id) REFERENCES trades(id) ON DELETE SET NULL
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_row_logs_batch_id ON import_execution_row_logs(import_batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_row_logs_status ON import_execution_row_logs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_row_logs_trade_id ON import_execution_row_logs(created_trade_id)")
```

### Migration 3: Add import_row_log_id to trades table

```python
def upgrade_trades_import_row_log_id(cursor):
    """Add import_row_log_id column to trades table"""
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN import_row_log_id INTEGER REFERENCES import_execution_row_logs(id) ON DELETE SET NULL")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_import_row_log_id ON trades(import_row_log_id)")
    except Exception as e:
        # Column may already exist
        if "duplicate column name" not in str(e).lower():
            raise
```

## Data Integrity Constraints

1. **Cascade Delete**: When import_execution_logs entry is deleted, all associated row logs are deleted automatically
2. **SET NULL**: When trade or row log is deleted, the reference is set to NULL rather than preventing deletion
3. **Status Validation**: CHECK constraints ensure only valid status values are stored
4. **Unique Batch ID**: Prevents duplicate import execution log entries
5. **Foreign Key Enforcement**: Enable foreign key constraints in SQLite connection

## Performance Considerations

- **Batch Inserts**: Use executemany() for row logs to minimize transaction overhead
- **Lazy Loading**: Query row logs only when detail expansion is triggered, not on list view
- **Index Coverage**: All common query patterns covered by indexes (batch_id, status, time)
- **Log Archival**: Consider moving row logs older than 90 days to archive table to maintain performance
- **Vacuum After Cleanup**: Run VACUUM periodically when old logs are deleted to reclaim space
