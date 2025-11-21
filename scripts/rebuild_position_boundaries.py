"""
Position Boundary Detection Fix - Database Rebuild Script

This script rebuilds positions that were incorrectly combined due to the position
boundary detection bug. It clears affected positions and rebuilds them using the
fixed position building logic.

Bug Fixed: Multiple separate trading sequences were being combined into single positions
when quantity returned to zero between sequences.

Usage:
    python scripts/rebuild_position_boundaries.py [--dry-run] [--account ACCOUNT] [--instrument INSTRUMENT]

Options:
    --dry-run              Preview changes without modifying database
    --account ACCOUNT      Only rebuild positions for specific account
    --instrument INSTRUMENT Only rebuild positions for specific instrument
    --date DATE            Only rebuild positions from specific date (YYYY-MM-DD)
    --all                  Rebuild ALL positions (default: only suspicious ones)
"""

import sys
import os
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
from utils.logging_config import get_logger

logger = get_logger(__name__)


def find_suspicious_positions(conn, account: str = None, instrument: str = None, date: str = None):
    """
    Find positions that are likely affected by the boundary detection bug.

    Suspicious indicators:
    - Very high execution count (> 15 executions)
    - Very high quantity (> 20 contracts for futures)
    """
    cursor = conn.cursor()
    query = """
        SELECT id, instrument, account, total_quantity, execution_count,
               entry_time, exit_time, max_quantity
        FROM positions
        WHERE 1=1
    """
    params = []

    # Add filters
    if account:
        query += " AND account = ?"
        params.append(account)

    if instrument:
        query += " AND instrument LIKE ?"
        params.append(f"%{instrument}%")

    if date:
        query += " AND DATE(entry_time) = ?"
        params.append(date)

    # Find suspicious positions (high execution count or very high quantity)
    query += """
        AND (execution_count > 15 OR max_quantity > 20)
        ORDER BY account, instrument, entry_time
    """

    cursor.execute(query, params)
    positions = cursor.fetchall()

    logger.info(f"Found {len(positions)} suspicious positions")
    return positions


def get_all_positions(conn, account: str = None, instrument: str = None, date: str = None):
    """Get all positions matching filters."""
    cursor = conn.cursor()
    query = """
        SELECT id, instrument, account, total_quantity, execution_count,
               entry_time, exit_time, max_quantity
        FROM positions
        WHERE 1=1
    """
    params = []

    if account:
        query += " AND account = ?"
        params.append(account)

    if instrument:
        query += " AND instrument LIKE ?"
        params.append(f"%{instrument}%")

    if date:
        query += " AND DATE(entry_time) = ?"
        params.append(date)

    query += " ORDER BY account, instrument, entry_time"

    cursor.execute(query, params)
    positions = cursor.fetchall()

    logger.info(f"Found {len(positions)} total positions")
    return positions


def delete_positions(conn, position_ids: list, dry_run: bool = False):
    """Delete positions and their trade mappings."""
    if not position_ids:
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would delete {len(position_ids)} positions")
        return

    cursor = conn.cursor()

    # Delete position_executions mappings
    placeholders = ','.join('?' * len(position_ids))
    cursor.execute(f"""
        DELETE FROM position_executions
        WHERE position_id IN ({placeholders})
    """, position_ids)

    # Delete positions
    cursor.execute(f"""
        DELETE FROM positions
        WHERE id IN ({placeholders})
    """, position_ids)

    logger.info(f"Deleted {len(position_ids)} positions and their mappings")


def rebuild_positions_for_account_instrument(position_service, account: str, instrument: str, dry_run: bool = False):
    """Rebuild positions for specific account/instrument combination."""
    logger.info(f"Rebuilding positions for {account}/{instrument}")

    # Get all trades for this account/instrument
    position_service.cursor.execute("""
        SELECT * FROM trades
        WHERE account = ? AND instrument = ?
        AND deleted = 0
        ORDER BY entry_time
    """, (account, instrument))

    trades = []
    for row in position_service.cursor.fetchall():
        # Convert to dict
        trade = dict(zip([d[0] for d in position_service.cursor.description], row))
        trades.append(trade)

    if not trades:
        logger.warning(f"No trades found for {account}/{instrument}")
        return 0

    logger.info(f"Found {len(trades)} trades for {account}/{instrument}")

    # Rebuild positions using the fixed position service
    if dry_run:
        logger.info(f"[DRY RUN] Would rebuild positions from {len(trades)} trades")
        # Run the position building logic to see what would be created
        result = position_service._process_trades_for_instrument(trades, account, instrument)
        return result.get('positions_created', 0)
    else:
        result = position_service._process_trades_for_instrument(trades, account, instrument)
        positions_created = result.get('positions_created', 0)
        logger.info(f"Created {positions_created} new positions for {account}/{instrument}")
        return positions_created


