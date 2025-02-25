import pandas as pd
import json
import os
from datetime import datetime, timedelta
import glob
import shutil
from typing import Dict, List

from config import config
from ninja_trader_api import NinjaTraderAPI

def process_trades(df, multipliers):
    """Process trades from NinjaTrader execution data"""
    # Create an explicit copy of the DataFrame
    ninja_trades_df = df.copy()
    
    # Convert Commission to float if it's a string
    if isinstance(ninja_trades_df['Commission'].iloc[0], str):
        ninja_trades_df.loc[:, 'Commission'] = ninja_trades_df['Commission'].str.replace('$', '', regex=False).astype(float)

    # Remove duplicates based on ID while keeping the first occurrence
    ninja_trades_df = ninja_trades_df.drop_duplicates(subset=['ID'])

    # Sort by Time to ensure proper order
    ninja_trades_df.loc[:, 'Time'] = pd.to_datetime(ninja_trades_df['Time'])
    ninja_trades_df = ninja_trades_df.sort_values('Time')

    # Initialize list to store processed trades
    processed_trades = []

    # Group by ID to match entries and exits
    entries = ninja_trades_df[ninja_trades_df['E/X'] == 'Entry']
    exits = ninja_trades_df[ninja_trades_df['E/X'] == 'Exit']

    # Process each entry
    for _, entry in entries.iterrows():
        try:
            # Find matching exit
            matching_exit = exits[exits['Time'] > entry['Time']].iloc[0]
            
            # Determine side of market and calculate P&L
            if entry['Action'] == 'Buy':
                side = 'Long'
                points_pl = float(matching_exit['Price']) - float(entry['Price'])
            else:
                side = 'Short'
                points_pl = float(entry['Price']) - float(matching_exit['Price'])
            
            # Calculate dollar P&L including commission
            multiplier = float(multipliers[entry['Instrument']])
            commission = float(entry['Commission']) * 2  # Both entry and exit
            dollar_pl = (points_pl * multiplier * float(entry['Quantity'])) - commission
            
            # Create trade record
            trade = {
                'Instrument': entry['Instrument'],
                'Side of Market': side,
                'Quantity': int(entry['Quantity']),
                'Entry Price': float(entry['Price']),
                'Entry Time': entry['Time'],
                'Exit Time': matching_exit['Time'],
                'Exit Price': float(matching_exit['Price']),
                'Result Gain/Loss in Points': round(points_pl, 2),
                'Gain/Loss in Dollars': round(dollar_pl, 2),
                'ID': entry['ID'],
                'Commission': round(commission, 2),
                'Account': entry['Account']
            }
            
            processed_trades.append(trade)
        except Exception as e:
            print(f"Error processing trade with ID {entry['ID']}: {str(e)}")

    return processed_trades

def get_execution_data(nt_api: NinjaTraderAPI, start_date: datetime = None, account: str = None) -> pd.DataFrame:
    """
    Retrieve execution data from NinjaTrader API.
    
    Args:
        nt_api: NinjaTrader API instance
        start_date: Optional start date for data retrieval (defaults to 7 days ago)
        account: Optional account name to filter by
        
    Returns:
        DataFrame containing execution data
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=7)
    
    try:
        return nt_api.get_executions(start_date=start_date, account=account)
    except Exception as e:
        print(f"Error retrieving execution data from NinjaTrader: {e}")
        raise

def main():
    print("Initializing NinjaTrader API...")
    try:
        nt_api = NinjaTraderAPI()
    except Exception as e:
        print(f"Failed to initialize NinjaTrader API: {e}")
        print("Falling back to CSV file processing...")
        nt_api = None

    # Read the instrument multipliers
    with open(config.instrument_config, 'r') as f:
        multipliers = json.load(f)

    # Try to get data directly from NinjaTrader API
    if nt_api and nt_api.connected:
        try:
            df = get_execution_data(nt_api)
            all_processed_trades = process_trades(df, multipliers)
        except NotImplementedError:
            print("Direct API access not implemented yet, falling back to CSV processing...")
            nt_api = None
        except Exception as e:
            print(f"Error accessing NinjaTrader API: {e}")
            print("Falling back to CSV file processing...")
            nt_api = None

    # Fall back to CSV processing if API access fails
    if not nt_api or not nt_api.connected:
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
            
            # Read the trades CSV
            full_path = os.path.join(str(config.data_dir), ninja_file)
            df = pd.read_csv(full_path)
            
            # Process the trades
            processed_trades = process_trades(df, multipliers)
            all_processed_trades.extend(processed_trades)
            
            # Move processed file to Archive folder
            archive_path = os.path.join(str(config.data_dir), 'archive', os.path.basename(ninja_file))
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            shutil.move(full_path, archive_path)
            print(f"Moved {ninja_file} to Archive folder")

    # Convert processed trades to DataFrame
    new_trades_df = pd.DataFrame(all_processed_trades)

    # If no new trades were processed, exit
    if len(all_processed_trades) == 0:
        print("No new trades to process")
        return

    trade_log_path = os.path.join(str(config.data_dir), 'trade_log.csv')

    # If trade log exists, append to it; otherwise create new
    if os.path.exists(trade_log_path):
        existing_trades_df = pd.read_csv(trade_log_path)
        # Convert datetime columns to consistent format
        datetime_columns = ['Entry Time', 'Exit Time']
        for col in datetime_columns:
            new_trades_df[col] = pd.to_datetime(new_trades_df[col])
            existing_trades_df[col] = pd.to_datetime(existing_trades_df[col])
        
        # Combine existing and new trades
        combined_trades_df = pd.concat([existing_trades_df, new_trades_df], ignore_index=True)
        
        # Remove any duplicates based on ID
        combined_trades_df = combined_trades_df.drop_duplicates(subset=['ID'])
        
        # Sort by Entry Time
        combined_trades_df = combined_trades_df.sort_values('Entry Time')
        
        # Save to CSV
        combined_trades_df.to_csv(trade_log_path, index=False)
    else:
        # Save new trades to CSV
        new_trades_df.to_csv(trade_log_path, index=False)

    print(f"Processing complete. {len(all_processed_trades)} new trades have been added to trade_log.csv")

if __name__ == "__main__":
    main()