"""
Database Migration Script for Custom Fields

Executes SQL migration scripts to create custom fields tables and indexes.
Supports both forward migrations and rollbacks.
"""

import sqlite3
import sys
import os
from pathlib import Path
import argparse
from datetime import datetime
import logging

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config.config import AppConfig
except ImportError:
    # Fallback if config import fails
    class AppConfig:
        def __init__(self):
            self.db_dir = Path(__file__).parent.parent / 'data' / 'db'
            self.db_path = self.db_dir / 'futures_trades_clean.db'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """Get database connection with proper settings"""
    if db_path is None:
        config = AppConfig()
        db_path = str(config.db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def execute_migration(conn: sqlite3.Connection, migration_file: Path) -> bool:
    """Execute a SQL migration file"""
    try:
        logger.info(f"Executing migration: {migration_file.name}")

        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Execute the migration
        conn.executescript(migration_sql)
        conn.commit()

        logger.info(f"Migration completed successfully: {migration_file.name}")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration failed: {migration_file.name}")
        logger.error(f"Error: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        conn.rollback()
        return False


def verify_migration(conn: sqlite3.Connection) -> bool:
    """Verify that migration was successful"""
    try:
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('custom_fields', 'position_custom_field_values', 'custom_field_options')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['custom_fields', 'position_custom_field_values', 'custom_field_options']
        for table in expected_tables:
            if table not in tables:
                logger.error(f"Migration verification failed: table '{table}' does not exist")
                return False

        # Check if indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND (
                name LIKE 'idx_custom_fields%' OR
                name LIKE 'idx_position_custom_field%' OR
                name LIKE 'idx_custom_field_options%'
            )
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        if len(indexes) == 0:
            logger.warning("No custom field indexes found - migration may be incomplete")

        logger.info(f"Migration verified: {len(tables)} tables, {len(indexes)} indexes created")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration verification failed: {e}")
        return False


def run_migration(db_path: str = None, rollback: bool = False) -> bool:
    """Run migration or rollback"""
    migrations_dir = Path(__file__).parent / 'migrations'

    if rollback:
        migration_file = migrations_dir / '001_create_custom_fields_tables_rollback.sql'
        action = "rollback"
    else:
        migration_file = migrations_dir / '001_create_custom_fields_tables.sql'
        action = "migration"

    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    try:
        # Connect to database
        conn = get_db_connection(db_path)

        # Execute migration
        logger.info(f"Starting {action}...")
        success = execute_migration(conn, migration_file)

        if not success:
            logger.error(f"{action.capitalize()} failed")
            return False

        # Verify migration (only for forward migrations)
        if not rollback:
            if not verify_migration(conn):
                logger.error("Migration verification failed")
                return False

        logger.info(f"{action.capitalize()} completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during {action}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run database migrations for custom fields')
    parser.add_argument('--rollback', action='store_true', help='Run rollback instead of migration')
    parser.add_argument('--db-path', type=str, help='Path to database file (optional)')

    args = parser.parse_args()

    # Run migration
    success = run_migration(db_path=args.db_path, rollback=args.rollback)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()