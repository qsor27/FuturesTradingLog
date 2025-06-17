"""
Tests for OHLC database functionality and performance
"""
import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta
from futures_db import FuturesDB

class TestOHLCDatabase:
    """Test OHLC database operations and performance"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'test_futures.db')
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    
    @pytest.fixture
    def sample_ohlc_data(self):
        """Generate sample OHLC data for testing"""
        base_time = int(datetime.now().timestamp())
        data = []
        
        for i in range(100):
            timestamp = base_time + (i * 60)  # 1 minute intervals
            open_price = 100.0 + (i * 0.1)
            high_price = open_price + 2.0
            low_price = open_price - 1.5
            close_price = open_price + 0.5
            volume = 1000 + (i * 10)
            
            data.append({
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': timestamp,
                'open_price': open_price,
                'high_price': high_price,
                'low_price': low_price,
                'close_price': close_price,
                'volume': volume
            })
        
        return data
    
    def test_ohlc_table_creation(self, temp_db):
        """Test that OHLC table is created with proper schema"""
        with FuturesDB(temp_db) as db:
            # Check if table exists
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlc_data'")
            table_exists = db.cursor.fetchone() is not None
            assert table_exists, "OHLC table should be created automatically"
            
            # Check table schema
            db.cursor.execute("PRAGMA table_info(ohlc_data)")
            columns = {row[1]: row[2] for row in db.cursor.fetchall()}
            
            expected_columns = {
                'id': 'INTEGER',
                'instrument': 'TEXT',
                'timeframe': 'TEXT', 
                'timestamp': 'INTEGER',
                'open_price': 'REAL',
                'high_price': 'REAL',
                'low_price': 'REAL',
                'close_price': 'REAL',
                'volume': 'INTEGER'
            }
            
            for col_name, col_type in expected_columns.items():
                assert col_name in columns, f"Column {col_name} should exist"
                assert columns[col_name] == col_type, f"Column {col_name} should be {col_type}"
    
    def test_ohlc_indexes_created(self, temp_db):
        """Test that performance indexes are created"""
        with FuturesDB(temp_db) as db:
            # Get list of indexes
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_ohlc_%'")
            indexes = [row[0] for row in db.cursor.fetchall()]
            
            expected_indexes = [
                'idx_ohlc_instrument_timeframe_timestamp',
                'idx_ohlc_timestamp',
                'idx_ohlc_instrument',
                'idx_ohlc_timeframe',
                'idx_ohlc_high_price',
                'idx_ohlc_low_price',
                'idx_ohlc_close_price',
                'idx_ohlc_volume'
            ]
            
            for expected_index in expected_indexes:
                assert expected_index in indexes, f"Index {expected_index} should be created"
    
    def test_insert_ohlc_data(self, temp_db, sample_ohlc_data):
        """Test inserting OHLC data"""
        with FuturesDB(temp_db) as db:
            # Insert first record
            data = sample_ohlc_data[0]
            result = db.insert_ohlc_data(
                data['instrument'],
                data['timeframe'],
                data['timestamp'],
                data['open_price'],
                data['high_price'],
                data['low_price'],
                data['close_price'],
                data['volume']
            )
            
            assert result == True, "Insert should succeed"
            
            # Verify data was inserted
            count = db.get_ohlc_count()
            assert count == 1, "Should have 1 record"
            
            # Test duplicate prevention
            result2 = db.insert_ohlc_data(
                data['instrument'],
                data['timeframe'],
                data['timestamp'],
                data['open_price'],
                data['high_price'],
                data['low_price'],
                data['close_price'],
                data['volume']
            )
            
            assert result2 == True, "Insert should still succeed (IGNORE)"
            count2 = db.get_ohlc_count()
            assert count2 == 1, "Should still have 1 record (duplicate ignored)"
    
    def test_get_ohlc_data(self, temp_db, sample_ohlc_data):
        """Test retrieving OHLC data with filters"""
        with FuturesDB(temp_db) as db:
            # Insert test data
            for data in sample_ohlc_data[:10]:
                db.insert_ohlc_data(
                    data['instrument'],
                    data['timeframe'],
                    data['timestamp'],
                    data['open_price'],
                    data['high_price'],
                    data['low_price'],
                    data['close_price'],
                    data['volume']
                )
            
            # Test basic retrieval
            results = db.get_ohlc_data('MNQ', '1m')
            assert len(results) == 10, "Should retrieve all 10 records"
            
            # Test time range filtering
            start_time = sample_ohlc_data[2]['timestamp']
            end_time = sample_ohlc_data[7]['timestamp']
            
            filtered_results = db.get_ohlc_data('MNQ', '1m', start_time, end_time)
            assert len(filtered_results) == 6, "Should retrieve 6 records in range"
            
            # Test data structure
            result = filtered_results[0]
            assert 'timestamp' in result
            assert 'open_price' in result
            assert 'high_price' in result
            assert 'low_price' in result
            assert 'close_price' in result
            assert 'volume' in result
    
    def test_find_ohlc_gaps(self, temp_db, sample_ohlc_data):
        """Test gap detection in OHLC data"""
        with FuturesDB(temp_db) as db:
            # Insert data with gaps (skip every 3rd record)
            for i, data in enumerate(sample_ohlc_data[:20]):
                if i % 3 != 2:  # Skip every 3rd record
                    db.insert_ohlc_data(
                        data['instrument'],
                        data['timeframe'],
                        data['timestamp'],
                        data['open_price'],
                        data['high_price'],
                        data['low_price'],
                        data['close_price'],
                        data['volume']
                    )
            
            # Find gaps
            start_time = sample_ohlc_data[0]['timestamp']
            end_time = sample_ohlc_data[19]['timestamp']
            
            gaps = db.find_ohlc_gaps('MNQ', '1m', start_time, end_time)
            assert len(gaps) > 0, "Should detect gaps in data"
            
            # Each gap should be a tuple of (start_timestamp, end_timestamp)
            for gap in gaps:
                assert isinstance(gap, tuple), "Gap should be a tuple"
                assert len(gap) == 2, "Gap should have start and end times"
                assert gap[0] < gap[1], "Gap start should be before end"
    
    def test_ohlc_performance(self, temp_db, sample_ohlc_data):
        """Test OHLC query performance with indexes"""
        with FuturesDB(temp_db) as db:
            # Insert larger dataset for performance testing
            large_dataset = []
            base_time = int(datetime.now().timestamp())
            
            # Create 10,000 records across multiple instruments and timeframes
            instruments = ['MNQ', 'ES', 'YM', 'RTY']
            timeframes = ['1m', '5m', '15m']
            
            for i in range(10000):
                instrument = instruments[i % len(instruments)]
                timeframe = timeframes[i % len(timeframes)]
                timestamp = base_time + (i * 60)
                
                large_dataset.append({
                    'instrument': instrument,
                    'timeframe': timeframe,
                    'timestamp': timestamp,
                    'open_price': 100.0 + (i * 0.01),
                    'high_price': 100.0 + (i * 0.01) + 1.0,
                    'low_price': 100.0 + (i * 0.01) - 0.5,
                    'close_price': 100.0 + (i * 0.01) + 0.2,
                    'volume': 1000 + i
                })
            
            # Insert all data
            for data in large_dataset:
                db.insert_ohlc_data(
                    data['instrument'],
                    data['timeframe'],
                    data['timestamp'],
                    data['open_price'],
                    data['high_price'],
                    data['low_price'],
                    data['close_price'],
                    data['volume']
                )
            
            # Test query performance
            start_time = time.time()
            results = db.get_ohlc_data('MNQ', '1m', limit=1000)
            query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Should be under 100ms for indexed query
            assert query_time < 100, f"Query should be fast (<100ms), took {query_time:.2f}ms"
            assert len(results) > 0, "Should return results"
            
            # Test complex filter performance  
            start_time = time.time()
            start_ts = base_time + 1000
            end_ts = base_time + 5000
            filtered_results = db.get_ohlc_data('MNQ', '1m', start_ts, end_ts)
            filter_time = (time.time() - start_time) * 1000
            
            assert filter_time < 50, f"Filtered query should be very fast (<50ms), took {filter_time:.2f}ms"
    
    def test_get_ohlc_count(self, temp_db, sample_ohlc_data):
        """Test OHLC record counting with filters"""
        with FuturesDB(temp_db) as db:
            # Insert mixed data
            for data in sample_ohlc_data[:10]:
                db.insert_ohlc_data(
                    data['instrument'],
                    data['timeframe'],
                    data['timestamp'],
                    data['open_price'],
                    data['high_price'],
                    data['low_price'],
                    data['close_price'],
                    data['volume']
                )
            
            # Insert some ES data
            for i in range(5):
                data = sample_ohlc_data[i].copy()
                data['instrument'] = 'ES'
                db.insert_ohlc_data(
                    data['instrument'],
                    data['timeframe'],
                    data['timestamp'] + 10000,  # Different timestamps
                    data['open_price'],
                    data['high_price'],
                    data['low_price'],
                    data['close_price'],
                    data['volume']
                )
            
            # Test total count
            total_count = db.get_ohlc_count()
            assert total_count == 15, "Should have 15 total records"
            
            # Test filtered by instrument
            mnq_count = db.get_ohlc_count(instrument='MNQ')
            assert mnq_count == 10, "Should have 10 MNQ records"
            
            es_count = db.get_ohlc_count(instrument='ES')
            assert es_count == 5, "Should have 5 ES records"
            
            # Test filtered by timeframe
            timeframe_count = db.get_ohlc_count(timeframe='1m')
            assert timeframe_count == 15, "All records should be 1m timeframe"
    
    def test_timeframe_seconds_conversion(self, temp_db):
        """Test timeframe to seconds conversion"""
        with FuturesDB(temp_db) as db:
            # Test internal method
            assert db._get_timeframe_seconds('1m') == 60
            assert db._get_timeframe_seconds('5m') == 300
            assert db._get_timeframe_seconds('15m') == 900
            assert db._get_timeframe_seconds('1h') == 3600
            assert db._get_timeframe_seconds('4h') == 14400
            assert db._get_timeframe_seconds('1d') == 86400
            
            # Test unknown timeframe defaults to 1m
            assert db._get_timeframe_seconds('unknown') == 60
    
    def test_ohlc_data_validation(self, temp_db):
        """Test OHLC data validation and error handling"""
        with FuturesDB(temp_db) as db:
            # Test with invalid data types
            result = db.insert_ohlc_data('MNQ', '1m', 'invalid_timestamp', 100.0, 101.0, 99.0, 100.5, 1000)
            assert result == False, "Should fail with invalid timestamp"
            
            # Test with None required values
            result = db.insert_ohlc_data(None, '1m', 1234567890, 100.0, 101.0, 99.0, 100.5, 1000)
            assert result == False, "Should fail with None instrument"
            
            # Test retrieval with invalid parameters
            results = db.get_ohlc_data('NONEXISTENT', '1m')
            assert len(results) == 0, "Should return empty list for non-existent instrument"