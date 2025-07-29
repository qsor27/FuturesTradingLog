"""
Integration tests for critical application paths
Tests end-to-end workflows and component interactions
"""

import pytest
import sqlite3
import tempfile
import os
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from typing import Dict, List, Any
import io

# Import application components
from app import create_app
from position_service import PositionService
from TradingLog_db import TradingLogDatabase
from data_service import DataService
from config import Config


class TestCriticalPathIntegration:
    """Integration tests for critical application workflows"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield db_path
        os.unlink(db_path)
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory"""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def test_config(self, temp_db, temp_data_dir):
        """Create test configuration"""
        config = Config()
        config.db_path = temp_db
        config.data_dir = temp_data_dir
        config.debug = True
        return config
    
    @pytest.fixture
    def app(self, test_config):
        """Create Flask app for testing"""
        app = create_app(test_config)
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def sample_csv_data(self):
        """Generate sample CSV data for import testing"""
        return """entry_execution_id,instrument,account,side_of_market,quantity,entry_price,exit_price,entry_time,exit_time,commission,dollars_gain_loss,points_gain_loss
exec_001,ES,TestAccount,Buy,1,4000.0,4010.0,2023-01-01 09:00:00,2023-01-01 10:00:00,2.50,500.00,10.0
exec_002,ES,TestAccount,Sell,1,4020.0,4015.0,2023-01-01 11:00:00,2023-01-01 12:00:00,2.50,250.00,5.0
exec_003,NQ,TestAccount,Buy,2,15000.0,15050.0,2023-01-01 13:00:00,2023-01-01 14:00:00,5.00,2000.00,50.0"""
    
    def test_csv_import_to_positions_workflow(self, client, sample_csv_data):
        """Test complete CSV import to positions workflow"""
        # Test CSV upload
        response = client.post('/import/csv', 
                             data={'csv_data': sample_csv_data},
                             content_type='multipart/form-data')
        
        assert response.status_code == 200
        
        # Test position rebuild
        response = client.post('/positions/rebuild')
        assert response.status_code == 200
        
        # Verify positions were created
        response = client.get('/api/positions')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data['positions']) == 3  # 3 completed trades = 3 positions
    
    def test_position_building_and_chart_data_integration(self, client, sample_csv_data):
        """Test integration between position building and chart data"""
        # Import data and build positions
        client.post('/import/csv', 
                   data={'csv_data': sample_csv_data},
                   content_type='multipart/form-data')
        client.post('/positions/rebuild')
        
        # Test chart data retrieval
        response = client.get('/api/chart-data/ES')
        assert response.status_code == 200
        
        # Verify chart data structure
        data = response.get_json()
        assert 'ohlc_data' in data
        assert 'positions' in data
        assert 'timeframe' in data
    
    def test_database_initialization_and_migration(self, test_config):
        """Test database initialization and schema migration"""
        # Test database creation
        with TradingLogDatabase(test_config.db_path) as db:
            # Verify core tables exist
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in db.cursor.fetchall()]
            
            required_tables = ['trades', 'positions', 'position_executions', 'ohlc_data']
            for table in required_tables:
                assert table in tables, f"Required table '{table}' not found"
            
            # Test table structure
            db.cursor.execute("PRAGMA table_info(positions)")
            columns = [row[1] for row in db.cursor.fetchall()]
            
            required_columns = ['id', 'instrument', 'account', 'position_type', 
                              'entry_time', 'exit_time', 'total_quantity']
            for column in required_columns:
                assert column in columns, f"Required column '{column}' not found in positions table"
    
    def test_position_service_database_integration(self, test_config):
        """Test PositionService database integration"""
        with PositionService(test_config.db_path) as ps:
            # Test table creation
            ps.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in ps.cursor.fetchall()]
            assert 'positions' in tables
            assert 'position_executions' in tables
            
            # Test data insertion and retrieval
            sample_trades = [
                {
                    'id': 1,
                    'entry_execution_id': 'exec_001',
                    'instrument': 'ES',
                    'account': 'TestAccount',
                    'side_of_market': 'Buy',
                    'quantity': 1,
                    'entry_price': 4000.0,
                    'exit_price': 4010.0,
                    'entry_time': '2023-01-01 09:00:00',
                    'commission': 2.50,
                    'deleted': 0
                },
                {
                    'id': 2,
                    'entry_execution_id': 'exec_002',
                    'instrument': 'ES',
                    'account': 'TestAccount',
                    'side_of_market': 'Sell',
                    'quantity': 1,
                    'entry_price': 4010.0,
                    'exit_price': 4010.0,
                    'entry_time': '2023-01-01 10:00:00',
                    'commission': 2.50,
                    'deleted': 0
                }
            ]
            
            # Insert test trades
            for trade in sample_trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade['entry_execution_id'],
                    trade['instrument'],
                    trade['account'],
                    trade['side_of_market'],
                    trade['quantity'],
                    trade['entry_price'],
                    trade['exit_price'],
                    trade['entry_time'],
                    trade['commission'],
                    trade['deleted']
                ))
            
            # Test position building
            result = ps.rebuild_positions_from_trades()
            assert result['positions_created'] == 1
            assert result['trades_processed'] == 2
            
            # Test position retrieval
            positions, total_count, total_pages = ps.get_positions()
            assert len(positions) == 1
            assert total_count == 1
            assert total_pages == 1
    
    def test_flask_app_startup_and_health_check(self, client):
        """Test Flask application startup and health check"""
        # Test health endpoint
        response = client.get('/health')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'database' in data
        assert 'version' in data
    
    def test_api_error_handling_integration(self, client):
        """Test API error handling across different endpoints"""
        # Test invalid position ID
        response = client.get('/api/positions/99999')
        assert response.status_code == 404
        
        # Test invalid chart data request
        response = client.get('/api/chart-data/INVALID_INSTRUMENT')
        assert response.status_code in [400, 404]
        
        # Test invalid CSV data
        response = client.post('/import/csv', 
                             data={'csv_data': 'invalid,csv,data'},
                             content_type='multipart/form-data')
        assert response.status_code in [400, 422]
    
    def test_data_service_integration(self, test_config):
        """Test DataService integration with caching and database"""
        with patch('yfinance.download') as mock_yfinance:
            # Mock yfinance response
            mock_data = Mock()
            mock_data.reset_index.return_value = [
                {'Date': datetime(2023, 1, 1), 'Open': 4000.0, 'High': 4010.0, 
                 'Low': 3995.0, 'Close': 4005.0, 'Volume': 1000000}
            ]
            mock_yfinance.return_value = mock_data
            
            # Test data service
            data_service = DataService()
            
            # Test data retrieval
            data = data_service.get_ohlc_data('ES=F', '1d', '1mo')
            assert len(data) > 0
            
            # Test caching (second call should be faster)
            import time
            start_time = time.time()
            data_cached = data_service.get_ohlc_data('ES=F', '1d', '1mo')
            cache_time = time.time() - start_time
            
            assert cache_time < 0.1  # Should be very fast from cache
            assert len(data_cached) == len(data)
    
    def test_configuration_loading_integration(self, temp_data_dir):
        """Test configuration loading and validation"""
        # Create test config files
        config_dir = os.path.join(temp_data_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        # Create instrument multipliers config
        multipliers = {
            'ES': 50.0,
            'NQ': 20.0,
            'YM': 5.0
        }
        
        with open(os.path.join(config_dir, 'instrument_multipliers.json'), 'w') as f:
            json.dump(multipliers, f)
        
        # Test config loading
        config = Config()
        config.data_dir = temp_data_dir
        config.config_dir = config_dir
        
        # Test multiplier loading in position service
        with PositionService() as ps:
            # Mock the config
            ps.data_dir = temp_data_dir
            
            # Test multiplier retrieval
            multiplier = ps._get_instrument_multiplier('ES')
            assert multiplier == 50.0
            
            # Test default multiplier
            multiplier = ps._get_instrument_multiplier('UNKNOWN')
            assert multiplier == 1.0
    
    def test_position_validation_integration(self, client, sample_csv_data):
        """Test position validation system integration"""
        # Import data and build positions
        client.post('/import/csv', 
                   data={'csv_data': sample_csv_data},
                   content_type='multipart/form-data')
        client.post('/positions/rebuild')
        
        # Test validation endpoints
        response = client.get('/api/validation/health')
        assert response.status_code == 200
        
        response = client.get('/api/validation/summary')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'total_positions' in data
        assert 'validation_status' in data
    
    def test_logging_system_integration(self, test_config):
        """Test logging system integration"""
        # Test that logging is properly configured
        import logging
        
        # Test different log levels
        logger = logging.getLogger('position_service')
        logger.info("Integration test log message")
        logger.warning("Integration test warning")
        logger.error("Integration test error")
        
        # Verify log configuration exists
        assert logger.handlers is not None
        assert len(logger.handlers) > 0
    
    def test_concurrent_access_integration(self, client, sample_csv_data):
        """Test concurrent access to critical paths"""
        import threading
        import time
        
        # Import initial data
        client.post('/import/csv', 
                   data={'csv_data': sample_csv_data},
                   content_type='multipart/form-data')
        client.post('/positions/rebuild')
        
        # Test concurrent reads
        results = []
        
        def make_request():
            response = client.get('/api/positions')
            results.append(response.status_code)
        
        # Start multiple concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5
    
    def test_memory_cleanup_integration(self, client, sample_csv_data):
        """Test memory cleanup in critical paths"""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform multiple operations
        for i in range(10):
            client.post('/import/csv', 
                       data={'csv_data': sample_csv_data},
                       content_type='multipart/form-data')
            client.post('/positions/rebuild')
            client.get('/api/positions')
            
            # Force garbage collection
            gc.collect()
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for 10 iterations)
        assert memory_increase < 50, f"Memory leaked: {memory_increase:.1f}MB"
    
    def test_transaction_rollback_integration(self, test_config):
        """Test database transaction rollback integration"""
        with PositionService(test_config.db_path) as ps:
            # Start a transaction
            ps.cursor.execute("BEGIN")
            
            # Insert some data
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_test', 'ES', 'TestAccount', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0))
            
            # Verify data is there (within transaction)
            ps.cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_execution_id = 'exec_test'")
            count = ps.cursor.fetchone()[0]
            assert count == 1
            
            # Rollback transaction
            ps.cursor.execute("ROLLBACK")
            
            # Verify data is gone
            ps.cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_execution_id = 'exec_test'")
            count = ps.cursor.fetchone()[0]
            assert count == 0
    
    def test_full_workflow_integration(self, client, sample_csv_data):
        """Test complete end-to-end workflow"""
        # 1. Import CSV data
        response = client.post('/import/csv', 
                             data={'csv_data': sample_csv_data},
                             content_type='multipart/form-data')
        assert response.status_code == 200
        
        # 2. Build positions
        response = client.post('/positions/rebuild')
        assert response.status_code == 200
        
        # 3. Retrieve positions
        response = client.get('/api/positions')
        assert response.status_code == 200
        positions_data = response.get_json()
        
        # 4. Get position statistics
        response = client.get('/api/positions/statistics')
        assert response.status_code == 200
        stats_data = response.get_json()
        
        # 5. Get chart data
        response = client.get('/api/chart-data/ES')
        assert response.status_code == 200
        chart_data = response.get_json()
        
        # 6. Validate integration
        assert len(positions_data['positions']) == 3
        assert stats_data['total_positions'] == 3
        assert 'positions' in chart_data
        
        # 7. Test validation system
        response = client.get('/api/validation/summary')
        assert response.status_code == 200
        validation_data = response.get_json()
        
        # 8. Verify data consistency
        assert positions_data['total_count'] == stats_data['total_positions']
        assert validation_data['total_positions'] == stats_data['total_positions']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])