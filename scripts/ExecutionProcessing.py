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

def print_dataframe_info(df, label):
    """Print detailed information about a DataFrame"""
    print(f"\n{label} DataFrame Info:")
    print(f"Number of rows: {len(df)}")
    if len(df) > 0:
        print("First row:")
        first_row = df.iloc[0]
        for col in df.columns:
            print(f"{col}: {first_row[col]} (type: {type(first_row[col]).__name__})")

def load_existing_trades():
    """Load existing trades from TradeLog.csv"""
    if not os.path.exists('TradeLog.csv'):
        print("No TradeLog.csv found.")
        return pd.DataFrame()

    print("\nLoading existing trades...")
    df = pd.read_csv('TradeLog.csv')
    print(f"Loaded {len(df)} existing trades")
    print_dataframe_info(df, "Existing Trades")
    return df

def compare_trades(new_trade, existing_trade):
    """Compare two trades and print details if they might be duplicates"""
    print("\nComparing trades:")
    print("New trade:")
    for key, value in new_trade.items():
        print(f"{key}: {value} (type: {type(value).__name__})")
    print("\nExisting trade:")
    for key, value in existing_trade.items():
        print(f"{key}: {value} (type: {type(value).__name__})")

def is_duplicate_trade(new_trade, existing_trades_df):
    """Check if a trade already exists in the database"""
    if len(existing_trades_df) == 0:
        return False

    print("\nChecking for duplicates with following values:")
    print(f"Entry Time: {new_trade['Entry Time']}")
    print(f"Exit Time: {new_trade['Exit Time']}")
    print(f"Entry Price: {new_trade['Entry Price']}")
    print(f"Exit Price: {new_trade['Exit Price']}")
    print(f"Quantity: {new_trade['Quantity']}")
    print(f"Account: {new_trade['Account']}")

    # Convert times to string format for exact comparison
    new_entry_time = pd.to_datetime(new_trade['Entry Time']).strftime('%Y-%m-%d %H:%M:%S')
    new_exit_time = pd.to_datetime(new_trade['Exit Time']).strftime('%Y-%m-%d %H:%M:%S')
    existing_trades_df['Entry_Time_Str'] = pd.to_datetime(existing_trades_df['Entry Time']).dt.strftime('%Y-%m-%d %H:%M:%S')
    existing_trades_df['Exit_Time_Str'] = pd.to_datetime(existing_trades_df['Exit Time']).dt.strftime('%Y-%m-%d %H:%M:%S')

    # Convert numeric values to exact types
    new_entry_price = float(new_trade['Entry Price'])
    new_exit_price = float(new_trade['Exit Price'])
    new_quantity = int(new_trade['Quantity'])
    new_account = str(new_trade['Account'])

    matches = existing_trades_df[
        (existing_trades_df['Entry_Time_Str'] == new_entry_time) &
        (existing_trades_df['Exit_Time_Str'] == new_exit_time) &
        (existing_trades_df['Entry Price'].astype(float) == new_entry_price) &
        (existing_trades_df['Exit Price'].astype(float) == new_exit_price) &
        (existing_trades_df['Quantity'].astype(int) == new_quantity) &
        (existing_trades_df['Account'].astype(str) == new_account)
    ]

    if len(matches) > 0:
        print("\n!!! DUPLICATE FOUND !!!")
        print("Matching trade in database:")
        for idx, match in matches.iterrows():
            print(f"Entry Time: {match['Entry_Time_Str']}")
            print(f"Exit Time: {match['Exit_Time_Str']}")
            print(f"Entry Price: {match['Entry Price']}")
            print(f"Exit Price: {match['Exit Price']}")
            print(f"Quantity: {match['Quantity']}")
            print(f"Account: {match['Account']}")
        return True

    print("No duplicate found")
    return False

