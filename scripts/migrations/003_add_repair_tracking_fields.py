"""
Migration: Add repair tracking fields to integrity_issues table

This migration adds fields to track automatic repair attempts:
- repair_attempted: Whether repair was attempted
- repair_method: Method used for repair
- repair_successful: Whether repair succeeded
- repair_timestamp: When repair was attempted
- repair_details: JSON details about repair
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_config import get_logger

logger = get_logger(__name__)


class AddRepairTrackingFieldsMigration:
    """Migration to add repair tracking fields to integrity_issues table"""

    def __init__(self, db_path: str):
        """
        Initialize migration

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.migration_name = "003_add_repair_tracking_fields"

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

                # Check if integrity_issues table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='integrity_issues'
                """)

                if not cursor.fetchone():
                    logger.error("integrity_issues table does not exist")
                    return False

                # Check which fields already exist
                cursor.execute("PRAGMA table_info(integrity_issues)")
                columns = [col[1] for col in cursor.fetchall()]

                fields_to_add = []
                if 'repair_attempted' not in columns:
                    fields_to_add.append(('repair_attempted', 'INTEGER DEFAULT 0'))
                if 'repair_method' not in columns:
                    fields_to_add.append(('repair_method', 'TEXT'))
                if 'repair_successful' not in columns:
                    fields_to_add.append(('repair_successful', 'INTEGER'))
                if 'repair_timestamp' not in columns:
                    fields_to_add.append(('repair_timestamp', 'TEXT'))
                if 'repair_details' not in columns:
                    fields_to_add.append(('repair_details', 'TEXT'))

                if not fields_to_add:
                    logger.info("All repair tracking fields already exist, skipping migration")
                    return True

                # Add new columns
                for field_name, field_type in fields_to_add:
                    logger.info(f"Adding column {field_name} to integrity_issues table")
                    cursor.execute(f"""
                        ALTER TABLE integrity_issues
                        ADD COLUMN {field_name} {field_type}
                    """)

                conn.commit()

                # Verify the changes
                cursor.execute("PRAGMA table_info(integrity_issues)")
                updated_columns = [col[1] for col in cursor.fetchall()]

                required_fields = ['repair_attempted', 'repair_method', 'repair_successful',
                                 'repair_timestamp', 'repair_details']
                if all(field in updated_columns for field in required_fields):
                    logger.info(f"Migration {self.migration_name} completed successfully")
                    return True
                else:
                    logger.error(f"Migration {self.migration_name} failed - fields not added")
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

        Note: SQLite doesn't support DROP COLUMN directly, so we need to recreate the table

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info(f"Rolling back migration: {self.migration_name}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get current table schema
                cursor.execute("PRAGMA table_info(integrity_issues)")
                columns = cursor.fetchall()

                # Filter out the repair tracking fields
                keep_columns = [
                    f"{col[1]} {col[2]}"
                    for col in columns
                    if col[1] not in ['repair_attempted', 'repair_method', 'repair_successful',
                                    'repair_timestamp', 'repair_details']
                ]

                if len(keep_columns) == len(columns):
                    logger.info("Repair tracking fields don't exist, nothing to rollback")
                    return True

                # Create temporary table without repair fields
                logger.info("Creating temporary table without repair tracking fields")
                create_temp_sql = f"""
                    CREATE TABLE integrity_issues_temp (
                        {', '.join(keep_columns)}
                    )
                """
                cursor.execute(create_temp_sql)

                # Copy data to temporary table
                column_names = [col[1] for col in columns
                              if col[1] not in ['repair_attempted', 'repair_method',
                                              'repair_successful', 'repair_timestamp', 'repair_details']]
                logger.info("Copying data to temporary table")
                cursor.execute(f"""
                    INSERT INTO integrity_issues_temp ({', '.join(column_names)})
                    SELECT {', '.join(column_names)} FROM integrity_issues
                """)

                # Drop old table
                logger.info("Dropping old integrity_issues table")
                cursor.execute("DROP TABLE integrity_issues")

                # Rename temporary table
                logger.info("Renaming temporary table to integrity_issues")
                cursor.execute("ALTER TABLE integrity_issues_temp RENAME TO integrity_issues")

                conn.commit()

                logger.info(f"Migration {self.migration_name} rolled back successfully")
                return True

        except sqlite3.Error as e:
            logger.error(f"Database error during rollback: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during rollback: {e}")
            return False


def main():
    """Run the migration"""
    import argparse

    parser = argparse.ArgumentParser(description="Add repair tracking fields migration")
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

    migration = AddRepairTrackingFieldsMigration(args.db_path)

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