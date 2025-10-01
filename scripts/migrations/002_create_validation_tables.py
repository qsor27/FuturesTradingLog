"""
Migration: Create validation_results and integrity_issues tables

Creates the tables needed to store validation results and integrity issues
for position-execution validation tracking.
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_config import get_logger

logger = get_logger(__name__)


class CreateValidationTablesMigration:
    """Migration to create validation_results and integrity_issues tables"""

    def __init__(self, db_path: str):
        """
        Initialize migration

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.migration_name = "002_create_validation_tables"

    def up(self) -> bool:
        """
        Apply the migration

        Returns:
            True if migration successful, False otherwise
        """
        logger.info(f"Applying migration: {self.migration_name}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create validation_results table
                logger.info("Creating validation_results table")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS validation_results (
                        validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        position_id INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        issue_count INTEGER DEFAULT 0,
                        validation_type TEXT DEFAULT 'full',
                        details TEXT,
                        completed_at TEXT,
                        error_message TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
                    )
                """)

                # Create indexes for validation_results
                logger.info("Creating indexes for validation_results")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_validation_results_position_id
                    ON validation_results(position_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_validation_results_status
                    ON validation_results(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_validation_results_timestamp
                    ON validation_results(timestamp DESC)
                """)

                # Create integrity_issues table
                logger.info("Creating integrity_issues table")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS integrity_issues (
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
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (validation_id) REFERENCES validation_results(validation_id) ON DELETE CASCADE,
                        FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
                    )
                """)

                # Create indexes for integrity_issues
                logger.info("Creating indexes for integrity_issues")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_validation_id
                    ON integrity_issues(validation_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_position_id
                    ON integrity_issues(position_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_issue_type
                    ON integrity_issues(issue_type)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_severity
                    ON integrity_issues(severity)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_resolution_status
                    ON integrity_issues(resolution_status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_integrity_issues_detected_at
                    ON integrity_issues(detected_at DESC)
                """)

                conn.commit()

                # Verify the tables were created
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN ('validation_results', 'integrity_issues')
                """)
                tables = [row[0] for row in cursor.fetchall()]

                if 'validation_results' in tables and 'integrity_issues' in tables:
                    logger.info(f"Migration {self.migration_name} completed successfully")
                    return True
                else:
                    logger.error(f"Migration {self.migration_name} failed - tables not created")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Database error during migration: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            return False

    def down(self) -> bool:
        """
        Rollback the migration

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info(f"Rolling back migration: {self.migration_name}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Drop integrity_issues table first (has foreign key to validation_results)
                logger.info("Dropping integrity_issues table")
                cursor.execute("DROP TABLE IF EXISTS integrity_issues")

                # Drop validation_results table
                logger.info("Dropping validation_results table")
                cursor.execute("DROP TABLE IF EXISTS validation_results")

                conn.commit()

                # Verify the tables were dropped
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN ('validation_results', 'integrity_issues')
                """)
                tables = [row[0] for row in cursor.fetchall()]

                if len(tables) == 0:
                    logger.info(f"Migration {self.migration_name} rolled back successfully")
                    return True
                else:
                    logger.error(f"Migration {self.migration_name} rollback failed - tables still exist")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Database error during rollback: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during rollback: {e}")
            return False


def main():
    """Run the migration"""
    import argparse

    parser = argparse.ArgumentParser(description="Create validation tables migration")
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/db/trading_log.db',
        help='Path to the SQLite database'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback the migration'
    )

    args = parser.parse_args()

    migration = CreateValidationTablesMigration(args.db_path)

    if args.rollback:
        success = migration.down()
        action = "rolled back"
    else:
        success = migration.up()
        action = "applied"

    if success:
        print(f"[OK] Migration {action} successfully")
        sys.exit(0)
    else:
        print(f"[FAIL] Migration {action} failed")
        sys.exit(1)


if __name__ == '__main__':
    main()