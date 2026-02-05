"""
Migration: Add trade validation fields to trades and positions tables

This migration adds fields to track trade validation feedback from NinjaTrader:
- trade_validation: Individual trade validation status (Valid/Invalid/NULL)
- validation_status: Aggregated position validation status (Valid/Invalid/Mixed/NULL)

Spec reference: lines 98-103
Task Group 1: Database Schema and Migration
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_config import get_logger

logger = get_logger(__name__)


class AddTradeValidationFieldsMigration:
    """Migration to add trade validation fields to trades and positions tables"""

    def __init__(self, db_path: str):
        """
        Initialize migration

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.migration_name = "004_add_trade_validation_fields"

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

                # Check if trades table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='trades'
                """)

                if not cursor.fetchone():
                    logger.error("trades table does not exist")
                    return False

                # Check if positions table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='positions'
                """)

                if not cursor.fetchone():
                    logger.error("positions table does not exist")
                    return False

                # Check which fields already exist in trades table
                cursor.execute("PRAGMA table_info(trades)")
                trades_columns = [col[1] for col in cursor.fetchall()]

                # Check which fields already exist in positions table
                cursor.execute("PRAGMA table_info(positions)")
                positions_columns = [col[1] for col in cursor.fetchall()]

                # Add trade_validation to trades table if not exists
                if 'trade_validation' not in trades_columns:
                    logger.info("Adding trade_validation column to trades table")
                    cursor.execute("""
                        ALTER TABLE trades
                        ADD COLUMN trade_validation TEXT
                        CHECK (trade_validation IS NULL OR trade_validation IN ('Valid', 'Invalid'))
                    """)
                else:
                    logger.info("trade_validation column already exists in trades table, skipping")

                # Add validation_status to positions table if not exists
                if 'validation_status' not in positions_columns:
                    logger.info("Adding validation_status column to positions table")
                    cursor.execute("""
                        ALTER TABLE positions
                        ADD COLUMN validation_status TEXT
                        CHECK (validation_status IS NULL OR validation_status IN ('Valid', 'Invalid', 'Mixed'))
                    """)
                else:
                    logger.info("validation_status column already exists in positions table, skipping")

                # Create index on positions.validation_status if not exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='idx_positions_validation_status'
                """)

                if not cursor.fetchone():
                    logger.info("Creating index on positions.validation_status")
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_positions_validation_status
                        ON positions(validation_status)
                    """)
                else:
                    logger.info("Index idx_positions_validation_status already exists, skipping")

                conn.commit()

                # Verify the changes
                cursor.execute("PRAGMA table_info(trades)")
                updated_trades_columns = [col[1] for col in cursor.fetchall()]

                cursor.execute("PRAGMA table_info(positions)")
                updated_positions_columns = [col[1] for col in cursor.fetchall()]

                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='idx_positions_validation_status'
                """)
                index_exists = cursor.fetchone() is not None

                if ('trade_validation' in updated_trades_columns and
                    'validation_status' in updated_positions_columns and
                    index_exists):
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

        Note: SQLite doesn't support DROP COLUMN directly, so we need to recreate the tables

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info(f"Rolling back migration: {self.migration_name}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Rollback trades table
                logger.info("Rolling back trades table")
                cursor.execute("PRAGMA table_info(trades)")
                trades_columns = cursor.fetchall()

                # Filter out trade_validation column
                keep_trades_columns = [
                    col[1] for col in trades_columns
                    if col[1] != 'trade_validation'
                ]

                if len(keep_trades_columns) < len(trades_columns):
                    # Create temporary table without trade_validation
                    logger.info("Creating temporary trades table without trade_validation")

                    # Get column definitions without trade_validation
                    column_defs = []
                    for col in trades_columns:
                        if col[1] == 'trade_validation':
                            continue
                        col_def = f"{col[1]} {col[2]}"
                        if col[3]:  # NOT NULL
                            col_def += " NOT NULL"
                        if col[4] is not None:  # DEFAULT value
                            col_def += f" DEFAULT {col[4]}"
                        if col[5]:  # PRIMARY KEY
                            col_def += " PRIMARY KEY"
                        column_defs.append(col_def)

                    create_temp_sql = f"""
                        CREATE TABLE trades_temp (
                            {', '.join(column_defs)}
                        )
                    """
                    cursor.execute(create_temp_sql)

                    # Copy data to temporary table
                    logger.info("Copying data to temporary trades table")
                    cursor.execute(f"""
                        INSERT INTO trades_temp ({', '.join(keep_trades_columns)})
                        SELECT {', '.join(keep_trades_columns)} FROM trades
                    """)

                    # Drop old table
                    logger.info("Dropping old trades table")
                    cursor.execute("DROP TABLE trades")

                    # Rename temporary table
                    logger.info("Renaming temporary table to trades")
                    cursor.execute("ALTER TABLE trades_temp RENAME TO trades")

                    # Recreate indexes on trades table (excluding validation_status related ones)
                    logger.info("Recreating indexes on trades table")
                    indexes = [
                        "CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_dollars_gain_loss ON trades(dollars_gain_loss)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_entry_execution_id ON trades(entry_execution_id, account)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_link_group_id ON trades(link_group_id)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_account_entry_time ON trades(account, entry_time)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_side_entry_time ON trades(side_of_market, entry_time)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_deleted ON trades(deleted)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_source_file ON trades(source_file)",
                        "CREATE INDEX IF NOT EXISTS idx_trades_import_batch_id ON trades(import_batch_id)",
                    ]
                    for index_sql in indexes:
                        try:
                            cursor.execute(index_sql)
                        except sqlite3.Error:
                            pass  # Index might not be applicable to this schema
                else:
                    logger.info("trade_validation column doesn't exist in trades table, nothing to rollback")

                # Rollback positions table
                logger.info("Rolling back positions table")
                cursor.execute("PRAGMA table_info(positions)")
                positions_columns = cursor.fetchall()

                # Filter out validation_status column
                keep_positions_columns = [
                    col[1] for col in positions_columns
                    if col[1] != 'validation_status'
                ]

                if len(keep_positions_columns) < len(positions_columns):
                    # Create temporary table without validation_status
                    logger.info("Creating temporary positions table without validation_status")

                    # Get column definitions without validation_status
                    column_defs = []
                    for col in positions_columns:
                        if col[1] == 'validation_status':
                            continue
                        col_def = f"{col[1]} {col[2]}"
                        if col[3]:  # NOT NULL
                            col_def += " NOT NULL"
                        if col[4] is not None:  # DEFAULT value
                            col_def += f" DEFAULT {col[4]}"
                        if col[5]:  # PRIMARY KEY
                            col_def += " PRIMARY KEY"
                        column_defs.append(col_def)

                    create_temp_sql = f"""
                        CREATE TABLE positions_temp (
                            {', '.join(column_defs)}
                        )
                    """
                    cursor.execute(create_temp_sql)

                    # Copy data to temporary table
                    logger.info("Copying data to temporary positions table")
                    cursor.execute(f"""
                        INSERT INTO positions_temp ({', '.join(keep_positions_columns)})
                        SELECT {', '.join(keep_positions_columns)} FROM positions
                    """)

                    # Drop old table
                    logger.info("Dropping old positions table")
                    cursor.execute("DROP TABLE positions")

                    # Rename temporary table
                    logger.info("Renaming temporary table to positions")
                    cursor.execute("ALTER TABLE positions_temp RENAME TO positions")

                    # Recreate indexes on positions table (excluding idx_positions_validation_status)
                    logger.info("Recreating indexes on positions table")
                    indexes = [
                        "CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time)",
                        "CREATE INDEX IF NOT EXISTS idx_positions_exit_time ON positions(exit_time)",
                        "CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account)",
                        "CREATE INDEX IF NOT EXISTS idx_positions_instrument ON positions(instrument)",
                        "CREATE INDEX IF NOT EXISTS idx_positions_account_instrument ON positions(account, instrument)",
                        "CREATE INDEX IF NOT EXISTS idx_positions_deleted ON positions(deleted)",
                    ]
                    for index_sql in indexes:
                        try:
                            cursor.execute(index_sql)
                        except sqlite3.Error:
                            pass  # Index might not be applicable to this schema
                else:
                    logger.info("validation_status column doesn't exist in positions table, nothing to rollback")

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

    parser = argparse.ArgumentParser(description="Add trade validation fields migration")
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

    migration = AddTradeValidationFieldsMigration(args.db_path)

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
