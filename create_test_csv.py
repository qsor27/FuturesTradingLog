#!/usr/bin/env python3
"""
Create a test CSV file to test the UnifiedCSVImportService in the running container
"""
import pandas as pd
from datetime import datetime
from pathlib import Path

def create_test_csv():
    """Create a test CSV file in the container's data directory"""
    
    # Use the container's data directory
    data_dir = Path(r"C:\Containers\FuturesTradingLog\data")
    
    # Create a realistic test file with today's timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = data_dir / f"NinjaTrader_Executions_TEST_{timestamp}.csv"
    
    # Create realistic test data
    test_data = {
        'Time': [
            f'{datetime.now().strftime("%m/%d/%Y %H:%M:%S %p")}',
            f'{datetime.now().strftime("%m/%d/%Y %H:%M:%S %p")}',
        ],
        'Instrument': ['ES 12-24', 'ES 12-24'],
        'Market pos.': ['Long', 'Short'],
        'Qty': [1, 1],
        'Price': [5850.25, 5852.75],
        'Account': ['TestAccount', 'TestAccount'],
        'ID': [f'TEST{timestamp}001', f'TEST{timestamp}002'],
        'Commission': [2.25, 2.25],
        'Action': ['Buy', 'Sell'],
        'E/X': ['Entry', 'Exit'],
        'Position': ['Open', 'Close'],
        'Order ID': [f'ORD{timestamp}001', f'ORD{timestamp}002'],
        'Name': ['ES Test Trade', 'ES Test Trade'],
        'Rate': [0.01, 0.01],
        'Connection': ['Test', 'Test']
    }
    
    df = pd.DataFrame(test_data)
    df.to_csv(csv_file, index=False)
    
    print(f"[OK] Created test CSV file: {csv_file.name}")
    print(f"  - File path: {csv_file}")
    print(f"  - File size: {csv_file.stat().st_size} bytes")
    print(f"  - Rows: {len(df)}")
    
    return csv_file

if __name__ == "__main__":
    test_file = create_test_csv()
    print(f"\nTest file created successfully!")
    print(f"The UnifiedCSVImportService should detect this file on its next check.")
    print(f"You can monitor the container logs to see if it gets processed:")
    print(f"  docker logs futurestradinglog-dev --follow")