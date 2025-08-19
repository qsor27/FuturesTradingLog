"""
Secure Execution Processing with Input Validation

Enhanced version of ExecutionProcessing.py with:
- File size and row count limits
- Pydantic validation for each row
- Malicious content detection
- Graceful error handling
- Progress tracking
"""

import pandas as pd
import json
import os
from datetime import datetime
import glob
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from decimal import Decimal

from config import config
from models.execution import Execution, ExecutionAction, ExecutionType
from pydantic import ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security limits
MAX_FILE_SIZE_MB = 10
MAX_ROWS = 100000
REQUIRED_COLUMNS = ['ID', 'Account', 'Instrument', 'Time', 'Action', 'E/X', 'Quantity', 'Price', 'Commission']
SUSPICIOUS_PATTERNS = [
    '=cmd', '=system', '=exec', '=shell',  # Command injection patterns
    '<script', 'javascript:', 'vbscript:',  # Script injection patterns
    'DROP TABLE', 'DELETE FROM', 'INSERT INTO', 'UPDATE SET',  # SQL injection patterns
]


class SecureExecutionProcessor:
    """Secure processor for NinjaTrader execution files"""
    
    def __init__(self, multipliers: Dict[str, float]):
        self.multipliers = multipliers
        self.processed_count = 0
        self.error_count = 0
        self.warnings: List[str] = []
        
    def validate_file_security(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate file security and size limits.
        
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
            
            # Basic content scan for suspicious patterns
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Read first 1MB for quick scan
                    content = f.read(1024 * 1024)
                    content_lower = content.lower()
                    
                    for pattern in SUSPICIOUS_PATTERNS:
                        if pattern.lower() in content_lower:
                            return False, f"Suspicious content detected: {pattern}"
                            
            except UnicodeDecodeError:
                return False, "File contains invalid characters. Please ensure UTF-8 encoding."
            
            return True, "File validation passed"
            
        except Exception as e:
            return False, f"File validation error: {str(e)}"
    
    def validate_csv_structure(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate CSV structure and row count.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check row count
            if len(df) > MAX_ROWS:
                return False, f"Too many rows: {len(df)} > {MAX_ROWS} limit"
            
            # Check required columns
            missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
            if missing_cols:
                return False, f"Missing required columns: {missing_cols}"
            
            # Check for empty DataFrame
            if len(df) == 0:
                return False, "File contains no data rows"
            
            # Check for duplicate IDs
            if df['ID'].duplicated().any():
                duplicate_count = df['ID'].duplicated().sum()
                self.warnings.append(f"Found {duplicate_count} duplicate IDs - will be removed")
            
            return True, "CSV structure validation passed"
            
        except Exception as e:
            return False, f"CSV structure validation error: {str(e)}"
    
    def validate_row_data(self, row: pd.Series) -> Optional[Execution]:
        """
        Validate a single row using Pydantic model.
        
        Returns:
            Validated Execution object or None if invalid
        """
        try:
            # Convert pandas Series to dict
            row_dict = row.to_dict()
            
            # Create Execution object with validation
            execution = Execution.from_ninja_row(row_dict)
            return execution
            
        except ValidationError as e:
            self.error_count += 1
            logger.warning(f"Row validation failed for ID {row.get('ID', 'unknown')}: {e}")
            return None
        except Exception as e:
            self.error_count += 1
            logger.error(f"Unexpected error validating row {row.get('ID', 'unknown')}: {e}")
            return None
    
    def process_trades_secure(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Process trades with security validation.
        
        Returns:
            List of processed trade dictionaries
        """
        logger.info(f"Processing {len(df)} executions with security validation")
        
        # Validate and convert each row
        valid_executions = []
        for index, row in df.iterrows():
            execution = self.validate_row_data(row)
            if execution:
                valid_executions.append(execution)
            else:
                logger.warning(f"Skipping invalid row {index + 1}")
        
        if not valid_executions:
            logger.error("No valid executions found in file")
            return []
        
        logger.info(f"Successfully validated {len(valid_executions)} executions")
        
        # Process executions by account
        processed_trades = []
        executions_by_account = {}
        
        # Group executions by account
        for execution in valid_executions:
            if execution.account not in executions_by_account:
                executions_by_account[execution.account] = []
            executions_by_account[execution.account].append(execution)
        
        # Process each account separately
        for account, executions in executions_by_account.items():
            logger.info(f"Processing account: {account}")
            
            # Sort executions by timestamp
            executions.sort(key=lambda x: x.timestamp)
            
            # Track open positions using FIFO
            open_positions = []
            
            for execution in executions:
                logger.debug(f"Processing {execution.execution_type.value}: {execution.action.value} {execution.quantity} at {execution.price}")
                
                if execution.is_opening:
                    # Opening new position
                    open_positions.append({
                        'execution': execution,
                        'remaining_quantity': execution.quantity
                    })
                    logger.debug(f"Added to open positions: {execution.quantity} contracts")
                    
                elif execution.is_closing:
                    # Closing position - match against open positions using FIFO
                    remaining_to_close = execution.quantity
                    positions_to_remove = []
                    
                    for i, open_pos in enumerate(open_positions):
                        if remaining_to_close <= 0:
                            break
                        
                        entry_execution = open_pos['execution']
                        available_quantity = open_pos['remaining_quantity']
                        
                        # Determine how much to close
                        close_qty = min(remaining_to_close, available_quantity)
                        
                        # Calculate P&L
                        if entry_execution.action == ExecutionAction.BUY:
                            points_pl = execution.price - entry_execution.price
                        else:  # SELL
                            points_pl = entry_execution.price - execution.price
                        
                        # Get multiplier
                        multiplier = Decimal(str(self.multipliers.get(execution.instrument, 1)))
                        
                        # Calculate commission
                        entry_commission = entry_execution.commission * (Decimal(str(close_qty)) / Decimal(str(entry_execution.quantity)))
                        exit_commission = execution.commission * (Decimal(str(close_qty)) / Decimal(str(execution.quantity)))
                        total_commission = entry_commission + exit_commission
                        
                        # Calculate dollar P&L
                        dollar_pl = (points_pl * multiplier * Decimal(str(close_qty))) - total_commission
                        
                        # Create unique trade ID
                        unique_id = f"{entry_execution.id}_to_{execution.id}_{len(processed_trades)+1}"
                        
                        # Create trade record
                        trade = {
                            'Instrument': execution.instrument,
                            'Side of Market': entry_execution.action.value,
                            'Quantity': close_qty,
                            'Entry Price': float(entry_execution.price),
                            'Entry Time': entry_execution.timestamp,
                            'Exit Time': execution.timestamp,
                            'Exit Price': float(execution.price),
                            'Result Gain/Loss in Points': round(float(points_pl), 2),
                            'Gain/Loss in Dollars': round(float(dollar_pl), 2),
                            'ID': unique_id,
                            'Commission': round(float(total_commission), 2),
                            'Account': execution.account
                        }
                        
                        processed_trades.append(trade)
                        self.processed_count += 1
                        
                        # Update remaining quantities
                        open_pos['remaining_quantity'] -= close_qty
                        remaining_to_close -= close_qty
                        
                        # Mark for removal if fully closed
                        if open_pos['remaining_quantity'] <= 0:
                            positions_to_remove.append(i)
                    
                    # Remove fully closed positions
                    for i in reversed(positions_to_remove):
                        open_positions.pop(i)
                    
                    # Warning if couldn't match all exits
                    if remaining_to_close > 0:
                        self.warnings.append(f"Could not match {remaining_to_close} contracts for exit in account {account}")
            
            # Warning for remaining open positions
            if open_positions:
                total_open = sum(pos['remaining_quantity'] for pos in open_positions)
                self.warnings.append(f"Account {account} has {total_open} contracts in open positions")
        
        logger.info(f"Successfully processed {self.processed_count} trades")
        return processed_trades
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single CSV file with full security validation.
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing file: {file_path}")
        
        # Reset counters
        self.processed_count = 0
        self.error_count = 0
        self.warnings = []
        
        try:
            # Step 1: File security validation
            is_valid, message = self.validate_file_security(file_path)
            if not is_valid:
                return {'success': False, 'error': message}
            
            # Step 2: Load CSV
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                return {'success': False, 'error': f"Failed to read CSV: {str(e)}"}
            
            # Step 3: CSV structure validation
            is_valid, message = self.validate_csv_structure(df)
            if not is_valid:
                return {'success': False, 'error': message}
            
            # Step 4: Process trades
            processed_trades = self.process_trades_secure(df)
            
            # Step 5: Return results
            return {
                'success': True,
                'trades_processed': self.processed_count,
                'validation_errors': self.error_count,
                'warnings': self.warnings,
                'processed_trades': processed_trades
            }
            
        except Exception as e:
            logger.error(f"Unexpected error processing file {file_path}: {e}")
            return {'success': False, 'error': f"Processing error: {str(e)}"}


def process_trades(csv_file_path: str, multipliers: Dict[str, float], delete_existing: bool = False) -> Dict[str, Any]:
    """
    Main entry point for secure trade processing.
    
    Args:
        csv_file_path: Path to CSV file
        multipliers: Instrument multipliers dictionary
        delete_existing: Whether to delete existing trades (not used in secure version)
    
    Returns:
        Dictionary with processing results
    """
    processor = SecureExecutionProcessor(multipliers)
    result = processor.process_file(csv_file_path)
    
    if result['success']:
        logger.info(f"Processing completed successfully: {result['trades_processed']} trades")
        if result['warnings']:
            logger.warning(f"Processing warnings: {result['warnings']}")
    else:
        logger.error(f"Processing failed: {result['error']}")
    
    return result


def create_archive_folder():
    """Create Archive folder if it doesn't exist"""
    archive_path = config.data_dir / 'archive'
    if not archive_path.exists():
        archive_path.mkdir(parents=True)


def main():
    """Main execution for command line usage"""
    # Change to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    logger.info(f"Starting secure execution processing")
    logger.info(f"Data directory: {config.data_dir}")
    
    # Ensure data directory exists
    os.makedirs(str(config.data_dir), exist_ok=True)
    create_archive_folder()
    
    # Read instrument multipliers
    try:
        with open(config.instrument_config, 'r') as f:
            multipliers = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load instrument multipliers: {e}")
        return
    
    # Find CSV files
    pattern = os.path.join(str(config.data_dir), 'NinjaTrader*.csv')
    ninja_files = glob.glob(pattern)
    
    if not ninja_files:
        logger.info("No NinjaTrader files found for processing")
        return
    
    # Process each file
    all_processed_trades = []
    total_errors = 0
    
    for file_path in ninja_files:
        logger.info(f"Processing {os.path.basename(file_path)}")
        
        result = process_trades(file_path, multipliers)
        
        if result['success']:
            all_processed_trades.extend(result['processed_trades'])
            total_errors += result['validation_errors']
            
            # Move processed file to archive
            archive_path = config.data_dir / 'archive' / os.path.basename(file_path)
            shutil.move(file_path, str(archive_path))
            logger.info(f"Moved {os.path.basename(file_path)} to archive")
        else:
            logger.error(f"Failed to process {os.path.basename(file_path)}: {result['error']}")
    
    # Save results
    if all_processed_trades:
        # Convert to DataFrame and save
        trades_df = pd.DataFrame(all_processed_trades)
        
        # Handle datetime columns
        datetime_columns = ['Entry Time', 'Exit Time']
        for col in datetime_columns:
            trades_df[col] = pd.to_datetime(trades_df[col])
        
        # Save to trade log
        trade_log_path = config.data_dir / 'trade_log.csv'
        
        if trade_log_path.exists():
            # Append to existing
            existing_df = pd.read_csv(trade_log_path)
            for col in datetime_columns:
                existing_df[col] = pd.to_datetime(existing_df[col])
            
            combined_df = pd.concat([existing_df, trades_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['ID'])
            combined_df = combined_df.sort_values('Entry Time')
            combined_df.to_csv(trade_log_path, index=False)
        else:
            trades_df.to_csv(trade_log_path, index=False)
        
        logger.info(f"Processing complete: {len(all_processed_trades)} trades processed")
        if total_errors > 0:
            logger.warning(f"Total validation errors: {total_errors}")
    else:
        logger.warning("No trades were processed")


if __name__ == "__main__":
    main()