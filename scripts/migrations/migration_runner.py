"""
Migration Runner

Automatically discovers and runs database migrations in order.
Tracks which migrations have been applied using a migrations table.
"""
import sqlite3
import sys
import importlib.util
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_config import get_logger

logger = get_logger(__name__)


class MigrationRunner:
    """Discovers and runs database migrations"""

    def __init__(self, db_path: str):
        """
        Initialize migration runner

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent

    def _ensure_migrations_table(self, cursor: sqlite3.Cursor):
        """Create migrations tracking table if it doesn't exist"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied'
            )
        """)

    def _get_applied_migrations(self, cursor: sqlite3.Cursor) -> set:
        """Get list of already applied migrations"""
        cursor.execute("SELECT migration_name FROM schema_migrations WHERE status = 'applied'")
        return {row[0] for row in cursor.fetchall()}

    def _discover_migrations(self) -> List[Tuple[str, Path]]:
        """
        Discover all migration files in the migrations directory

        Returns:
            List of (migration_name, file_path) tuples sorted by name
        """
        migrations = []
        for file_path in self.migrations_dir.glob('*.py'):
            # Skip __init__.py and migration_runner.py
            if file_path.name in ['__init__.py', 'migration_runner.py']:
                continue

            # Migration name is filename without .py extension
            migration_name = file_path.stem
            migrations.append((migration_name, file_path))

        # Sort by migration number (e.g., 001_, 002_, etc.)
        migrations.sort(key=lambda x: x[0])
        return migrations

    def _load_migration_class(self, file_path: Path) -> object:
        """
        Dynamically load migration class from file

        Args:
            file_path: Path to migration file

        Returns:
            Migration class (not instance)
        """
        spec = importlib.util.spec_from_file_location("migration_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the migration class (should be the one ending with 'Migration')
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.endswith('Migration') and attr_name != 'Migration':
                return attr

        raise ValueError(f"No migration class found in {file_path}")

    def _record_migration(self, cursor: sqlite3.Cursor, migration_name: str, status: str = 'applied'):
        """Record that a migration has been applied"""
        cursor.execute("""
            INSERT OR REPLACE INTO schema_migrations (migration_name, applied_at, status)
            VALUES (?, ?, ?)
        """, (migration_name, datetime.now().isoformat(), status))

    def run_pending_migrations(self) -> Tuple[int, int]:
        """
        Run all pending migrations

        Returns:
            Tuple of (successful_count, failed_count)
        """
        logger.info("Starting migration runner")
        successful = 0
        failed = 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Ensure migrations tracking table exists
                self._ensure_migrations_table(cursor)
                conn.commit()

                # Get applied migrations
                applied = self._get_applied_migrations(cursor)
                logger.info(f"Already applied migrations: {applied}")

                # Discover available migrations
                all_migrations = self._discover_migrations()
                logger.info(f"Discovered {len(all_migrations)} migration files")

                # Filter to only pending migrations
                pending = [(name, path) for name, path in all_migrations if name not in applied]

                if not pending:
                    logger.info("No pending migrations to run")
                    return (0, 0)

                logger.info(f"Found {len(pending)} pending migrations to run")

                # Run each pending migration
                for migration_name, file_path in pending:
                    logger.info(f"Running migration: {migration_name}")
                    print(f"[MIGRATION] Applying {migration_name}...")

                    try:
                        # Load migration class
                        MigrationClass = self._load_migration_class(file_path)

                        # Create instance and run
                        migration = MigrationClass(self.db_path)
                        success = migration.up()

                        if success:
                            # Record as applied
                            self._record_migration(cursor, migration_name, 'applied')
                            conn.commit()
                            successful += 1
                            logger.info(f"✓ Migration {migration_name} applied successfully")
                            print(f"[OK] Migration {migration_name} applied successfully")
                        else:
                            failed += 1
                            logger.error(f"✗ Migration {migration_name} failed")
                            print(f"[FAIL] Migration {migration_name} failed")
                            # Don't stop on failure, continue with other migrations

                    except Exception as e:
                        failed += 1
                        logger.error(f"Error running migration {migration_name}: {e}", exc_info=True)
                        print(f"[ERROR] Migration {migration_name} failed: {e}")
                        # Continue with other migrations

                logger.info(f"Migration run complete: {successful} successful, {failed} failed")
                return (successful, failed)

        except Exception as e:
            logger.error(f"Fatal error in migration runner: {e}", exc_info=True)
            return (successful, failed)

    def get_migration_status(self) -> dict:
        """
        Get status of all migrations

        Returns:
            Dict with migration status information
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Ensure migrations table exists
                self._ensure_migrations_table(cursor)

                # Get applied migrations
                applied = self._get_applied_migrations(cursor)

                # Get all migrations
                all_migrations = self._discover_migrations()

                return {
                    'total': len(all_migrations),
                    'applied': len(applied),
                    'pending': len(all_migrations) - len(applied),
                    'applied_migrations': sorted(applied),
                    'pending_migrations': sorted([name for name, _ in all_migrations if name not in applied])
                }

        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {
                'error': str(e)
            }


def main():
    """Run pending migrations from command line"""
    import argparse

    parser = argparse.ArgumentParser(description="Database migration runner")
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/db/trading_log.db',
        help='Path to the SQLite database'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show migration status without running'
    )

    args = parser.parse_args()

    runner = MigrationRunner(args.db_path)

    if args.status:
        status = runner.get_migration_status()
        if 'error' in status:
            print(f"[ERROR] {status['error']}")
            sys.exit(1)

        print(f"\nMigration Status:")
        print(f"  Total migrations: {status['total']}")
        print(f"  Applied: {status['applied']}")
        print(f"  Pending: {status['pending']}")

        if status['applied_migrations']:
            print(f"\n  Applied migrations:")
            for name in status['applied_migrations']:
                print(f"    [x] {name}")

        if status['pending_migrations']:
            print(f"\n  Pending migrations:")
            for name in status['pending_migrations']:
                print(f"    [ ] {name}")

        sys.exit(0)

    # Run migrations
    successful, failed = runner.run_pending_migrations()

    if failed > 0:
        print(f"\n[WARNING] {failed} migration(s) failed, {successful} succeeded")
        sys.exit(1)
    elif successful > 0:
        print(f"\n[OK] All {successful} migration(s) applied successfully")
        sys.exit(0)
    else:
        print("\n[OK] No migrations needed")
        sys.exit(0)


if __name__ == '__main__':
    main()
