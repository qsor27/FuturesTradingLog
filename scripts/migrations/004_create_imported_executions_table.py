"""
Database migration: Create imported_executions table for execution ID deduplication

This migration creates a table to track all imported execution IDs from CSV files
to prevent duplicate trades when re-importing CSV files.

Fields:
- execution_id: Unique execution ID from NinjaTrader (primary key)
- csv_filename: Original CSV file this execution was imported from
- import_timestamp: When this execution was first imported
- import_source: Source of import (e.g., 'CSV_IMPORT', 'BACKFILL', 'MANUAL')
"""
import sqlite3
from datetime import datetime


def upgrade(db_path: str) -> None:
    """
    Create imported_executions table with indexes.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create imported_executions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS imported_executions (
                execution_id TEXT PRIMARY KEY,
                csv_filename TEXT,
                import_timestamp TEXT NOT NULL,
                import_source TEXT DEFAULT 'CSV_IMPORT',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on csv_filename for audit queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_imported_executions_csv_filename
            ON imported_executions(csv_filename)
        """)

        # Create index on import_timestamp for temporal queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_imported_executions_import_timestamp
            ON imported_executions(import_timestamp)
        """)

        # Create index on import_source for filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_imported_executions_import_source
            ON imported_executions(import_source)
        """)

        conn.commit()
        print("Migration 004: Successfully created imported_executions table with indexes")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 004: Error during migration - {e}")
        raise

    finally:
        conn.close()


def downgrade(db_path: str) -> None:
    """
    Drop imported_executions table.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Drop indexes first
        cursor.execute("DROP INDEX IF EXISTS idx_imported_executions_csv_filename")
        cursor.execute("DROP INDEX IF EXISTS idx_imported_executions_import_timestamp")
        cursor.execute("DROP INDEX IF EXISTS idx_imported_executions_import_source")

        # Drop table
        cursor.execute("DROP TABLE IF EXISTS imported_executions")

        conn.commit()
        print("Migration 004: Successfully dropped imported_executions table and indexes")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 004: Error during downgrade - {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from config import config

    # Run migration
    print(f"Running migration 004 on database: {config.db_path}")
    upgrade(config.db_path)
    print("Migration 004 completed successfully")
