"""
Historical CSV Re-Import Script (Task Group 7)

One-time database migration script to re-import all historical CSV files
from the archive folder with proper account-aware position tracking.

Usage:
    python scripts/reimport_historical_csvs.py [--dry-run] [--force]

Options:
    --dry-run    Preview what would be imported without making database changes
    --force      Skip user confirmation prompt before clearing database

This script will:
1. Scan data/archive folder for NinjaTrader CSV files
2. Sort files chronologically by date in filename
3. Clear existing trades and positions tables (with confirmation)
4. Process each CSV file sequentially using the import service
5. Rebuild positions from scratch with account separation
6. Report summary statistics

CRITICAL: This will delete ALL existing trades and positions!
Use --dry-run first to preview the operation.
"""

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from services.ninjatrader_import_service import ninjatrader_import_service


def setup_logging() -> logging.Logger:
    """
    Setup logging to console and file.

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('HistoricalReimport')
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    log_dir = config.data_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / 'reimport.log')
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def discover_archive_csvs(data_dir: Path) -> List[Path]:
    """
    Scan archive folder for CSV files matching NinjaTrader pattern.

    Task 7.3: Implement archive CSV discovery and sorting
    - Scan data/archive folder for CSV files
    - Filter files matching pattern: NinjaTrader_Executions_YYYYMMDD.csv
    - Sort files chronologically by date in filename
    - Log discovered file count and date range

    Args:
        data_dir: Base data directory path

    Returns:
        List of CSV file paths sorted chronologically
    """
    logger = logging.getLogger('HistoricalReimport')

    archive_dir = data_dir / 'archive'

    if not archive_dir.exists():
        logger.error(f"Archive directory not found: {archive_dir}")
        return []

    # Find all CSV files matching pattern
    pattern = 'NinjaTrader_Executions_*.csv'
    csv_files = list(archive_dir.glob(pattern))

    if not csv_files:
        logger.warning(f"No CSV files found in archive directory: {archive_dir}")
        return []

    # Sort chronologically by date in filename
    def extract_date(filepath: Path) -> str:
        """Extract YYYYMMDD date from filename"""
        try:
            # Filename format: NinjaTrader_Executions_YYYYMMDD.csv
            return filepath.stem.split('_')[-1]
        except:
            return ''

    csv_files.sort(key=extract_date)

    # Log discovered files
    if csv_files:
        dates = [extract_date(f) for f in csv_files]
        date_range = f"{dates[0]} to {dates[-1]}"
        logger.info(f"Discovered {len(csv_files)} CSV files in archive (date range: {date_range})")
    else:
        logger.info("No CSV files discovered in archive")

    return csv_files


def clear_database_tables(db_path: Path, dry_run: bool = False, force: bool = False) -> Dict[str, int]:
    """
    Clear existing trades and positions tables with confirmation.

    Task 7.4: Implement database clearing (with confirmation)
    - Prompt user for confirmation unless --force flag provided
    - Execute: DELETE FROM position_executions (foreign key dependency)
    - Execute: DELETE FROM positions
    - Execute: DELETE FROM trades
    - Log deletion counts for each table
    - Skip deletion in dry-run mode

    Args:
        db_path: Path to SQLite database
        dry_run: If True, skip actual deletion
        force: If True, skip user confirmation

    Returns:
        Dictionary with deletion counts for each table
    """
    logger = logging.getLogger('HistoricalReimport')

    if dry_run:
        logger.info("[DRY RUN] Would clear database tables (skipping in dry-run mode)")
        return {'position_executions': 0, 'positions': 0, 'trades': 0}

    # Count existing records
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM position_executions")
    pe_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM positions")
    pos_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM trades")
    trade_count = cursor.fetchone()[0]

    conn.close()

    logger.info(f"Current database contents:")
    logger.info(f"  - position_executions: {pe_count} records")
    logger.info(f"  - positions: {pos_count} records")
    logger.info(f"  - trades: {trade_count} records")

    # Prompt for confirmation unless force flag set
    if not force:
        logger.warning("\n" + "=" * 60)
        logger.warning("WARNING: This will DELETE ALL existing data!")
        logger.warning("=" * 60)
        response = input("\nType 'YES' to confirm deletion: ")

        if response != 'YES':
            logger.info("Operation cancelled by user")
            sys.exit(0)

    # Delete tables in correct order (foreign key dependencies)
    logger.info("Clearing database tables...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Delete in order: position_executions -> positions -> trades
        cursor.execute("DELETE FROM position_executions")
        logger.info(f"Deleted {pe_count} records from position_executions")

        cursor.execute("DELETE FROM positions")
        logger.info(f"Deleted {pos_count} records from positions")

        cursor.execute("DELETE FROM trades")
        logger.info(f"Deleted {trade_count} records from trades")

        conn.commit()
        logger.info("Database tables cleared successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error clearing database tables: {e}")
        raise

    finally:
        conn.close()

    return {
        'position_executions': pe_count,
        'positions': pos_count,
        'trades': trade_count
    }


def process_archive_csvs(
    data_dir: Path,
    db_path: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Process all archive CSV files sequentially in chronological order.

    Task 7.5: Implement sequential CSV processing
    - For each CSV file in chronological order:
      - Call ninjatrader_import_service.process_csv_file(file_path)
      - Track: executions imported, positions created, accounts found
      - Log progress every 10 files processed
    - Skip actual import in dry-run mode (only validate CSVs)

    Task 7.6: Implement summary statistics reporting
    - Collect totals: files processed, executions imported, positions created, unique accounts
    - Calculate processing time (start to finish)
    - Log summary statistics at completion

    Args:
        data_dir: Base data directory path
        db_path: Path to SQLite database
        dry_run: If True, preview without database changes

    Returns:
        Dictionary with processing results and summary statistics
    """
    logger = logging.getLogger('HistoricalReimport')

    # Discover archive CSV files
    csv_files = discover_archive_csvs(data_dir)

    if not csv_files:
        logger.error("No CSV files found to process")
        return {
            'success': False,
            'files_discovered': 0,
            'files_processed': 0,
            'executions_imported': 0,
            'error': 'No CSV files found in archive'
        }

    if dry_run:
        logger.info(f"\n[DRY RUN] Would process {len(csv_files)} CSV files:")
        for i, csv_file in enumerate(csv_files, 1):
            logger.info(f"  {i}. {csv_file.name}")
        return {
            'success': True,
            'files_discovered': len(csv_files),
            'files_processed': 0,
            'executions_imported': 0,
            'dry_run': True
        }

    # Start processing
    start_time = time.time()
    logger.info(f"\nStarting sequential processing of {len(csv_files)} CSV files...")

    # Statistics tracking
    files_processed = 0
    executions_imported = 0
    files_failed = 0
    unique_accounts = set()
    unique_instruments = set()

    # Process each file sequentially
    for i, csv_file in enumerate(csv_files, 1):
        try:
            logger.info(f"\nProcessing file {i}/{len(csv_files)}: {csv_file.name}")

            # Call import service to process file
            result = ninjatrader_import_service.process_csv_file(csv_file)

            if result.get('success'):
                files_processed += 1
                executions_imported += result.get('executions_imported', 0)

                # Log progress
                logger.info(
                    f"  ✓ Imported {result.get('executions_imported', 0)} executions, "
                    f"skipped {result.get('executions_skipped', 0)}"
                )

                # Track unique accounts and instruments (from database)
                # Note: We could track these from the result, but let's query the DB
                # to ensure accuracy after position building

            else:
                files_failed += 1
                logger.warning(
                    f"  ✗ Failed: {result.get('error', 'Unknown error')}"
                )

            # Log progress every 10 files
            if i % 10 == 0:
                logger.info(
                    f"\nProgress: {i}/{len(csv_files)} files processed "
                    f"({files_processed} successful, {files_failed} failed)"
                )

        except Exception as e:
            files_failed += 1
            logger.error(f"  ✗ Error processing {csv_file.name}: {e}", exc_info=True)

    # Calculate processing time
    processing_time = time.time() - start_time

    # Query database for final statistics
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count unique accounts
        cursor.execute("SELECT COUNT(DISTINCT account) FROM trades")
        account_count = cursor.fetchone()[0]

        # Count unique instruments
        cursor.execute("SELECT COUNT(DISTINCT instrument) FROM trades")
        instrument_count = cursor.fetchone()[0]

        # Count positions created
        cursor.execute("SELECT COUNT(*) FROM positions")
        positions_created = cursor.fetchone()[0]

        conn.close()

    except Exception as e:
        logger.error(f"Error querying final statistics: {e}")
        account_count = 0
        instrument_count = 0
        positions_created = 0

    # Log summary statistics
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Files discovered:        {len(csv_files)}")
    logger.info(f"Files processed:         {files_processed}")
    logger.info(f"Files failed:            {files_failed}")
    logger.info(f"Executions imported:     {executions_imported}")
    logger.info(f"Positions created:       {positions_created}")
    logger.info(f"Unique accounts:         {account_count}")
    logger.info(f"Unique instruments:      {instrument_count}")
    logger.info(f"Processing time:         {processing_time:.1f} seconds")
    logger.info("=" * 80)

    # Format summary message
    summary_message = (
        f"Processed {files_processed} files, imported {executions_imported} executions, "
        f"created {positions_created} positions across {account_count} accounts "
        f"in {processing_time:.1f} seconds"
    )
    logger.info(f"\n{summary_message}")

    return {
        'success': True,
        'files_discovered': len(csv_files),
        'files_processed': files_processed,
        'files_failed': files_failed,
        'executions_imported': executions_imported,
        'positions_created': positions_created,
        'unique_accounts': account_count,
        'unique_instruments': instrument_count,
        'processing_time': processing_time,
        'summary_message': summary_message
    }


