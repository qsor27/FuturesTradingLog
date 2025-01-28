import pandas as pd
import json
import os
from datetime import datetime
import glob
import shutil

def create_archive_folder():
    """Create Archive folder if it doesn't exist"""
    if not os.path.exists('Archive'):
        os.makedirs('Archive')

def process_trades(df, multipliers):
    """Process trades from a NinjaTrader DataFrame"""
    # Create an explicit copy of the DataFrame
    ninja_trades_df = df.copy()
    
    # Convert Commission to float, removing '$' if present
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

def main():
    # Create Archive folder
    create_archive_folder()

    # Read the instrument multipliers
    with open('instrument_multipliers.json', 'r') as f:
        multipliers = json.load(f)

    # Find all NinjaTrader grid files
    ninja_files = glob.glob('NinjaTrader*.csv')
    
    if not ninja_files:
        print("No NinjaTrader files found for processing")
        return

    all_processed_trades = []
    
    # Process each NinjaTrader file
    for ninja_file in ninja_files:
        print(f"Processing {ninja_file}...")
        
        # Read the trades CSV
        df = pd.read_csv(ninja_file)
        
        # Process the trades
        processed_trades = process_trades(df, multipliers)
        all_processed_trades.extend(processed_trades)
        
        # Move processed file to Archive folder
        archive_path = os.path.join('Archive', ninja_file)
        shutil.move(ninja_file, archive_path)
        print(f"Moved {ninja_file} to Archive folder")

    # Convert processed trades to DataFrame
    new_trades_df = pd.DataFrame(all_processed_trades)

    # If TradeLog.csv exists, append to it; otherwise create new
    if os.path.exists('TradeLog.csv'):
        existing_trades_df = pd.read_csv('TradeLog.csv')
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
        combined_trades_df.to_csv('TradeLog.csv', index=False)
    else:
        # Save new trades to CSV
        new_trades_df.to_csv('TradeLog.csv', index=False)

    print(f"Processing complete. {len(all_processed_trades)} new trades have been added to TradeLog.csv")

if __name__ == "__main__":
    main()