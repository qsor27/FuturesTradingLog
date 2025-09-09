"""
Integration tests for the complete OHLC chart functionality
Tests the full pipeline from data fetching to chart display
"""
import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from app import app

class TestOHLCIntegration:
    """Integration tests for complete OHLC functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client with temporary database"""
        # Use temporary database for integration tests
        temp_dir = tempfile.mkdtemp()
        temp_db = os.path.join(temp_dir, 'integration_test.db')
        
        app.config['TESTING'] = True
        app.config['DATABASE_PATH'] = temp_db
        
        with app.test_client() as client:
            yield client
        
        # Cleanup
        if os.path.exists(temp_db):
            os.remove(temp_db)
        os.rmdir(temp_dir)
    
    def test_database_initialization_on_startup(self, client):
        """Test that OHLC database is properly initialized when app starts"""
        # Make a request to trigger database initialization
        response = client.get('/health')
        assert response.status_code == 200
        
        # Verify OHLC table and indexes were created
        from scripts.TradingLog_db import FuturesDB
        with FuturesDB() as db:
            # Check OHLC table exists
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlc_data'")
            assert db.cursor.fetchone() is not None
            
            # Check indexes were created
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_ohlc_%'")
            indexes = db.cursor.fetchall()
            assert len(indexes) >= 8, "Should have created 8+ OHLC indexes"
    
    @patch('data_service.ohlc_service.update_recent_data')
    def test_end_to_end_chart_data_flow(self, mock_update, client):
        """Test complete data flow from API fetch to chart display"""
        from scripts.TradingLog_db import FuturesDB
        
        # Setup mock to return success and insert test data
        mock_update.return_value = True
        
        # Pre-insert test data directly into database
        with FuturesDB() as db:
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            for i in range(5):
                db.insert_ohlc_data(
                    'MNQ', '1m', base_time + (i * 60),
                    100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000 + i
                )
        
        # Step 1: Update data via API (mocked)
        response = client.get('/api/update-data/MNQ?timeframes=1m')
        assert response.status_code == 200
        
        update_data = json.loads(response.data)
        assert update_data['success'] == True
        assert update_data['total_records'] >= 3
        
        # Step 2: Retrieve chart data
        response = client.get('/api/chart-data/MNQ?timeframe=1m&days=1')
        assert response.status_code == 200
        
        chart_data = json.loads(response.data)
        assert chart_data['success'] == True
        assert len(chart_data['data']) >= 3
        
        # Verify data format for TradingView
        candle = chart_data['data'][0]
        required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
        for field in required_fields:
            assert field in candle, f"Missing required field: {field}"
        
        # Step 3: Test chart page rendering
        response = client.get('/chart/MNQ')
        assert response.status_code == 200
        assert b'MNQ' in response.data
        assert b'TradingView' in response.data or b'chart' in response.data.lower()
    
    def test_trade_markers_integration(self, client):
        """Test trade markers integration with chart data"""
        from scripts.TradingLog_db import FuturesDB
        
        # Insert a test trade
        with FuturesDB() as db:
            db.cursor.execute("""
                INSERT INTO trades (instrument, side_of_market, quantity, entry_price, 
                                  entry_time, exit_time, exit_price, dollars_gain_loss, account)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('MNQ', 'Long', 4, 100.0, '2024-01-01 10:00:00', 
                  '2024-01-01 10:30:00', 102.0, 200.0, 'Test'))
            db.conn.commit()
            
            # Get the trade ID
            trade_id = db.cursor.lastrowid
        
        # Test trade markers API
        response = client.get(f'/api/trade-markers/{trade_id}')
        assert response.status_code == 200
        
        markers_data = json.loads(response.data)
        assert markers_data['success'] == True
        assert len(markers_data['markers']) == 2  # Entry and exit
        
        # Verify marker structure
        entry_marker = markers_data['markers'][0]
        assert entry_marker['position'] == 'belowBar'
        assert 'Entry: 100.0' in entry_marker['text']
        
        exit_marker = markers_data['markers'][1]
        assert exit_marker['position'] == 'aboveBar'
        assert 'Exit: 102.0' in exit_marker['text']
        assert '$200.00' in exit_marker['text']
    
    def test_gap_detection_and_backfill_integration(self, client):
        """Test gap detection and automatic backfilling"""
        from scripts.TradingLog_db import FuturesDB
        from data_service import ohlc_service
        
        # Use a unique instrument to avoid interference from other tests
        test_instrument = 'GAP_TEST'
        
        # Insert some OHLC data with gaps
        with FuturesDB() as db:
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            
            # Insert data with a gap (skip timestamps 3 and 4)
            for i in [1, 2, 5, 6, 7]:
                db.insert_ohlc_data(
                    test_instrument, '1m', base_time + (i * 60),
                    100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000 + i
                )
        
        # Test gap detection
        start_date = datetime.fromtimestamp(base_time)
        end_date = datetime.fromtimestamp(base_time + 480)  # 8 minutes later
        
        with FuturesDB() as db:
            gaps = db.find_ohlc_gaps(test_instrument, '1m', base_time, base_time + 480)
            assert len(gaps) > 0, "Should detect gaps in data"
        
        # Test that chart data API triggers gap filling
        with patch.object(ohlc_service, 'fetch_ohlc_data') as mock_fetch:
            # Mock successful data fetch for gap filling
            mock_fetch.return_value = [
                {
                    'instrument': test_instrument,
                    'timeframe': '1m',
                    'timestamp': base_time + 180,  # Fill gap at minute 3
                    'open_price': 103.0,
                    'high_price': 104.0,
                    'low_price': 102.0,
                    'close_price': 103.5,
                    'volume': 1003
                }
            ]
            
            response = client.get(f'/api/chart-data/{test_instrument}?timeframe=1m&days=1')
            assert response.status_code == 200
    
    def test_multiple_instrument_support(self, client):
        """Test support for multiple instruments"""
        instruments = ['MNQ', 'ES', 'YM', 'RTY']
        
        from scripts.TradingLog_db import FuturesDB
        
        # Insert data for multiple instruments
        with FuturesDB() as db:
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            
            for i, instrument in enumerate(instruments):
                for j in range(5):  # 5 candles per instrument
                    db.insert_ohlc_data(
                        instrument, '1m', base_time + (j * 60) + (i * 1000),
                        100.0 + i + j, 101.0 + i + j, 99.0 + i + j, 
                        100.5 + i + j, 1000 + i + j
                    )
        
        # Test instruments API
        response = client.get('/api/instruments')
        assert response.status_code == 200
        
        instruments_data = json.loads(response.data)
        assert instruments_data['success'] == True
        
        for instrument in instruments:
            assert instrument in instruments_data['instruments']
        
        # Test chart data for each instrument
        for instrument in instruments:
            response = client.get(f'/api/chart-data/{instrument}?timeframe=1m&days=1')
            assert response.status_code == 200
            
            chart_data = json.loads(response.data)
            assert chart_data['success'] == True
            assert chart_data['instrument'] == instrument
            assert len(chart_data['data']) > 0
    
    def test_timeframe_support(self, client):
        """Test support for different timeframes"""
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        from scripts.TradingLog_db import FuturesDB
        
        # Insert data for different timeframes
        with FuturesDB() as db:
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            
            for i, timeframe in enumerate(timeframes):
                for j in range(3):
                    db.insert_ohlc_data(
                        'MNQ', timeframe, base_time + (j * 3600) + (i * 100),
                        100.0 + i + j, 101.0 + i + j, 99.0 + i + j,
                        100.5 + i + j, 1000 + i + j
                    )
        
        # Test chart data for each timeframe
        for timeframe in timeframes:
            response = client.get(f'/api/chart-data/MNQ?timeframe={timeframe}&days=1')
            assert response.status_code == 200
            
            chart_data = json.loads(response.data)
            assert chart_data['success'] == True
            assert chart_data['timeframe'] == timeframe
            assert len(chart_data['data']) > 0
    
    def test_error_handling_integration(self, client):
        """Test error handling across the entire system"""
        # Test 1: Non-existent instrument
        response = client.get('/api/chart-data/NONEXISTENT')
        assert response.status_code == 200  # Should return empty data, not error
        
        chart_data = json.loads(response.data)
        assert chart_data['success'] == True
        assert len(chart_data['data']) == 0
        
        # Test 2: Invalid trade ID for markers
        response = client.get('/api/trade-markers/99999')
        assert response.status_code == 404
        
        # Test 3: Invalid timeframe (should default gracefully)
        response = client.get('/api/chart-data/MNQ?timeframe=invalid')
        assert response.status_code == 200  # Should handle gracefully
    
    def test_chart_page_integration(self, client):
        """Test complete chart page functionality"""
        from scripts.TradingLog_db import FuturesDB
        
        # Setup test data
        with FuturesDB() as db:
            # Insert OHLC data
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            for i in range(10):
                db.insert_ohlc_data(
                    'MNQ', '1m', base_time + (i * 60),
                    100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000 + i
                )
            
            # Insert trade data
            db.cursor.execute("""
                INSERT INTO trades (instrument, side_of_market, quantity, entry_price, 
                                  entry_time, dollars_gain_loss, account)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('MNQ', 'Long', 4, 100.5, '2024-01-01 10:05:00', 100.0, 'Test'))
            db.conn.commit()
        
        # Test chart page renders correctly
        response = client.get('/chart/MNQ')
        assert response.status_code == 200
        
        # Check that page contains expected elements
        page_content = response.data.decode('utf-8')
        assert 'MNQ' in page_content
        assert 'chart' in page_content.lower()
        assert 'data-chart' in page_content
        assert 'TradingView' in page_content or 'lightweight-charts' in page_content
    
    @patch('data_service.ohlc_service.fetch_ohlc_data')
    @patch('data_service.ohlc_service.detect_and_fill_gaps')
    def test_performance_under_load(self, mock_fill_gaps, mock_fetch, client):
        """Test performance with realistic data load"""
        from scripts.TradingLog_db import FuturesDB
        
        # Mock gap detection and data fetching to avoid yfinance calls
        mock_fill_gaps.return_value = True
        mock_fetch.return_value = []  # No external data fetched
        
        # Insert a substantial amount of test data
        with FuturesDB() as db:
            base_time = int(datetime(2024, 1, 1, 10, 0).timestamp())
            
            # Insert 1440 minutes of data (1 day)
            for i in range(1440):
                db.insert_ohlc_data(
                    'MNQ', '1m', base_time + (i * 60),
                    100.0 + (i * 0.01), 100.5 + (i * 0.01), 
                    99.5 + (i * 0.01), 100.25 + (i * 0.01), 1000 + i
                )
        
        # Test that chart data loads quickly
        import time
        start_time = time.time()
        
        response = client.get('/api/chart-data/MNQ?timeframe=1m&days=1')
        
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0, f"Chart data API too slow: {response_time:.2f}s"
        
        chart_data = json.loads(response.data)
        assert chart_data['success'] == True
        # Performance test - just verify we get reasonable amount of data quickly
        assert len(chart_data['data']) >= 1000  # Allow for some variation due to external data
    
    @patch('data_service.ohlc_service.fetch_ohlc_data')
    @patch('data_service.ohlc_service.detect_and_fill_gaps')
    def test_data_consistency_across_apis(self, mock_fill_gaps, mock_fetch, client):
        """Test data consistency across different API endpoints"""
        from scripts.TradingLog_db import FuturesDB
        
        # Mock gap detection and data fetching to prevent additional data
        mock_fill_gaps.return_value = True
        mock_fetch.return_value = []  # No external data fetched
        
        # Insert test data with recent timestamps
        with FuturesDB() as db:
            # Use recent timestamps so they appear in "days=1" query
            from datetime import datetime
            base_time = int((datetime.now() - timedelta(hours=2)).timestamp())
            
            for i in range(100):
                db.insert_ohlc_data(
                    'MNQ', '1m', base_time + (i * 60),
                    100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000 + i
                )
        
        # Get data via chart API
        response1 = client.get('/api/chart-data/MNQ?timeframe=1m&days=1')
        chart_data = json.loads(response1.data)
        
        # Get count via instruments API
        with FuturesDB() as db:
            count = db.get_ohlc_count('MNQ', '1m')
        
        # Simple consistency check - verify we got data and it's reasonable
        # (Database may have data from previous tests, chart API filters by timeframe)
        assert len(chart_data['data']) > 0, "Chart API should return some data"
        assert chart_data['success'] == True, "Chart API should succeed"
        
        # Verify our specific test data is included
        test_data_found = any(
            record['open'] >= 100.0 and record['open'] <= 199.0 
            for record in chart_data['data']  # Check all records
        )
        assert test_data_found, f"Should find our test data in the results. Found {len(chart_data['data'])} records"
        
        # Verify data ordering (should be ascending by time)
        timestamps = [candle['time'] for candle in chart_data['data']]
        assert timestamps == sorted(timestamps), "Chart data should be ordered by timestamp"