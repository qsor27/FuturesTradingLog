"""
Database migration: Backfill imported_executions table with existing trades

This migration populates the imported_executions table with execution IDs
from all existing trades in the database to prevent re-importing them.
"""
import sqlite3
from datetime import datetime


def upgrade(db_path: str) -> None:
    """
    Backfill imported_executions table with existing trade execution IDs.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all trades with valid execution IDs
        cursor.execute("""
            SELECT DISTINCT entry_execution_id, instrument, entry_time
            FROM trades
            WHERE entry_execution_id IS NOT NULL
              AND entry_execution_id != ''
            ORDER BY entry_time ASC
        """)

        trades_to_backfill = cursor.fetchall()
        print(f"Migration 005: Found {len(trades_to_backfill)} trades to backfill")

        # Backfill each execution ID
        backfilled_count = 0
        skipped_count = 0

        for execution_id, instrument, entry_time in trades_to_backfill:
            # Check if already exists (in case migration is re-run)
            cursor.execute("""
                SELECT COUNT(*) FROM imported_executions
                WHERE execution_id = ?
            """, (execution_id,))

            if cursor.fetchone()[0] > 0:
                skipped_count += 1
                continue

            # Insert into imported_executions with BACKFILL source
            cursor.execute("""
                INSERT INTO imported_executions (
                    execution_id,
                    csv_filename,
                    import_timestamp,
                    import_source
                )
                VALUES (?, ?, ?, ?)
            """, (
                execution_id,
                None,  # No CSV filename for backfilled records
                entry_time,  # Use trade entry time as import timestamp
                'BACKFILL'
            ))
            backfilled_count += 1

        conn.commit()
        print(f"Migration 005: Successfully backfilled {backfilled_count} execution IDs")
        if skipped_count > 0:
            print(f"Migration 005: Skipped {skipped_count} execution IDs (already exist)")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 005: Error during migration - {e}")
        raise

    finally:
        conn.close()


def downgrade(db_path: str) -> None:
    """
    Remove backfilled records from imported_executions table.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Delete all backfilled records
        cursor.execute("""
            DELETE FROM imported_executions
            WHERE import_source = 'BACKFILL'
        """)

        deleted_count = cursor.rowcount
        conn.commit()
        print(f"Migration 005: Successfully removed {deleted_count} backfilled execution IDs")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 005: Error during downgrade - {e}")
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
    print(f"Running migration 005 on database: {config.db_path}")
    upgrade(config.db_path)
    print("Migration 005 completed successfully")
