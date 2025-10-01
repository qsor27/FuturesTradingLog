"""
Import Service - Handles CSV Import Operations

Extracted from DatabaseManager to follow single responsibility principle.
This service manages the complex logic of importing NinjaTrader execution data
from CSV files into the database.
"""

import logging
import pandas as pd
from datetime import datetime
from typing import Optional

# Get database logger
db_logger = logging.getLogger('database')


class ImportService:
    """
    Service for importing NinjaTrader execution data from CSV files
    
    Supports both basic (15 fields) and enhanced (23 fields) CSV formats
    from the NinjaScript indicator.
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager for repository access"""
        self.db_manager = db_manager
    
    def import_raw_executions(self, csv_path: str) -> bool:
        """
        Import raw NinjaTrader executions directly as individual execution records
        Supports both basic (15 fields) and enhanced (23 fields) CSV formats from NinjaScript indicator
        
        Args:
            csv_path: Path to the CSV file containing execution data
            
        Returns:
            bool: True if import was successful, False otherwise
        """
        try:
            db_logger.info(f"Importing raw executions from {csv_path}...")
            
            # Read CSV file using pandas with robust error handling
            df = self._read_csv_file(csv_path)
            if df is None:
                return False
            
            db_logger.info(f"Read {len(df)} raw executions from CSV")
            
            # Clean up and validate CSV data
            df = self._clean_and_validate_csv(df)
            if df is None:
                return False
            
            # Convert timestamps
            df['Time'] = pd.to_datetime(df['Time'])
            
            # Process executions and import to database
            imported_count = self._process_executions(df)
            
            self.db_manager.conn.commit()
            db_logger.info(f"Successfully imported {imported_count} raw executions")
            return True
            
        except Exception as e:
            db_logger.error(f"Error importing raw executions: {e}")
            self.db_manager.conn.rollback()
            return False
    
    def _read_csv_file(self, csv_path: str) -> Optional[pd.DataFrame]:
        """
        Read CSV file with robust error handling for various encoding issues
        
        Returns:
            DataFrame or None if reading failed
        """
        try:
            # Primary attempt with standard settings
            df = pd.read_csv(csv_path, 
                           encoding='utf-8-sig',  # Handle BOM characters
                           on_bad_lines='skip',    # Skip malformed lines
                           skipinitialspace=True)  # Handle extra spaces
            return df
        except Exception as e:
            try:
                # Fallback: use Python engine for more robust parsing
                df = pd.read_csv(csv_path,
                               encoding='utf-8-sig', 
                               engine='python',
                               on_bad_lines='skip')
                return df
            except Exception as e2:
                db_logger.error(f"Error reading CSV file: {e2}")
                return None
    
    def _clean_and_validate_csv(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Clean up CSV data and validate required columns are present
        
        Returns:
            Cleaned DataFrame or None if validation failed
        """
        # Clean up column names and data
        df.columns = df.columns.str.strip()  # Remove whitespace from column names
        
        # Remove empty columns (caused by trailing commas)
        df = df.dropna(axis=1, how='all')
        
        # Detect CSV format based on column count
        num_cols = len(df.columns)
        db_logger.info(f"Detected CSV format: {num_cols} columns")
        
        # Validate we have the minimum required columns for basic format
        required_basic_cols = [
            'Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'E/X', 
            'Position', 'Order ID', 'Name', 'Commission', 'Rate', 'Account', 'Connection'
        ]
        
        # Check if we have all required basic columns
        missing_cols = [col for col in required_basic_cols if col not in df.columns]
        if missing_cols:
            db_logger.error(f"Missing required columns: {missing_cols}")
            return None
        
        db_logger.info("CSV format validated - basic columns present")
        if num_cols > 15:
            db_logger.info(f"Enhanced format detected with {num_cols - 14} additional fields")
        
        return df
    
    def _process_executions(self, df: pd.DataFrame) -> int:
        """
        Process each execution row and insert into database
        
        Returns:
            Number of successfully imported executions
        """
        imported_count = 0
        
        # Process each execution row
        for _, row in df.iterrows():
            try:
                trade_data = self._parse_execution_row(row)
                if trade_data:
                    success = self.db_manager.trades.add_trade(trade_data)
                    if success:
                        imported_count += 1
                        
            except Exception as row_error:
                db_logger.warning(f"Error processing row: {row_error}")
                continue
        
        return imported_count
    
    def _parse_execution_row(self, row) -> Optional[dict]:
        """
        Parse a single execution row into trade data dictionary
        
        Returns:
            Dictionary with trade data or None if parsing failed
        """
        try:
            # Parse basic execution data
            instrument = str(row['Instrument']).strip()
            action = str(row['Action']).strip()  # Buy/Sell
            quantity = int(row['Quantity'])
            price = float(row['Price'])
            execution_time = row['Time']
            execution_id = str(row['ID']).strip()
            entry_exit = str(row['E/X']).strip()  # Entry/Exit
            account = str(row['Account']).strip()
            
            # Parse commission - handle '$0.00' format
            commission = self._parse_commission(row['Commission'])
            
            # CRITICAL FIX: Keep original action (Buy/Sell) as side_of_market for proper position building
            # This preserves the actual market action rather than converting to Long/Short
            side_of_market = action  # 'Buy' or 'Sell' - this is what position builder expects
            
            # Create unique entry_execution_id for duplicate prevention
            entry_execution_id = f"{execution_id}_{account}"
            
            # CRITICAL FIX: Convert pandas Timestamp to ISO string for SQLite compatibility
            execution_time_str = execution_time.isoformat() if hasattr(execution_time, 'isoformat') else str(execution_time)
            
            # Build trade data dictionary
            trade_data = {
                'instrument': instrument,
                'side_of_market': side_of_market,
                'quantity': quantity,
                'entry_price': price,
                'entry_time': execution_time_str,
                'account': account,
                'commission': commission,
                'entry_execution_id': entry_execution_id,
                # CRITICAL: Set these to zero for raw executions so position builder knows to aggregate them
                'points_gain_loss': 0.0,
                'dollars_gain_loss': 0.0,
                'exit_price': None,
                'exit_time': None
            }
            
            return trade_data
            
        except Exception as e:
            db_logger.warning(f"Error parsing execution row: {e}")
            return None
    
    def _parse_commission(self, commission_value) -> float:
        """
        Parse commission value from various formats
        
        Args:
            commission_value: Commission value from CSV (could be '$0.00', '0.00', etc.)
            
        Returns:
            Float commission value
        """
        commission_str = str(commission_value).strip()
        if commission_str and commission_str != '':
            # Remove '$' sign and commas if present
            commission_str = commission_str.replace('$', '').replace(',', '')
            try:
                return float(commission_str)
            except ValueError:
                return 0.0
        else:
            return 0.0