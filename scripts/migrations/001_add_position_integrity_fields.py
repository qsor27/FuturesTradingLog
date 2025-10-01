"""
Migration: Add integrity tracking fields to positions table

Adds last_validated_at, validation_status, and integrity_score fields to the positions table
to support position-execution integrity validation.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_config import get_logger

logger = get_logger(__name__)


class AddPositionIntegrityFieldsMigration:
    """Migration to add integrity tracking fields to positions table"""

    def __init__(self, db_path: str):
        """
        Initialize migration

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.migration_name = "001_add_position_integrity_fields"

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

                # Check if positions table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='positions'
                """)

                if not cursor.fetchone():
                    logger.error("Positions table does not exist")
                    return False

                # Check if fields already exist
                cursor.execute("PRAGMA table_info(positions)")
                columns = [col[1] for col in cursor.fetchall()]

                fields_to_add = []
                if 'last_validated_at' not in columns:
                    fields_to_add.append(('last_validated_at', 'TEXT'))
                if 'validation_status' not in columns:
                    fields_to_add.append(('validation_status', 'TEXT DEFAULT "not_validated"'))
                if 'integrity_score' not in columns:
                    fields_to_add.append(('integrity_score', 'REAL DEFAULT 0.0'))

                if not fields_to_add:
                    logger.info("All integrity fields already exist, skipping migration")
                    return True

                # Add new columns
                for field_name, field_type in fields_to_add:
                    logger.info(f"Adding column {field_name} to positions table")
                    cursor.execute(f"""
                        ALTER TABLE positions
                        ADD COLUMN {field_name} {field_type}
                    """)

                # Update existing positions to have default values
                logger.info("Updating existing positions with default integrity values")
                cursor.execute("""
                    UPDATE positions
                    SET validation_status = 'not_validated',
                        integrity_score = 0.0
                    WHERE validation_status IS NULL
                """)

                conn.commit()

                # Verify the changes
                cursor.execute("PRAGMA table_info(positions)")
                updated_columns = [col[1] for col in cursor.fetchall()]

                if all(field in updated_columns for field in ['last_validated_at', 'validation_status', 'integrity_score']):
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
                cursor.execute("PRAGMA table_info(positions)")
                columns = cursor.fetchall()

                # Filter out the integrity fields
                keep_columns = [
                    f"{col[1]} {col[2]}"
                    for col in columns
                    if col[1] not in ['last_validated_at', 'validation_status', 'integrity_score']
                ]

                if len(keep_columns) == len(columns):
                    logger.info("Integrity fields don't exist, nothing to rollback")
                    return True

                # Create temporary table without integrity fields
                logger.info("Creating temporary table without integrity fields")
                create_temp_sql = f"""
                    CREATE TABLE positions_temp (
                        {', '.join(keep_columns)}
                    )
                """
                cursor.execute(create_temp_sql)

                # Copy data to temporary table
                column_names = [col[1] for col in columns if col[1] not in ['last_validated_at', 'validation_status', 'integrity_score']]
                logger.info("Copying data to temporary table")
                cursor.execute(f"""
                    INSERT INTO positions_temp ({', '.join(column_names)})
                    SELECT {', '.join(column_names)} FROM positions
                """)

                # Drop old table
                logger.info("Dropping old positions table")
                cursor.execute("DROP TABLE positions")

                # Rename temporary table
                logger.info("Renaming temporary table to positions")
                cursor.execute("ALTER TABLE positions_temp RENAME TO positions")

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

    parser = argparse.ArgumentParser(description="Add position integrity fields migration")
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

    migration = AddPositionIntegrityFieldsMigration(args.db_path)

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