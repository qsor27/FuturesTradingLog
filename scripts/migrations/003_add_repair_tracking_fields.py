"""
Database migration: Add repair tracking fields to integrity_issues table

This migration adds fields to track automatic repair attempts:
- repair_attempted: Whether repair was attempted
- repair_method: Method used for repair
- repair_successful: Whether repair succeeded
- repair_timestamp: When repair was attempted
- repair_details: JSON details about repair
"""
import sqlite3
from datetime import datetime


def upgrade(db_path: str) -> None:
    """
    Add repair tracking fields to integrity_issues table.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add repair_attempted column (default False)
        cursor.execute("""
            ALTER TABLE integrity_issues
            ADD COLUMN repair_attempted INTEGER DEFAULT 0
        """)

        # Add repair_method column (nullable text)
        cursor.execute("""
            ALTER TABLE integrity_issues
            ADD COLUMN repair_method TEXT
        """)

        # Add repair_successful column (nullable integer - 0/1/NULL)
        cursor.execute("""
            ALTER TABLE integrity_issues
            ADD COLUMN repair_successful INTEGER
        """)

        # Add repair_timestamp column (nullable text)
        cursor.execute("""
            ALTER TABLE integrity_issues
            ADD COLUMN repair_timestamp TEXT
        """)

        # Add repair_details column (nullable text for JSON)
        cursor.execute("""
            ALTER TABLE integrity_issues
            ADD COLUMN repair_details TEXT
        """)

        conn.commit()
        print(f"Migration 003: Successfully added repair tracking fields to integrity_issues table")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 003: Error during migration - {e}")
        raise

    finally:
        conn.close()


def downgrade(db_path: str) -> None:
    """
    Remove repair tracking fields from integrity_issues table.

    Note: SQLite doesn't support DROP COLUMN directly, so we need to:
    1. Create a new table without the repair columns
    2. Copy data from old table
    3. Drop old table
    4. Rename new table

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create new table without repair fields
        cursor.execute("""
            CREATE TABLE integrity_issues_backup (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                validation_id INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                resolution_status TEXT DEFAULT 'open',
                position_id INTEGER,
                execution_id INTEGER,
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                resolution_method TEXT,
                resolution_details TEXT,
                metadata TEXT,
                FOREIGN KEY (validation_id) REFERENCES validation_results(validation_id)
            )
        """)

        # Copy data from old table (excluding repair fields)
        cursor.execute("""
            INSERT INTO integrity_issues_backup (
                issue_id, validation_id, issue_type, severity, description,
                resolution_status, position_id, execution_id, detected_at,
                resolved_at, resolution_method, resolution_details, metadata
            )
            SELECT
                issue_id, validation_id, issue_type, severity, description,
                resolution_status, position_id, execution_id, detected_at,
                resolved_at, resolution_method, resolution_details, metadata
            FROM integrity_issues
        """)

        # Drop old table
        cursor.execute("DROP TABLE integrity_issues")

        # Rename new table
        cursor.execute("ALTER TABLE integrity_issues_backup RENAME TO integrity_issues")

        conn.commit()
        print(f"Migration 003: Successfully removed repair tracking fields from integrity_issues table")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration 003: Error during downgrade - {e}")
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
    print(f"Running migration 003 on database: {config.db_path}")
    upgrade(config.db_path)
    print("Migration 003 completed successfully")