def process_trades(df, multipliers, existing_trades_df):
    """Process trades from a NinjaTrader DataFrame"""
    print('\nStarting trade processing...')
    print_dataframe_info(df, 'Input')

    # Create an explicit copy
    ninja_trades_df = df.copy()
    
    # Convert Commission to float, removing '$' if present
    ninja_trades_df['Commission'] = ninja_trades_df['Commission'].str.replace('$', '', regex=False).astype(float)

    # Sort by Time
    ninja_trades_df['Time'] = pd.to_datetime(ninja_trades_df['Time'])
    ninja_trades_df = ninja_trades_df.sort_values('Time')

    # Split entries and exits
    entries = ninja_trades_df[ninja_trades_df['E/X'] == 'Entry']
    exits = ninja_trades_df[ninja_trades_df['E/X'] == 'Exit']

    processed_trades = []
    skipped_trades = 0

    print(f'\nProcessing {len(entries)} potential trades...')

    for _, entry in entries.iterrows():
        try:
            # Find matching exit by time and quantity
            matching_exits = exits[
                (exits['Time'] > entry['Time']) & 
                (exits['Quantity'] == entry['Quantity'])
            ]
            
            if len(matching_exits) == 0:
                print(f'No matching exit found for entry at {entry["Time"]} with quantity {entry["Quantity"]}')
                continue
            
            matching_exit = matching_exits.iloc[0]
            
            # Calculate trade details
            if entry['Action'] == 'Buy':
                side = 'Long'
                points_pl = float(matching_exit['Price']) - float(entry['Price'])
            else:
                side = 'Short'
                points_pl = float(entry['Price']) - float(matching_exit['Price'])
            
            multiplier = float(multipliers[entry['Instrument']])
            commission = float(entry['Commission']) + float(matching_exit['Commission'])
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
                'Commission': round(commission, 2),
                'Account': str(entry['Account']),
                'ID': entry['ID']
            }
            
            print(f'\nProcessed trade:')
            print(f'Entry Time: {trade["Entry Time"]}')
            print(f'Exit Time: {trade["Exit Time"]}')
            print(f'Account: {trade["Account"]}')
            print(f'Points: {trade["Result Gain/Loss in Points"]}')
            print(f'P&L: ${trade["Gain/Loss in Dollars"]}')
            
            if not is_duplicate_trade(trade, existing_trades_df):
                processed_trades.append(trade)
                print('Trade added to processing list')
            else:
                skipped_trades += 1
                print('Trade skipped as duplicate')
                
        except Exception as e:
            print(f'Error processing trade: {str(e)}')
            import traceback
            traceback.print_exc()

    print(f'\nProcessing complete:')
    print(f'Processed trades: {len(processed_trades)}')
    print(f'Skipped duplicates: {skipped_trades}')
    
    return processed_trades

def main():
    try:
        print("\nStarting execution processing...")
        create_archive_folder()

        # Load multipliers
        print("\nLoading instrument multipliers...")
        with open('instrument_multipliers.json', 'r') as f:
            multipliers = json.load(f)
        print(f"Loaded multipliers for instruments: {list(multipliers.keys())}")

        # Load existing trades
        existing_trades_df = load_existing_trades()

        # Find files to process
        ninja_files = glob.glob('NinjaTrader*.csv')
        if not ninja_files:
            print("\nNo files to process")
            return True

        print(f"\nFound {len(ninja_files)} files to process: {ninja_files}")
        all_processed_trades = []

        # Process each file
        for ninja_file in ninja_files:
            print(f"\nProcessing {ninja_file}...")
            df = pd.read_csv(ninja_file)
            
            # Process trades
            processed_trades = process_trades(df, multipliers, existing_trades_df)
            if processed_trades:
                all_processed_trades.extend(processed_trades)
            
            # Move to archive
            archive_path = os.path.join('Archive', ninja_file)
            shutil.move(ninja_file, archive_path)
            print(f"Moved {ninja_file} to Archive")

        if len(all_processed_trades) == 0:
            print("\nNo new unique trades to add")
            return True

        # Final duplicate check before saving
        final_trades = []
        print("\nPerforming final duplicate check...")
        
        for trade in all_processed_trades:
            if not is_duplicate_trade(trade, existing_trades_df):
                final_trades.append(trade)

        if len(final_trades) == 0:
            print("\nAll trades were duplicates - nothing to add")
            return True

        # Save to CSV
        new_trades_df = pd.DataFrame(final_trades)
        
        if len(existing_trades_df) > 0:
            combined_df = pd.concat([existing_trades_df, new_trades_df], ignore_index=True)
            combined_df = combined_df.sort_values('Entry Time')
            combined_df.to_csv('TradeLog.csv', index=False)
            print(f"\nAdded {len(final_trades)} new trades to TradeLog.csv")
        else:
            new_trades_df.to_csv('TradeLog.csv', index=False)
            print(f"\nCreated new TradeLog.csv with {len(new_trades_df)} trades")

        return True

    except Exception as e:
        print(f"\nError in main execution: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()