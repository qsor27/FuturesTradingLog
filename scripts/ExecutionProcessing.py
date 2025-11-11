import pandas as pd
import json
import os
from datetime import datetime
import glob
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

from config import config

# Import secure processor if available
try:
    from secure_execution_processing import SecureExecutionProcessor
    SECURE_PROCESSING_AVAILABLE = True
except ImportError:
    SECURE_PROCESSING_AVAILABLE = False
    logging.warning("Secure processing not available - using legacy mode")

# Import cache manager for invalidation
try:
    from scripts.cache_manager import get_cache_manager
    CACHE_INVALIDATION_AVAILABLE = True
except ImportError:
    CACHE_INVALIDATION_AVAILABLE = False
    logging.warning("Cache invalidation not available")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security limits
MAX_FILE_SIZE_MB = 10
MAX_ROWS = 100000

def validate_file_security(file_path: str) -> Tuple[bool, str]:
    """
    Basic security validation for CSV files.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        file_path_obj = Path(file_path)
        
        # Check file exists
        if not file_path_obj.exists():
            return False, f"File not found: {file_path}"
        
        # Check file size
        file_size = file_path_obj.stat().st_size
        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"File too large: {file_size / (1024*1024):.1f}MB > {MAX_FILE_SIZE_MB}MB limit"
        
        # Check file extension
        if file_path_obj.suffix.lower() != '.csv':
            return False, f"Invalid file type: {file_path_obj.suffix}. Only CSV files allowed."
        
        return True, "File validation passed"
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"


def create_archive_folder():
    """Create Archive folder if it doesn't exist"""
    archive_path = config.data_dir / 'archive'
    if not archive_path.exists():
        archive_path.mkdir(parents=True)


def invalidate_cache_after_import(processed_trades: List[Dict]) -> None:
    """
    Invalidate cache after processing trades to ensure data consistency.
    """
    if not CACHE_INVALIDATION_AVAILABLE or not processed_trades:
        return
    
    try:
        # Extract unique instruments and accounts from processed trades
        instruments = set()
        accounts = set()
        
        for trade in processed_trades:
            if 'Instrument' in trade:
                instruments.add(trade['Instrument'])
            if 'Account' in trade:
                accounts.add(trade['Account'])
        
        instruments = list(instruments)
        accounts = list(accounts)
        
        if instruments or accounts:
            cache_manager = get_cache_manager()
            result = cache_manager.on_trade_import(instruments, accounts)
            
            logger.info(f"Cache invalidation completed for {len(instruments)} instruments, {len(accounts)} accounts")
            logger.debug(f"Cache invalidation details: {result}")
    
    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}")
        # Don't raise - cache invalidation failure shouldn't stop trade processing