def reimport_all_historical_data(dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    Main function to re-import all historical CSV files.

    Task 7.2: Create reimport_historical_csvs.py script
    - Main function: reimport_all_historical_data(dry_run=False)
    - Parse command line args: --dry-run flag
    - Connect to SQLite database using config.db_path
    - Setup logging to console and file

    Args:
        dry_run: If True, preview without database changes
        force: If True, skip user confirmation

    Returns:
        Dictionary with operation results
    """
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("HISTORICAL CSV RE-IMPORT SCRIPT")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Data directory: {config.data_dir}")
    logger.info(f"Database: {config.db_path}")
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE (will modify database)'}")
    logger.info("=" * 80 + "\n")

    try:
        # Step 1: Discover archive CSV files
        logger.info("Step 1: Discovering archive CSV files...")
        csv_files = discover_archive_csvs(config.data_dir)

        if not csv_files:
            logger.error("No CSV files found. Exiting.")
            return {
                'success': False,
                'error': 'No CSV files found in archive'
            }

        # Step 2: Clear database tables
        if not dry_run:
            logger.info("\nStep 2: Clearing database tables...")
            deletion_counts = clear_database_tables(
                config.db_path,
                dry_run=dry_run,
                force=force
            )
        else:
            logger.info("\nStep 2: Clearing database tables (skipped in dry-run mode)")
            deletion_counts = {}

        # Step 3: Process archive CSVs
        logger.info("\nStep 3: Processing archive CSV files...")
        result = process_archive_csvs(
            config.data_dir,
            config.db_path,
            dry_run=dry_run
        )

        # Add deletion counts to result
        result['deletion_counts'] = deletion_counts

        # Final status
        logger.info("\n" + "=" * 80)
        if result.get('success'):
            logger.info("✓ Historical re-import completed successfully!")
        else:
            logger.error("✗ Historical re-import failed")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"Fatal error during re-import: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """
    Command line entry point.

    Parse arguments and execute re-import operation.
    """
    parser = argparse.ArgumentParser(
        description='Re-import all historical CSV files from archive with account-aware position tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be imported (recommended first step)
  python scripts/reimport_historical_csvs.py --dry-run

  # Re-import with confirmation prompt
  python scripts/reimport_historical_csvs.py

  # Re-import without confirmation prompt
  python scripts/reimport_historical_csvs.py --force

CRITICAL WARNING:
  This script will DELETE ALL existing trades and positions!
  Always use --dry-run first to preview the operation.
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be imported without making database changes'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip user confirmation prompt before clearing database'
    )

    args = parser.parse_args()

    # Execute re-import
    result = reimport_all_historical_data(
        dry_run=args.dry_run,
        force=args.force
    )

    # Exit with appropriate code
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
