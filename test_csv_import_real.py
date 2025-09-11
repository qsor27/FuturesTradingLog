#!/usr/bin/env python3
"""
Test real CSV import functionality
"""
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def create_test_csv_file(csv_path: Path):
    """Create a realistic NinjaTrader CSV file for testing"""
    
    # Sample NinjaTrader execution data
    data = {
        'Time': [
            '1/15/2024 9:30:05 AM',
            '1/15/2024 9:31:12 AM',
            '1/15/2024 9:32:45 AM',
            '1/15/2024 9:33:22 AM'
        ],
        'Instrument': ['ES 03-24', 'ES 03-24', 'ES 03-24', 'ES 03-24'],
        'Market pos.': ['Long', 'Long', 'Short', 'Short'],
        'Qty': [1, 1, 2, 2],
        'Price': [4820.25, 4821.50, 4822.75, 4821.00],
        'Account': ['Sim101', 'Sim101', 'Sim101', 'Sim101'],
        'ID': ['E001', 'E002', 'E003', 'E004'],
        'Commission': [2.25, 2.25, 4.50, 4.50]
    }
    
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    print(f"[OK] Created test CSV file with {len(df)} rows")
    return df

def test_real_csv_import():
    """Test real CSV import functionality with mocked dependencies"""
    try:
        print("Testing real CSV import process...")
        
        # Import necessary modules
        from services.unified_csv_import_service import UnifiedCSVImportService
        from unittest.mock import patch, MagicMock
        
        # Create temporary data directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create instrument config
            import json
            instrument_config = {'ES': 50.0, 'NQ': 20.0, 'MES': 5.0}
            config_file = temp_path / 'instruments.json'
            with open(config_file, 'w') as f:
                json.dump(instrument_config, f)
            
            # Create a test CSV file
            csv_file = temp_path / 'NinjaTrader_Executions_20240115.csv'
            test_df = create_test_csv_file(csv_file)
            
            # Mock the config and dependencies
            with patch('services.unified_csv_import_service.config') as mock_config, \
                 patch('services.unified_csv_import_service.process_trades') as mock_process_trades, \
                 patch('services.unified_csv_import_service.FuturesDB') as mock_db_class:
                
                # Setup config mock
                mock_config.data_dir = temp_path
                mock_config.instrument_config = config_file
                
                # Setup process_trades mock to return realistic trade data
                mock_processed_trades = [
                    {
                        'Instrument': 'ES 03-24',
                        'Side of Market': 'Long',
                        'Quantity': 1,
                        'Entry Price': 4820.25,
                        'Entry Time': '2024-01-15 09:30:05',
                        'Exit Time': '2024-01-15 09:31:12',
                        'Exit Price': 4821.50,
                        'Result Gain/Loss in Points': 1.25,
                        'Gain/Loss in Dollars': 62.50,
                        'ID': 'TRADE001',
                        'Commission': 2.25,
                        'Account': 'Sim101'
                    },
                    {
                        'Instrument': 'ES 03-24',
                        'Side of Market': 'Short',
                        'Quantity': 2,
                        'Entry Price': 4822.75,
                        'Entry Time': '2024-01-15 09:32:45',
                        'Exit Time': '2024-01-15 09:33:22',
                        'Exit Price': 4821.00,
                        'Result Gain/Loss in Points': 3.50,
                        'Gain/Loss in Dollars': 350.00,
                        'ID': 'TRADE002',
                        'Commission': 4.50,
                        'Account': 'Sim101'
                    }
                ]
                mock_process_trades.return_value = mock_processed_trades
                
                # Setup database mock
                mock_db_instance = MagicMock()
                mock_db_class.return_value.__enter__.return_value = mock_db_instance
                mock_db_instance.add_trade.return_value = True
                
                # Create service instance
                service = UnifiedCSVImportService()
                print(f"[OK] Service initialized with data dir: {service.data_dir}")
                
                # Test file detection
                csv_files = service._find_new_csv_files()
                print(f"[OK] Found {len(csv_files)} CSV files to process")
                assert len(csv_files) == 1, f"Expected 1 file, found {len(csv_files)}"
                
                # Test file processing
                trades = service._process_csv_file(csv_files[0])
                print(f"[OK] Processed {len(trades)} trades from CSV file")
                assert len(trades) == 2, f"Expected 2 trades, got {len(trades)}"
                
                # Test trade import to database
                import_success = service._import_trades_to_database(trades)
                print(f"[OK] Trade import to database: {import_success}")
                assert import_success, "Trade import should succeed"
                
                # Verify database calls
                assert mock_db_instance.add_trade.call_count == 2, f"Expected 2 add_trade calls, got {mock_db_instance.add_trade.call_count}"
                print(f"[OK] Database received {mock_db_instance.add_trade.call_count} trade inserts")
                
                # Test full processing workflow
                result = service.process_all_new_files()
                print(f"[OK] Full processing result: {result['success']}")
                print(f"  - Files processed: {result['files_processed']}")
                print(f"  - Trades imported: {result['trades_imported']}")
                
                assert result['success'], "Full processing should succeed"
                assert result['files_processed'] == 1, "Should process 1 file"
                assert result['trades_imported'] == 2, "Should import 2 trades"
                
                # Verify file was marked as processed
                assert csv_files[0].name in service.processed_files, "File should be marked as processed"
                print(f"[OK] File marked as processed: {csv_files[0].name}")
                
                # Test that the same file won't be processed again
                csv_files_after = service._find_new_csv_files()
                print(f"[OK] Found {len(csv_files_after)} new files after processing (should be 0)")
                assert len(csv_files_after) == 0, "Already processed files should not be found again"
                
                print("\n[SUCCESS] Real CSV import test passed!")
                print("The UnifiedCSVImportService successfully:")
                print("  - Detected new CSV files")
                print("  - Processed and validated CSV data")
                print("  - Converted trades using ExecutionProcessing")
                print("  - Imported trades to database")
                print("  - Marked files as processed")
                print("  - Avoided reprocessing already handled files")
                
                return True
                
    except Exception as e:
        print(f"[ERROR] Real CSV import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_real_csv_import()
    sys.exit(0 if success else 1)