def process_trades(df, multipliers):
    """
    Process executions from a NinjaTrader DataFrame and output individual execution records.

    This function outputs each execution (Entry or Exit) as a separate record without
    performing FIFO pairing. The position builder handles FIFO matching and P&L calculation.

    Args:
        df: DataFrame containing execution data with columns:
            ID, Account, Instrument, Time, Action, E/X, Quantity, Price, Commission
        multipliers: Dict mapping instrument names to their point multipliers

    Returns:
        List of individual execution records with the following structure:
        - All executions store their price in entry_price field (not exit_price)
        - Entry executions: execution_id, Account, Instrument, action, entry_exit='Entry',
          quantity, entry_price, entry_time, exit_price=None, exit_time=None, commission
        - Exit executions: execution_id, Account, Instrument, action, entry_exit='Exit',
          quantity, entry_price, entry_time, exit_price=None, exit_time=None, commission
    """
    # Validate DataFrame size
    if len(df) > MAX_ROWS:
        raise ValueError(f"DataFrame too large: {len(df)} rows > {MAX_ROWS} limit")

    # Create an explicit copy of the DataFrame
    ninja_trades_df = df.copy()

    # Validate required columns
    required_columns = ['ID', 'Account', 'Instrument', 'Time', 'Action', 'E/X', 'Quantity', 'Price', 'Commission']
    missing_columns = [col for col in required_columns if col not in ninja_trades_df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Convert Commission to float with error handling
    try:
        ninja_trades_df.loc[:, 'Commission'] = ninja_trades_df['Commission'].str.replace('$', '', regex=False).astype(float)
    except Exception as e:
        raise ValueError(f"Failed to parse Commission column: {str(e)}")

    # Remove duplicates based on ID while keeping the first occurrence
    ninja_trades_df = ninja_trades_df.drop_duplicates(subset=['ID'])

    # Sort by Time to ensure proper order with error handling
    try:
        ninja_trades_df.loc[:, 'Time'] = pd.to_datetime(ninja_trades_df['Time'])
        ninja_trades_df = ninja_trades_df.sort_values(['Account', 'Time'])
    except Exception as e:
        raise ValueError(f"Failed to parse Time column: {str(e)}")

    # Initialize list to store individual execution records
    individual_executions = []

    # Process each account separately to maintain account separation
    for account in ninja_trades_df['Account'].unique():
        account_df = ninja_trades_df[ninja_trades_df['Account'] == account].copy()
        print(f"Processing account: {account}")

        # Process each execution as an individual record
        for _, execution in account_df.iterrows():
            try:
                qty = int(execution['Quantity'])
                price = float(execution['Price'])
                time = execution['Time']
                exec_id = execution['ID']
                commission = float(execution['Commission'])
                instrument = execution['Instrument']
                action = execution['Action']  # Buy or Sell
                entry_exit = execution['E/X']  # Entry or Exit
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid execution row {execution['ID']}: {str(e)}")
                continue

            print(f"  Processing {entry_exit}: {action} {qty} at {price} (ID: {exec_id})")

            # Create individual execution record
            if entry_exit == 'Entry':
                # Entry execution: set entry fields, leave exit fields as None
                execution_record = {
                    'execution_id': exec_id,
                    'Account': account,
                    'Instrument': instrument,
                    'action': action,
                    'entry_exit': entry_exit,
                    'quantity': qty,
                    'entry_price': price,
                    'entry_time': time,
                    'exit_price': None,
                    'exit_time': None,
                    'commission': commission
                }
                print(f"    Created Entry execution record: {qty} contracts at {price}")

            elif entry_exit == 'Exit':
                # Exit execution: Store price in entry_price field (all individual executions use entry_price)
                # The exit_price field is only for completed round-trip trades (not individual executions)
                execution_record = {
                    'execution_id': exec_id,
                    'Account': account,
                    'Instrument': instrument,
                    'action': action,
                    'entry_exit': entry_exit,
                    'quantity': qty,
                    'entry_price': price,  # FIX: Store execution price in entry_price (not None)
                    'entry_time': time,  # Use execution timestamp
                    'exit_price': None,   # Leave as None for individual executions
                    'exit_time': None,    # Leave as None for individual executions
                    'commission': commission
                }
                print(f"    Created Exit execution record: {qty} contracts at {price}")

            else:
                logger.warning(f"Unknown execution type {entry_exit} for ID {exec_id}")
                continue

            individual_executions.append(execution_record)

        print(f"  Account {account} completed: {len([e for e in individual_executions if e['Account'] == account])} executions")

    print(f"\nTotal individual executions created: {len(individual_executions)}")
    return individual_executions

def main():
    # Change to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print(f"Script directory: {script_dir}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Data directory from config: {config.data_dir}")
    print(f"Data directory exists: {os.path.exists(str(config.data_dir))}")
    
    # Ensure data directory exists
    os.makedirs(str(config.data_dir), exist_ok=True)
    
    # Create Archive folder
    create_archive_folder()

    # Read the instrument multipliers
    with open(config.instrument_config, 'r') as f:
        multipliers = json.load(f)

    # Get glob pattern with full path
    ninja_files = []
    pattern = os.path.join(str(config.data_dir), 'NinjaTrader*.csv')
    for file in glob.glob(pattern):
        ninja_files.append(os.path.basename(file))
    
    if not ninja_files:
        print("No NinjaTrader files found for processing")
        return

    all_processed_trades = []
    
    # Process each NinjaTrader file
    for ninja_file in ninja_files:
        print(f"Processing {ninja_file}...")
        full_path = os.path.join(str(config.data_dir), ninja_file)
        
        # Validate file security
        is_valid, error_msg = validate_file_security(full_path)
        if not is_valid:
            logger.error(f"Security validation failed for {ninja_file}: {error_msg}")
            continue
        
        try:
            # Read the trades CSV
            df = pd.read_csv(full_path)
            
            # Process the trades
            processed_trades = process_trades(df, multipliers)
            all_processed_trades.extend(processed_trades)
        except Exception as e:
            logger.error(f"Failed to process {ninja_file}: {str(e)}")
            continue
        
        # Move processed file to Archive folder
        archive_path = config.data_dir / 'archive' / os.path.basename(ninja_file)
        shutil.move(full_path, str(archive_path))
        print(f"Moved {ninja_file} to Archive folder")

    # Convert processed trades to DataFrame
    new_trades_df = pd.DataFrame(all_processed_trades)
    
    # Invalidate cache after processing trades
    invalidate_cache_after_import(all_processed_trades)

    trade_log_path = os.path.join(str(config.data_dir), 'trade_log.csv')

    print(f"Data directory: {config.data_dir}")
    print(f"Trade log path: {trade_log_path}")

    # If trade log exists, append to it; otherwise create new
    if os.path.exists(trade_log_path):
        existing_trades_df = pd.read_csv(trade_log_path)
        # Convert datetime columns to consistent format
        # Use actual column names from execution records (lowercase with underscore)
        datetime_columns = ['entry_time', 'exit_time']
        for col in datetime_columns:
            if col in new_trades_df.columns:
                new_trades_df[col] = pd.to_datetime(new_trades_df[col])
            if col in existing_trades_df.columns:
                existing_trades_df[col] = pd.to_datetime(existing_trades_df[col])

        # Combine existing and new trades
        combined_trades_df = pd.concat([existing_trades_df, new_trades_df], ignore_index=True)

        # Remove any duplicates based on execution_id
        combined_trades_df = combined_trades_df.drop_duplicates(subset=['execution_id'])

        # Sort by entry_time (with fallback to exit_time for exit-only records)
        sort_column = 'entry_time' if 'entry_time' in combined_trades_df.columns else 'exit_time'
        combined_trades_df = combined_trades_df.sort_values(sort_column)
        
        # Ensure trade_log.csv is in the data directory
        trade_log_path = os.path.join(str(config.data_dir), 'trade_log.csv')
        
        # Save to CSV
        combined_trades_df.to_csv(trade_log_path, index=False)
    else:
        # Save new trades to CSV
        print(f"Saving trade log to: {trade_log_path}")
        new_trades_df.to_csv(trade_log_path, index=False)
        print(f"Trade log saved successfully: {os.path.exists(trade_log_path)}")

        # Verify file location
        print(f"Actual file location: {os.path.realpath(trade_log_path)}")

    print(f"Processing complete. {len(all_processed_trades)} new trades have been added to TradeLog.csv")

if __name__ == "__main__":
    main()