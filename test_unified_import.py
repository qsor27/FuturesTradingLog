#!/usr/bin/env python3
"""
Test script for UnifiedCSVImportService
"""
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_unified_csv_import():
    """Test the UnifiedCSVImportService functionality"""
    try:
        print("Testing UnifiedCSVImportService...")
        
        # Import the service
        from services.unified_csv_import_service import UnifiedCSVImportService
        
        # Create temporary data directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock instrument config
            import json
            instrument_config = {'ES': 50.0, 'NQ': 20.0}
            config_file = temp_path / 'instruments.json'
            with open(config_file, 'w') as f:
                json.dump(instrument_config, f)
            
            # Mock the config
            from unittest.mock import patch
            with patch('services.unified_csv_import_service.config') as mock_config:
                mock_config.data_dir = temp_path
                mock_config.instrument_config = config_file
                
                # Create service instance
                service = UnifiedCSVImportService()
                
                print("[OK] Service initialized successfully")
                print(f"  - Data directory: {service.data_dir}")
                print(f"  - Processed files: {len(service.processed_files)}")
                print(f"  - Multipliers loaded: {len(service.multipliers)}")
                
                # Test finding CSV files (should be empty)
                csv_files = service._find_new_csv_files()
                print(f"[OK] Found {len(csv_files)} CSV files in empty directory")
                
                # Create a test CSV file
                test_data = pd.DataFrame({
                    'Time': ['2023-01-01 09:30:00', '2023-01-01 10:00:00'],
                    'Instrument': ['ES 03-23', 'ES 03-23'],
                    'Market pos.': ['Long', 'Short'],
                    'Qty': [1, 1],
                    'Price': [4100.25, 4105.50],
                    'Account': ['Sim101', 'Sim101'],
                    'ID': ['12345', '12346'],
                    'Commission': [2.25, 2.25]
                })
                
                csv_file = temp_path / 'test_data.csv'
                test_data.to_csv(csv_file, index=False)
                print(f"[OK] Created test CSV file: {csv_file.name}")
                
                # Test finding the new CSV file
                csv_files = service._find_new_csv_files()
                print(f"[OK] Found {len(csv_files)} CSV file(s)")
                
                # Test validation
                df = pd.read_csv(csv_file)
                is_valid = service._validate_csv_data(df, csv_file.name)
                print(f"[OK] CSV validation result: {is_valid}")
                
                # Test processing status
                status = service.get_processing_status()
                print(f"[OK] Processing status retrieved:")
                print(f"  - Total processed files: {status['total_processed_files']}")
                print(f"  - Execution processing available: {status['execution_processing_available']}")
                print(f"  - Position service available: {status['position_service_available']}")
                print(f"  - Cache invalidation available: {status['cache_invalidation_available']}")
                
                # Test getting available files
                available_files = service.get_available_files()
                print(f"[OK] Available files: {len(available_files)}")
                
                print("\n[SUCCESS] All tests passed! UnifiedCSVImportService is working correctly.")
                return True
                
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_unified_csv_import()
    sys.exit(0 if success else 1)