def rebuild(db_path: str, account: str = None, instrument: str = None, date: str = None, rebuild_all: bool = False, dry_run: bool = False):
    """
    Main rebuild process.

    Steps:
    1. Find affected positions
    2. Group by account/instrument
    3. Delete old positions
    4. Rebuild with fixed logic
    5. Report results
    """
    header = "=" * 80
    title = "Position Boundary Detection Fix - Rebuild Script"
    print(header)
    print(title)
    print(header)
    logger.info(header)
    logger.info(title)
    logger.info(header)

    if dry_run:
        print("DRY RUN MODE - No changes will be made to database")
        logger.info("DRY RUN MODE - No changes will be made to database")

    filter_msg = f"Filters: account={account}, instrument={instrument}, date={date}, rebuild_all={rebuild_all}"
    print(filter_msg)
    logger.info(filter_msg)

    # Use EnhancedPositionServiceV2 as context manager
    with EnhancedPositionServiceV2(db_path) as position_service:
        # Find positions to rebuild
        if rebuild_all:
            positions = get_all_positions(position_service.conn, account, instrument, date)
        else:
            positions = find_suspicious_positions(position_service.conn, account, instrument, date)

        if not positions:
            msg = "No positions found to rebuild"
            print(msg)
            logger.info(msg)
            return {
                'positions_deleted': 0,
                'positions_created': 0,
                'accounts_affected': set(),
                'instruments_affected': set()
            }

        # Group positions by account/instrument
        account_instrument_groups = {}
        position_ids_to_delete = []

        print(f"\nFound {len(positions)} positions to rebuild:")
        for pos in positions:
            pos_id, instr, acct, qty, exec_count, entry_time, exit_time, max_qty = pos
            key = (acct, instr)

            if key not in account_instrument_groups:
                account_instrument_groups[key] = []

            account_instrument_groups[key].append(pos_id)
            position_ids_to_delete.append(pos_id)

            pos_info = f"  - Position {pos_id}: {acct}/{instr}, qty={qty}, max_qty={max_qty}, executions={exec_count}"
            print(pos_info)
            logger.info(pos_info)

        summary = f"\nAffected combinations: {len(account_instrument_groups)}"
        print(summary)
        logger.info(summary)
        for (acct, instr), pos_ids in account_instrument_groups.items():
            combo_info = f"  {acct}/{instr}: {len(pos_ids)} positions"
            print(combo_info)
            logger.info(combo_info)

        # Confirm before proceeding (skip if not interactive)
        if not dry_run:
            import sys
            if sys.stdin.isatty():
                print(f"\nAbout to delete {len(position_ids_to_delete)} positions and rebuild them.")
                response = input("Continue? [y/N]: ")
                if response.lower() != 'y':
                    logger.info("Rebuild cancelled by user")
                    return {
                        'positions_deleted': 0,
                        'positions_created': 0,
                        'accounts_affected': set(),
                        'instruments_affected': set()
                    }
            else:
                # Non-interactive mode - proceed automatically
                logger.info(f"Non-interactive mode: proceeding to delete {len(position_ids_to_delete)} positions")

        # Delete old positions
        delete_positions(position_service.conn, position_ids_to_delete, dry_run)

        # Rebuild positions for each account/instrument
        total_positions_created = 0
        for (acct, instr) in account_instrument_groups.keys():
            positions_created = rebuild_positions_for_account_instrument(
                position_service, acct, instr, dry_run
            )
            total_positions_created += positions_created

        # Results
        results = {
            'positions_deleted': len(position_ids_to_delete),
            'positions_created': total_positions_created,
            'accounts_affected': set(acct for acct, _ in account_instrument_groups.keys()),
            'instruments_affected': set(instr for _, instr in account_instrument_groups.keys())
        }

        print("\n" + "=" * 80)
        print("REBUILD SUMMARY")
        print("=" * 80)
        print(f"Positions deleted: {results['positions_deleted']}")
        print(f"Positions created: {results['positions_created']}")
        print(f"Accounts affected: {len(results['accounts_affected'])}")
        print(f"Instruments affected: {len(results['instruments_affected'])}")

        logger.info("\n" + "=" * 80)
        logger.info("REBUILD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Positions deleted: {results['positions_deleted']}")
        logger.info(f"Positions created: {results['positions_created']}")
        logger.info(f"Accounts affected: {len(results['accounts_affected'])}")
        logger.info(f"Instruments affected: {len(results['instruments_affected'])}")

        if results['accounts_affected']:
            accounts_str = f"\nAccounts: {', '.join(sorted(results['accounts_affected']))}"
            print(accounts_str)
            logger.info(accounts_str)
        if results['instruments_affected']:
            instruments_str = f"Instruments: {', '.join(sorted(results['instruments_affected']))}"
            print(instruments_str)
            logger.info(instruments_str)

        if dry_run:
            dry_run_msg = "\n[DRY RUN] No changes were made to the database"
            print(dry_run_msg)
            logger.info(dry_run_msg)
        else:
            complete_msg = "\nRebuild complete! Database has been updated."
            print(complete_msg)
            logger.info(complete_msg)

        return results


def main():
    parser = argparse.ArgumentParser(description="Rebuild positions with fixed boundary detection")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without modifying database")
    parser.add_argument('--account', type=str, help="Only rebuild positions for specific account")
    parser.add_argument('--instrument', type=str, help="Only rebuild positions for specific instrument")
    parser.add_argument('--date', type=str, help="Only rebuild positions from specific date (YYYY-MM-DD)")
    parser.add_argument('--all', action='store_true', help="Rebuild ALL positions (default: only suspicious ones)")
    parser.add_argument('--db-path', type=str, help="Path to database file (default: from config)")

    args = parser.parse_args()

    # Use config database path if not specified
    if args.db_path:
        db_path = Path(args.db_path)
        if not db_path.is_absolute():
            db_path = Path(__file__).parent.parent / db_path
    else:
        # Use database path from config
        from config import config
        db_path = Path(config.db_path)

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    # Run rebuild
    try:
        rebuild(
            str(db_path),
            account=args.account,
            instrument=args.instrument,
            date=args.date,
            rebuild_all=args.all,
            dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"Rebuild failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
