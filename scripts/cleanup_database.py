"""
Database Cleanup Utility - Delete all positions and executions for clean re-import

This script provides a safe way to delete all trading data from the database
to enable clean re-import after fixing position building or P&L calculation bugs.

NO DATA REPAIR - Only deletion. Fix the code, delete the data, re-import fresh.
"""

import sqlite3
import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseCleanup:
    """Utility for safely deleting trading data from the database"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def get_record_counts(self) -> dict:
        """Get current record counts before deletion"""
        cursor = self.conn.cursor()

        counts = {}

        # Count positions
        cursor.execute("SELECT COUNT(*) as count FROM positions")
        counts['positions'] = cursor.fetchone()['count']

        # Count executions (position_executions mapping table)
        try:
            cursor.execute("SELECT COUNT(*) as count FROM position_executions")
            counts['position_executions'] = cursor.fetchone()['count']
        except sqlite3.OperationalError:
            counts['position_executions'] = 0

        # Count trades
        try:
            cursor.execute("SELECT COUNT(*) as count FROM trades")
            counts['trades'] = cursor.fetchone()['count']
        except sqlite3.OperationalError:
            counts['trades'] = 0

        return counts

    def delete_positions(self, confirm: bool = False) -> int:
        """Delete all positions and position_executions mappings"""
        if not confirm:
            raise ValueError("Confirmation required. Set confirm=True to proceed.")

        cursor = self.conn.cursor()

        # Get count before deletion
        count_before = self.get_record_counts()
        logger.info(f"Found {count_before['positions']} positions to delete")
        logger.info(f"Found {count_before['position_executions']} position-execution mappings to delete")

        # Delete position_executions first (foreign key constraint)
        cursor.execute("DELETE FROM position_executions")
        logger.info(f"Deleted {cursor.rowcount} position-execution mappings")

        # Delete positions
        cursor.execute("DELETE FROM positions")
        positions_deleted = cursor.rowcount
        logger.info(f"Deleted {positions_deleted} positions")

        # Reset auto-increment sequences
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='positions'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='position_executions'")
        logger.info("Reset auto-increment sequences")

        self.conn.commit()
        logger.info("✅ Position deletion committed successfully")

        return positions_deleted

    def delete_trades(self, confirm: bool = False) -> int:
        """Delete all trades/executions"""
        if not confirm:
            raise ValueError("Confirmation required. Set confirm=True to proceed.")

        cursor = self.conn.cursor()

        # Get count before deletion
        count_before = self.get_record_counts()
        logger.info(f"Found {count_before['trades']} trades to delete")

        # Delete trades
        cursor.execute("DELETE FROM trades")
        trades_deleted = cursor.rowcount
        logger.info(f"Deleted {trades_deleted} trades")

        # Reset auto-increment sequence
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='trades'")
        logger.info("Reset auto-increment sequences")

        self.conn.commit()
        logger.info("✅ Trade deletion committed successfully")

        return trades_deleted

    def delete_all(self, confirm: bool = False) -> dict:
        """Delete all trading data (positions and trades)"""
        if not confirm:
            raise ValueError("Confirmation required. Set confirm=True to proceed.")

        logger.info("🗑️  DELETING ALL TRADING DATA...")

        # Get counts before deletion
        counts_before = self.get_record_counts()
        logger.info(f"Database contains:")
        logger.info(f"  - {counts_before['positions']} positions")
        logger.info(f"  - {counts_before['position_executions']} position-execution mappings")
        logger.info(f"  - {counts_before['trades']} trades")

        # Delete in correct order (respecting foreign keys)
        positions_deleted = self.delete_positions(confirm=True)
        trades_deleted = self.delete_trades(confirm=True)

        # Run VACUUM to reclaim disk space
        logger.info("Running VACUUM to reclaim disk space...")
        self.conn.execute("VACUUM")
        logger.info("✅ VACUUM completed")

        result = {
            'positions_deleted': positions_deleted,
            'trades_deleted': trades_deleted,
            'timestamp': datetime.now().isoformat()
        }

        logger.info("✅ ALL TRADING DATA DELETED SUCCESSFULLY")
        return result

    def verify_empty(self) -> bool:
        """Verify that all trading data has been deleted"""
        counts = self.get_record_counts()

        if counts['positions'] == 0 and counts['trades'] == 0:
            logger.info("✅ Verification passed: Database is clean")
            return True
        else:
            logger.warning(f"⚠️ Verification failed: {counts['positions']} positions, {counts['trades']} trades remain")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Database Cleanup Utility - Delete all positions and executions for clean re-import',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete only positions (keeps trades)
  python scripts/cleanup_database.py --delete-positions --confirm

  # Delete only trades (keeps positions)
  python scripts/cleanup_database.py --delete-trades --confirm

  # Delete everything and reset
  python scripts/cleanup_database.py --delete-all --confirm

  # Show current counts without deleting
  python scripts/cleanup_database.py --show-counts

WARNING: This operation is IRREVERSIBLE. Make sure you have:
1. Fixed the bugs in the code
2. Backed up your database if needed
3. Are ready to re-import fresh CSV data
        """
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default='data/db/trading_log.db',
        help='Path to SQLite database file (default: data/db/trading_log.db)'
    )

    parser.add_argument(
        '--delete-positions',
        action='store_true',
        help='Delete all positions and position-execution mappings'
    )

    parser.add_argument(
        '--delete-trades',
        action='store_true',
        help='Delete all trades/executions'
    )

    parser.add_argument(
        '--delete-all',
        action='store_true',
        help='Delete ALL trading data (positions + trades)'
    )

    parser.add_argument(
        '--show-counts',
        action='store_true',
        help='Show current record counts without deleting'
    )

    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Required confirmation flag to actually perform deletion'
    )

    args = parser.parse_args()

    # Check if database exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"❌ Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"📁 Database: {db_path}")

    with DatabaseCleanup(str(db_path)) as cleanup:
        # Show counts if requested
        if args.show_counts:
            counts = cleanup.get_record_counts()
            logger.info("📊 Current database counts:")
            logger.info(f"  - Positions: {counts['positions']}")
            logger.info(f"  - Position-Execution mappings: {counts['position_executions']}")
            logger.info(f"  - Trades: {counts['trades']}")
            sys.exit(0)

        # Require at least one action
        if not (args.delete_positions or args.delete_trades or args.delete_all):
            logger.error("❌ No action specified. Use --delete-positions, --delete-trades, or --delete-all")
            parser.print_help()
            sys.exit(1)

        # Require confirmation
        if not args.confirm:
            logger.error("❌ --confirm flag required to perform deletion")
            logger.error("This ensures you understand the operation is IRREVERSIBLE")
            sys.exit(1)

        # Perform deletion
        try:
            if args.delete_all:
                result = cleanup.delete_all(confirm=True)
                logger.info(f"Deleted {result['positions_deleted']} positions")
                logger.info(f"Deleted {result['trades_deleted']} trades")
                cleanup.verify_empty()

            elif args.delete_positions:
                positions_deleted = cleanup.delete_positions(confirm=True)
                logger.info(f"Deleted {positions_deleted} positions")

            elif args.delete_trades:
                trades_deleted = cleanup.delete_trades(confirm=True)
                logger.info(f"Deleted {trades_deleted} trades")

            logger.info("✅ Cleanup completed successfully")
            logger.info("You can now re-import your CSV data with the fixed code")

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
