"""
Test suite for UnifiedCSVImportService
"""
import pytest
import tempfile
import shutil
import os
import time
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from services.unified_csv_import_service import UnifiedCSVImportService
from scripts.TradingLog_db import FuturesDB


class TestUnifiedCSVImportService:
    """Test cases for UnifiedCSVImportService"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for testing"""
        return {
            'valid_ninja_trader': pd.DataFrame({
                'ID': ['12345', '12346'],
                'Account': ['Sim101', 'Sim101'],
                'Instrument': ['ES 03-23', 'ES 03-23'],
                'Time': ['2023-01-01 09:30:00', '2023-01-01 10:00:00'],
                'Action': ['Buy', 'Sell'],
                'E/X': ['Entry', 'Exit'],
                'Quantity': [1, 1],
                'Price': [4100.25, 4105.50],
                'Commission': ['$2.25', '$2.25']
            }),
            'empty_csv': pd.DataFrame(),
            'invalid_columns': pd.DataFrame({
                'wrong_col1': ['val1'],
                'wrong_col2': ['val2']
            })
        }
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing"""
        with patch('services.unified_csv_import_service.FuturesDB') as mock_db_class:
            mock_db_instance = Mock()
            mock_db_class.return_value.__enter__.return_value = mock_db_instance
            mock_db_instance.add_trade.return_value = True
            yield mock_db_instance
    
    @pytest.fixture
    def mock_position_service(self):
        """Mock position service for testing"""
        with patch('services.unified_csv_import_service.EnhancedPositionServiceV2') as mock_ps:
            mock_instance = Mock()
            mock_ps.return_value.__enter__.return_value = mock_instance
            mock_instance.rebuild_positions_from_trades.return_value = {
                'positions_created': 2,
                'trades_processed': 4
            }
            yield mock_instance
    
    @pytest.fixture
    def service(self, temp_data_dir):
        """Create service instance with temp directory"""
        with patch('services.unified_csv_import_service.config') as mock_config:
            mock_config.data_dir = temp_data_dir
            mock_config.instrument_config = temp_data_dir / 'instruments.json'
            
            # Create mock instrument config
            instrument_config = {'ES': 50.0, 'NQ': 20.0}
            with open(mock_config.instrument_config, 'w') as f:
                import json
                json.dump(instrument_config, f)
            
            service = UnifiedCSVImportService()
            return service
    
    def test_service_initialization(self, service, temp_data_dir):
        """Test service initializes correctly"""
        assert service.data_dir == temp_data_dir
        assert service.processed_files == set()
        assert service.multipliers == {'ES': 50.0, 'NQ': 20.0}
    
    def test_initialization_missing_config(self, temp_data_dir):
        """Test service handles missing instrument config gracefully"""
        with patch('services.unified_csv_import_service.config') as mock_config:
            mock_config.data_dir = temp_data_dir
            mock_config.instrument_config = temp_data_dir / 'missing.json'
            
            service = UnifiedCSVImportService()
            assert service.multipliers == {}
    
    def test_find_new_csv_files_empty_directory(self, service):
        """Test finding files in empty directory"""
        files = service._find_new_csv_files()
        assert files == []
    
    def test_find_new_csv_files_with_files(self, service, temp_data_dir):
        """Test finding CSV files in directory"""
        # Create test files
        csv_file1 = temp_data_dir / 'test_data_2023-01-01.csv'
        csv_file2 = temp_data_dir / 'another_file.csv'
        txt_file = temp_data_dir / 'not_csv.txt'
        old_file = temp_data_dir / 'old_data.csv'
        
        csv_file1.touch()
        csv_file2.touch()
        txt_file.touch()
        old_file.touch()
        
        # Make old_file actually old (more than 24 hours)
        old_time = time.time() - 86500  # 24+ hours ago
        os.utime(old_file, (old_time, old_time))
        
        files = service._find_new_csv_files()
        
        # Should find only recent CSV files
        assert len(files) == 2
        file_names = [f.name for f in files]
        assert 'test_data_2023-01-01.csv' in file_names
        assert 'another_file.csv' in file_names
        assert 'not_csv.txt' not in file_names
        assert 'old_data.csv' not in file_names
    
    def test_find_new_csv_files_excludes_processed(self, service, temp_data_dir):
        """Test that processed files are excluded"""
        csv_file = temp_data_dir / 'test.csv'
        csv_file.touch()
        
        # Mark file as processed
        service.processed_files.add('test.csv')
        
        files = service._find_new_csv_files()
        assert files == []
    
    def test_validate_csv_data_valid(self, service, sample_csv_data):
        """Test validation of valid CSV data"""
        df = sample_csv_data['valid_ninja_trader']
        result = service._validate_csv_data(df, 'test.csv')
        assert result is True
    
    def test_validate_csv_data_empty(self, service, sample_csv_data):
        """Test validation of empty CSV"""
        df = sample_csv_data['empty_csv']
        result = service._validate_csv_data(df, 'test.csv')
        assert result is False
    
    def test_validate_csv_data_missing_columns(self, service, sample_csv_data):
        """Test validation of CSV with wrong columns"""
        df = sample_csv_data['invalid_columns']
        result = service._validate_csv_data(df, 'test.csv')
        assert result is False
    
    @patch('services.unified_csv_import_service.process_trades')
    def test_process_csv_file_success(self, mock_process_trades, service, sample_csv_data, temp_data_dir):
        """Test successful CSV file processing with new individual execution format"""
        # Setup
        csv_file = temp_data_dir / 'test.csv'
        sample_csv_data['valid_ninja_trader'].to_csv(csv_file, index=False)

        # Mock returns 2 individual executions (Entry and Exit)
        mock_process_trades.return_value = [
            {
                'execution_id': '12345',
                'Account': 'Sim101',
                'Instrument': 'ES 03-23',
                'action': 'Buy',
                'entry_exit': 'Entry',
                'quantity': 1,
                'entry_price': 4100.25,
                'entry_time': pd.to_datetime('2023-01-01 09:30:00'),
                'exit_price': None,
                'exit_time': None,
                'commission': 2.25
            },
            {
                'execution_id': '12346',
                'Account': 'Sim101',
                'Instrument': 'ES 03-23',
                'action': 'Sell',
                'entry_exit': 'Exit',
                'quantity': 1,
                'entry_price': None,
                'entry_time': None,
                'exit_price': 4105.50,
                'exit_time': pd.to_datetime('2023-01-01 10:00:00'),
                'commission': 2.25
            }
        ]

        # Execute
        result = service._process_csv_file(csv_file)

        # Verify - should return 2 individual executions
        assert len(result) == 2
        assert result[0]['Instrument'] == 'ES 03-23'
        assert result[0]['execution_id'] == '12345'
        assert result[1]['execution_id'] == '12346'
        mock_process_trades.assert_called_once()
    
    def test_process_csv_file_not_found(self, service, temp_data_dir):
        """Test processing non-existent file"""
        csv_file = temp_data_dir / 'missing.csv'
        result = service._process_csv_file(csv_file)
        assert result == []
    
    def test_process_csv_file_invalid_data(self, service, sample_csv_data, temp_data_dir):
        """Test processing file with invalid data"""
        csv_file = temp_data_dir / 'invalid.csv'
        sample_csv_data['invalid_columns'].to_csv(csv_file, index=False)
        
        result = service._process_csv_file(csv_file)
        assert result == []
    
    def test_import_trades_to_database_success(self, service, mock_db):
        """Test successful trade import to database"""
        trades = [
            {
                'Instrument': 'ES 03-23',
                'Side of Market': 'Long',
                'Quantity': 1,
                'Entry Price': 4100.25,
                'Entry Time': '2023-01-01 09:30:00',
                'Exit Time': '2023-01-01 10:00:00',
                'Exit Price': 4105.50,
                'Result Gain/Loss in Points': 5.25,
                'Gain/Loss in Dollars': 262.50,
                'ID': '12345',
                'Commission': 2.25,
                'Account': 'Sim101'
            }
        ]
        
        result = service._import_trades_to_database(trades)
        
        assert result is True
        mock_db.add_trade.assert_called_once()
        
        # Verify correct data format passed to database
        call_args = mock_db.add_trade.call_args[0][0]
        assert call_args['instrument'] == 'ES 03-23'
        assert call_args['side_of_market'] == 'Long'
        assert call_args['quantity'] == 1
        assert call_args['entry_execution_id'] == '12345'
    
    def test_import_trades_to_database_empty_list(self, service):
        """Test importing empty trade list"""
        result = service._import_trades_to_database([])
        assert result is True
    
    def test_import_trades_to_database_failure(self, service):
        """Test database import failure handling"""
        trades = [{'test': 'data'}]
        
        with patch('services.unified_csv_import_service.FuturesDB') as mock_db_class:
            mock_db_class.return_value.__enter__.side_effect = Exception("DB Error")
            
            result = service._import_trades_to_database(trades)
            assert result is False
    
    def test_rebuild_positions_success(self, service, mock_db, mock_position_service):
        """Test successful position rebuilding"""
        result = service._rebuild_positions(mock_db)
        
        assert result['positions_created'] == 2
        assert result['trades_processed'] == 4
        mock_position_service.rebuild_positions_from_trades.assert_called_once()
    
    def test_rebuild_positions_failure(self, service, mock_db):
        """Test position rebuilding failure handling"""
        with patch('services.unified_csv_import_service.EnhancedPositionServiceV2') as mock_ps:
            mock_ps.side_effect = Exception("Position Error")
            
            result = service._rebuild_positions(mock_db)
            assert result == {'positions_created': 0, 'trades_processed': 0}
    
    def test_archive_file_success(self, service, temp_data_dir):
        """Test successful file archiving"""
        # Create test file (old enough to archive)
        test_file = temp_data_dir / 'test.csv'
        test_file.write_text('test,data\n1,2')
        
        # Make file old enough to archive
        old_time = time.time() - 86500  # 24+ hours ago
        os.utime(test_file, (old_time, old_time))
        
        service._archive_file(test_file)
        
        # Verify file was moved to archive
        archive_dir = temp_data_dir / 'archive'
        archived_file = archive_dir / 'test.csv'
        
        assert not test_file.exists()
        assert archived_file.exists()
        assert archived_file.read_text() == 'test,data\n1,2'
    
    def test_archive_file_recent(self, service, temp_data_dir):
        """Test that recent files are not archived"""
        test_file = temp_data_dir / 'recent.csv'
        test_file.write_text('test,data')
        
        service._archive_file(test_file)
        
        # File should still exist (not archived)
        assert test_file.exists()
    
    def test_archive_file_duplicate_names(self, service, temp_data_dir):
        """Test archiving when file with same name already exists"""
        # Create archive directory with existing file
        archive_dir = temp_data_dir / 'archive'
        archive_dir.mkdir()
        existing_file = archive_dir / 'test.csv'
        existing_file.write_text('existing')
        
        # Create test file to archive (old enough)
        test_file = temp_data_dir / 'test.csv'
        test_file.write_text('new,data')
        old_time = time.time() - 86500
        os.utime(test_file, (old_time, old_time))
        
        service._archive_file(test_file)
        
        # Should create numbered version
        assert not test_file.exists()
        assert existing_file.exists()
        assert existing_file.read_text() == 'existing'
        
        numbered_file = archive_dir / 'test_1.csv'
        assert numbered_file.exists()
        assert numbered_file.read_text() == 'new,data'
    
    def test_process_all_new_files_success(self, service, mock_db, mock_position_service, temp_data_dir, sample_csv_data):
        """Test processing all new files successfully"""
        # Create test CSV file
        csv_file = temp_data_dir / 'test.csv'
        sample_csv_data['valid_ninja_trader'].to_csv(csv_file, index=False)
        
        with patch.object(service, '_process_csv_file') as mock_process:
            mock_process.return_value = [{'test': 'trade'}]
            
            result = service.process_all_new_files()
            
            assert result['success'] is True
            assert result['files_processed'] == 1
            assert result['trades_imported'] == 1
            assert 'test.csv' in service.processed_files
    
    def test_process_all_new_files_no_files(self, service):
        """Test processing when no new files exist"""
        result = service.process_all_new_files()
        
        assert result['success'] is True
        assert result['files_processed'] == 0
        assert result['trades_imported'] == 0
    
    def test_process_all_new_files_import_failure(self, service, temp_data_dir, sample_csv_data):
        """Test handling of import failures"""
        csv_file = temp_data_dir / 'test.csv'
        sample_csv_data['valid_ninja_trader'].to_csv(csv_file, index=False)
        
        with patch.object(service, '_process_csv_file') as mock_process, \
             patch.object(service, '_import_trades_to_database') as mock_import:
            
            mock_process.return_value = [{'test': 'trade'}]
            mock_import.return_value = False  # Simulate import failure
            
            result = service.process_all_new_files()
            
            assert result['success'] is False
            assert result['error'] == 'Failed to import trades to database'
    
    def test_manual_reprocess_file_success(self, service, mock_db, mock_position_service, temp_data_dir, sample_csv_data):
        """Test manual reprocessing of specific file"""
        csv_file = temp_data_dir / 'manual.csv'
        sample_csv_data['valid_ninja_trader'].to_csv(csv_file, index=False)
        
        with patch.object(service, '_process_csv_file') as mock_process:
            mock_process.return_value = [{'test': 'trade'}]
            
            result = service.manual_reprocess_file(csv_file)
            
            assert result['success'] is True
            assert result['trades_imported'] == 1
            assert 'manual.csv' in service.processed_files
    
    def test_manual_reprocess_file_not_found(self, service, temp_data_dir):
        """Test manual reprocessing of non-existent file"""
        missing_file = temp_data_dir / 'missing.csv'
        
        result = service.manual_reprocess_file(missing_file)
        
        assert result['success'] is False
        assert 'not found' in result['error'].lower()
    
    def test_manual_reprocess_file_no_trades(self, service, temp_data_dir, sample_csv_data):
        """Test manual reprocessing when no trades are found"""
        csv_file = temp_data_dir / 'empty.csv'
        sample_csv_data['empty_csv'].to_csv(csv_file, index=False)
        
        result = service.manual_reprocess_file(csv_file)
        
        assert result['success'] is True
        assert result['trades_imported'] == 0
    
    def test_get_processing_status(self, service):
        """Test getting processing status"""
        service.processed_files.add('file1.csv')
        service.processed_files.add('file2.csv')
        
        status = service.get_processing_status()
        
        assert status['total_processed_files'] == 2
        assert 'file1.csv' in status['processed_files']
        assert 'file2.csv' in status['processed_files']
        assert isinstance(status['last_check'], str)
    
    def test_reset_processed_files(self, service):
        """Test resetting processed files list"""
        service.processed_files.add('file1.csv')
        service.processed_files.add('file2.csv')
        
        service.reset_processed_files()
        
        assert len(service.processed_files) == 0
    
    def test_is_file_processed(self, service):
        """Test checking if file is processed"""
        service.processed_files.add('processed.csv')
        
        assert service.is_file_processed('processed.csv') is True
        assert service.is_file_processed('unprocessed.csv') is False
    
    def test_get_available_files(self, service, temp_data_dir):
        """Test getting list of available CSV files"""
        # Create test files
        csv1 = temp_data_dir / 'file1.csv'
        csv2 = temp_data_dir / 'file2.csv'
        txt_file = temp_data_dir / 'file.txt'
        
        csv1.touch()
        csv2.touch()
        txt_file.touch()
        
        files = service.get_available_files()
        
        assert len(files) == 2
        file_names = [f.name for f in files]
        assert 'file1.csv' in file_names
        assert 'file2.csv' in file_names
        assert 'file.txt' not in file_names


class TestUnifiedCSVImportServiceIntegration:
    """Integration tests for UnifiedCSVImportService"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for integration testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def integration_service(self, temp_data_dir):
        """Create service for integration testing"""
        with patch('services.unified_csv_import_service.config') as mock_config:
            mock_config.data_dir = temp_data_dir
            mock_config.instrument_config = temp_data_dir / 'instruments.json'
            
            # Create real instrument config
            instrument_config = {'ES': 50.0, 'NQ': 20.0}
            with open(mock_config.instrument_config, 'w') as f:
                import json
                json.dump(instrument_config, f)
            
            service = UnifiedCSVImportService()
            return service
    
    def test_end_to_end_file_processing(self, integration_service, temp_data_dir):
        """Test complete end-to-end file processing workflow with new execution format"""
        # Create realistic NinjaTrader CSV file with new format (Action and E/X)
        csv_data = pd.DataFrame({
            'ID': ['12345', '12346'],
            'Account': ['Sim101', 'Sim101'],
            'Instrument': ['ES 03-23', 'ES 03-23'],
            'Time': ['1/1/2023 9:30:00 AM', '1/1/2023 10:00:00 AM'],
            'Action': ['Buy', 'Sell'],
            'E/X': ['Entry', 'Exit'],
            'Quantity': [1, 1],
            'Price': [4100.25, 4105.50],
            'Commission': ['$2.25', '$2.25']
        })
        
        csv_file = temp_data_dir / 'NinjaTrader_Executions_20230101.csv'
        csv_data.to_csv(csv_file, index=False)
        
        # Mock dependencies for integration test
        with patch('services.unified_csv_import_service.process_trades') as mock_process, \
             patch('services.unified_csv_import_service.FuturesDB') as mock_db_class, \
             patch('services.unified_csv_import_service.EnhancedPositionServiceV2') as mock_ps:
            
            # Setup mocks - return individual executions (new format)
            mock_process.return_value = [
                {
                    'execution_id': '12345',
                    'Account': 'Sim101',
                    'Instrument': 'ES 03-23',
                    'action': 'Buy',
                    'entry_exit': 'Entry',
                    'quantity': 1,
                    'entry_price': 4100.25,
                    'entry_time': pd.to_datetime('2023-01-01 09:30:00'),
                    'exit_price': None,
                    'exit_time': None,
                    'commission': 2.25
                },
                {
                    'execution_id': '12346',
                    'Account': 'Sim101',
                    'Instrument': 'ES 03-23',
                    'action': 'Sell',
                    'entry_exit': 'Exit',
                    'quantity': 1,
                    'entry_price': None,
                    'entry_time': None,
                    'exit_price': 4105.50,
                    'exit_time': pd.to_datetime('2023-01-01 10:00:00'),
                    'commission': 2.25
                }
            ]
            
            mock_db_instance = Mock()
            mock_db_class.return_value.__enter__.return_value = mock_db_instance
            mock_db_instance.add_trade.return_value = True
            
            mock_ps_instance = Mock()
            mock_ps.return_value.__enter__.return_value = mock_ps_instance
            mock_ps_instance.rebuild_positions_from_trades.return_value = {
                'positions_created': 1,
                'trades_processed': 1
            }
            
            # Execute the workflow
            result = integration_service.process_all_new_files()
            
            # Verify results - now expects 2 executions imported instead of 1 trade
            assert result['success'] is True
            assert result['files_processed'] == 1
            assert result['trades_imported'] == 2  # 2 individual executions
            assert result['positions_created'] == 1

            # Verify file was processed and archived
            assert 'NinjaTrader_Executions_20230101.csv' in integration_service.processed_files

            # Verify database interactions - should be called twice (once per execution)
            assert mock_db_instance.add_trade.call_count == 2
            mock_ps_instance.rebuild_positions_from_trades.assert_called_once()