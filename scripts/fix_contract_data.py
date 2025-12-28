"""
One-time script to analyze and fix mixed contract data in OHLC table.

Problem: Data was previously stored under base symbols (e.g., "MNQ") instead of
full contract names (e.g., "MNQ SEP25"). This corrupts charts when contracts
roll over since different months have completely different prices.

Usage:
    python scripts/fix_contract_data.py --analyze
    python scripts/fix_contract_data.py --clear
    python scripts/fix_contract_data.py --clear --execute

After clearing, re-sync data to fetch correct contract-specific data.
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.TradingLog_db import FuturesDB

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_ohlc_data():
    """Analyze OHLC data to identify mixed contract issues."""
    logger.info("=" * 60)
    logger.info("OHLC Data Analysis - Checking for Mixed Contract Data")
    logger.info("=" * 60)

    with FuturesDB() as db:
        # Find base symbols (no expiration - potential mixed data)
        db.cursor.execute("""
            SELECT instrument,
                   COUNT(*) as record_count,
                   COUNT(DISTINCT timeframe) as timeframe_count,
                   MIN(timestamp) as earliest,
                   MAX(timestamp) as latest
            FROM ohlc_data
            WHERE instrument NOT LIKE '% %'
            GROUP BY instrument
            ORDER BY instrument
        """)

        base_symbol_data = db.cursor.fetchall()

        if base_symbol_data:
            logger.info("\n=== BASE SYMBOL DATA (Potentially Mixed) ===")
            logger.info("These may contain data from multiple contract months:")
            logger.info("-" * 60)

            total_base_records = 0
            for row in base_symbol_data:
                instrument, count, tf_count, earliest, latest = row
                earliest_dt = datetime.fromtimestamp(earliest) if earliest else None
                latest_dt = datetime.fromtimestamp(latest) if latest else None

                logger.info(f"  {instrument}:")
                logger.info(f"    Records: {count:,}")
                logger.info(f"    Timeframes: {tf_count}")
                if earliest_dt and latest_dt:
                    logger.info(f"    Date range: {earliest_dt.strftime('%Y-%m-%d')} to {latest_dt.strftime('%Y-%m-%d')}")
                total_base_records += count

            logger.info("-" * 60)
            logger.info(f"  TOTAL base symbol records: {total_base_records:,}")
        else:
            logger.info("\n=== BASE SYMBOL DATA ===")
            logger.info("  No base symbol data found (good!)")

        # Find contract-specific symbols (with expiration - correct format)
        db.cursor.execute("""
            SELECT instrument,
                   COUNT(*) as record_count,
                   COUNT(DISTINCT timeframe) as timeframe_count,
                   MIN(timestamp) as earliest,
                   MAX(timestamp) as latest
            FROM ohlc_data
            WHERE instrument LIKE '% %'
            GROUP BY instrument
            ORDER BY instrument
        """)

        contract_data = db.cursor.fetchall()

        if contract_data:
            logger.info("\n=== CONTRACT-SPECIFIC DATA (Correct Format) ===")
            logger.info("-" * 60)

            total_contract_records = 0
            for row in contract_data:
                instrument, count, tf_count, earliest, latest = row
                earliest_dt = datetime.fromtimestamp(earliest) if earliest else None
                latest_dt = datetime.fromtimestamp(latest) if latest else None

                logger.info(f"  {instrument}:")
                logger.info(f"    Records: {count:,}")
                logger.info(f"    Timeframes: {tf_count}")
                if earliest_dt and latest_dt:
                    logger.info(f"    Date range: {earliest_dt.strftime('%Y-%m-%d')} to {latest_dt.strftime('%Y-%m-%d')}")
                total_contract_records += count

            logger.info("-" * 60)
            logger.info(f"  TOTAL contract-specific records: {total_contract_records:,}")
        else:
            logger.info("\n=== CONTRACT-SPECIFIC DATA ===")
            logger.info("  No contract-specific data found")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)

        if base_symbol_data:
            logger.warning(f"  Found {len(base_symbol_data)} base symbols with mixed data")
            logger.warning("  Recommendation: Clear base symbol data and re-sync with contract-specific symbols")
            logger.info("  Run: python scripts/fix_contract_data.py --clear --execute")
        else:
            logger.info("  All OHLC data is stored with proper contract-specific symbols")


def clear_base_symbol_ohlc(dry_run=True):
    """Clear OHLC data stored under base symbols."""
    action = "[DRY RUN]" if dry_run else "[EXECUTING]"

    logger.info("=" * 60)
    logger.info(f"{action} Clearing Base Symbol OHLC Data")
    logger.info("=" * 60)

    with FuturesDB() as db:
        # Get counts first
        db.cursor.execute("""
            SELECT instrument, COUNT(*) as cnt
            FROM ohlc_data
            WHERE instrument NOT LIKE '% %'
            GROUP BY instrument
            ORDER BY instrument
        """)

        to_delete = db.cursor.fetchall()

        if not to_delete:
            logger.info("No base symbol data to clear.")
            return

        total_deleted = 0
        for instrument, count in to_delete:
            if dry_run:
                logger.info(f"  Would delete {count:,} records for: {instrument}")
            else:
                db.cursor.execute(
                    "DELETE FROM ohlc_data WHERE instrument = ?",
                    (instrument,)
                )
                db.conn.commit()
                logger.info(f"  Deleted {count:,} records for: {instrument}")
            total_deleted += count

        logger.info("-" * 60)
        verb = "Would delete" if dry_run else "Deleted"
        logger.info(f"{verb} {total_deleted:,} total records")

        if dry_run:
            logger.info("\nTo actually delete, run with --execute flag:")
            logger.info("  python scripts/fix_contract_data.py --clear --execute")
            logger.info("\nAfter clearing, re-sync data for your traded instruments.")


def main():
    parser = argparse.ArgumentParser(
        description="Fix mixed contract data in OHLC table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Analyze current data state:
    python scripts/fix_contract_data.py --analyze

  Preview what would be deleted (dry run):
    python scripts/fix_contract_data.py --clear

  Actually delete the mixed data:
    python scripts/fix_contract_data.py --clear --execute
        """
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze current OHLC data for mixed contract issues"
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear OHLC data stored under base symbols (dry run by default)"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the changes (without this flag, operations are dry-run)"
    )

    args = parser.parse_args()

    if not any([args.analyze, args.clear]):
        parser.print_help()
        return

    if args.analyze:
        analyze_ohlc_data()

    if args.clear:
        clear_base_symbol_ohlc(dry_run=not args.execute)


if __name__ == "__main__":
    main()
