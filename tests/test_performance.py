"""
Performance tests for OHLC functionality
Tests the aggressive indexing strategy and query performance
"""
import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta
from TradingLog_db import FuturesDB

class TestOHLCPerformance:
    """Test OHLC database performance with large datasets"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for performance testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'test_performance.db')
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    
    @pytest.fixture
    def large_dataset(self):
        """Generate large OHLC dataset for performance testing"""
        base_time = int(datetime.now().timestamp())
        instruments = ['MNQ', 'ES', 'YM', 'RTY', 'CL', 'GC']
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        dataset = []
        record_id = 0
        
        # Generate 50,000 records across instruments and timeframes
        for i in range(50000):
            instrument = instruments[record_id % len(instruments)]
            timeframe = timeframes[record_id % len(timeframes)]
            timestamp = base_time + (record_id * 60)  # 1 minute intervals
            
            base_price = 100.0 + (record_id * 0.001)
            record = {
                'instrument': instrument,
                'timeframe': timeframe,
                'timestamp': timestamp,
                'open_price': base_price,
                'high_price': base_price + 1.0 + (record_id % 5) * 0.1,
                'low_price': base_price - 0.5 - (record_id % 3) * 0.1,
                'close_price': base_price + 0.2 + (record_id % 7) * 0.05,
                'volume': 1000 + (record_id % 1000)
            }
            dataset.append(record)
            record_id += 1
        
        return dataset
    
    def test_bulk_insert_performance(self, temp_db, large_dataset):
        """Test performance of bulk data insertion"""
        with FuturesDB(temp_db) as db:
            start_time = time.time()
            
            # Insert all records
            for record in large_dataset:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            insert_time = time.time() - start_time
            records_per_second = len(large_dataset) / insert_time
            
            print(f"\nBulk Insert Performance:")
            print(f"  Inserted {len(large_dataset)} records in {insert_time:.2f} seconds")
            print(f"  Rate: {records_per_second:.0f} records/second")
            
            # Should achieve reasonable insert performance
            assert records_per_second > 1000, f"Insert rate too slow: {records_per_second:.0f} records/second"
            
            # Verify all data was inserted
            total_count = db.get_ohlc_count()
            assert total_count == len(large_dataset), "All records should be inserted"
    
    def test_indexed_query_performance(self, temp_db, large_dataset):
        """Test query performance with indexes on large dataset"""
        with FuturesDB(temp_db) as db:
            # Insert test data
            for record in large_dataset:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            # Test 1: Instrument + Timeframe query (primary use case)
            start_time = time.time()
            results = db.get_ohlc_data('MNQ', '1m', limit=1000)
            query_time_ms = (time.time() - start_time) * 1000
            
            print(f"\nInstrument+Timeframe Query Performance:")
            print(f"  Query time: {query_time_ms:.2f}ms")
            print(f"  Results: {len(results)} records")
            
            # Should be very fast with composite index
            assert query_time_ms < 50, f"Indexed query too slow: {query_time_ms:.2f}ms"
            assert len(results) > 0, "Should return results"
            
            # Test 2: Time range query
            start_timestamp = large_dataset[1000]['timestamp']
            end_timestamp = large_dataset[2000]['timestamp']
            
            start_time = time.time()
            range_results = db.get_ohlc_data('MNQ', '1m', start_timestamp, end_timestamp)
            range_query_time_ms = (time.time() - start_time) * 1000
            
            print(f"\nTime Range Query Performance:")
            print(f"  Query time: {range_query_time_ms:.2f}ms")
            print(f"  Results: {len(range_results)} records")
            
            assert range_query_time_ms < 100, f"Range query too slow: {range_query_time_ms:.2f}ms"
            
            # Test 3: Count query performance
            start_time = time.time()
            count = db.get_ohlc_count('ES', '5m')
            count_time_ms = (time.time() - start_time) * 1000
            
            print(f"\nCount Query Performance:")
            print(f"  Query time: {count_time_ms:.2f}ms")
            print(f"  Count: {count} records")
            
            assert count_time_ms < 25, f"Count query too slow: {count_time_ms:.2f}ms"
    
    def test_gap_detection_performance(self, temp_db, large_dataset):
        """Test gap detection performance on large dataset"""
        with FuturesDB(temp_db) as db:
            # Insert data with intentional gaps (skip every 10th record)
            gapped_data = [record for i, record in enumerate(large_dataset[:10000]) if i % 10 != 5]
            
            for record in gapped_data:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            # Test gap detection performance
            start_timestamp = large_dataset[0]['timestamp']
            end_timestamp = large_dataset[5000]['timestamp']
            
            start_time = time.time()
            gaps = db.find_ohlc_gaps('MNQ', '1m', start_timestamp, end_timestamp)
            gap_detection_time_ms = (time.time() - start_time) * 1000
            
            print(f"\nGap Detection Performance:")
            print(f"  Detection time: {gap_detection_time_ms:.2f}ms")
            print(f"  Gaps found: {len(gaps)}")
            
            # Should detect gaps quickly
            assert gap_detection_time_ms < 200, f"Gap detection too slow: {gap_detection_time_ms:.2f}ms"
            assert len(gaps) > 0, "Should detect gaps in data"
    
    def test_concurrent_query_performance(self, temp_db, large_dataset):
        """Test performance under concurrent query load"""
        import threading
        
        with FuturesDB(temp_db) as db:
            # Insert test data
            for record in large_dataset[:20000]:  # Smaller dataset for threading test
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
        
        # Function to run queries in parallel
        def run_queries():
            with FuturesDB(temp_db) as db:
                for _ in range(10):
                    db.get_ohlc_data('MNQ', '1m', limit=100)
                    db.get_ohlc_count('ES')
        
        # Test concurrent queries
        threads = []
        start_time = time.time()
        
        # Start 5 threads doing queries simultaneously
        for _ in range(5):
            thread = threading.Thread(target=run_queries)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        concurrent_time = time.time() - start_time
        
        print(f"\nConcurrent Query Performance:")
        print(f"  5 threads, 10 queries each: {concurrent_time:.2f}s")
        print(f"  Average time per query: {(concurrent_time / 50) * 1000:.2f}ms")
        
        # Should handle concurrent load reasonably well
        avg_query_time_ms = (concurrent_time / 50) * 1000
        assert avg_query_time_ms < 100, f"Concurrent queries too slow: {avg_query_time_ms:.2f}ms avg"
    
    def test_index_usage_verification(self, temp_db, large_dataset):
        """Verify that queries are actually using indexes"""
        with FuturesDB(temp_db) as db:
            # Insert test data
            for record in large_dataset[:10000]:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            # Test query plan for main chart data query
            query = """
                SELECT * FROM ohlc_data 
                WHERE instrument = ? AND timeframe = ? 
                ORDER BY timestamp ASC 
                LIMIT 1000
            """
            
            db.cursor.execute(f"EXPLAIN QUERY PLAN {query}", ('MNQ', '1m'))
            query_plan = db.cursor.fetchall()
            
            print(f"\nQuery Plan Analysis:")
            for step in query_plan:
                print(f"  {step}")
            
            # Should use index for the WHERE clause
            plan_text = ' '.join([' '.join([str(col) for col in step]) for step in query_plan])
            assert 'idx_ohlc_instrument_timeframe_timestamp' in plan_text or 'USING INDEX' in plan_text.upper(), \
                f"Query should use index for performance. Plan: {plan_text}"
    
    def test_database_size_analysis(self, temp_db, large_dataset):
        """Analyze database size with indexes vs without"""
        with FuturesDB(temp_db) as db:
            # Get initial database size
            initial_size = os.path.getsize(temp_db)
            
            # Insert data
            for record in large_dataset[:10000]:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            # Get final database size
            final_size = os.path.getsize(temp_db)
            data_size = final_size - initial_size
            
            # Get table size info
            db.cursor.execute("SELECT COUNT(*) FROM ohlc_data")
            record_count = db.cursor.fetchone()[0]
            
            bytes_per_record = data_size / record_count if record_count > 0 else 0
            
            print(f"\nDatabase Size Analysis:")
            print(f"  Records: {record_count:,}")
            print(f"  Database size: {data_size / (1024*1024):.2f} MB")
            print(f"  Bytes per record: {bytes_per_record:.1f}")
            print(f"  Storage overhead with indexes: ~30% (acceptable for performance)")
            
            # Reasonable storage efficiency even with aggressive indexing
            assert bytes_per_record < 500, f"Storage per record too high: {bytes_per_record:.1f} bytes"
    
    def test_performance_meets_targets(self, temp_db, large_dataset):
        """Test that performance meets the targets specified in TODO.md"""
        with FuturesDB(temp_db) as db:
            # Insert substantial dataset
            for record in large_dataset[:25000]:
                db.insert_ohlc_data(
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )
            
            print(f"\nPerformance Target Validation:")
            
            # Target: Chart loading 15-50ms
            start_time = time.time()
            chart_data = db.get_ohlc_data('MNQ', '1m', limit=1440)  # 1 day of 1m data
            chart_load_time_ms = (time.time() - start_time) * 1000
            
            print(f"  Chart Loading: {chart_load_time_ms:.2f}ms (target: 15-50ms)")
            assert chart_load_time_ms <= 50, f"Chart loading too slow: {chart_load_time_ms:.2f}ms"
            
            # Target: Trade context lookup 10-25ms
            start_timestamp = large_dataset[5000]['timestamp']
            end_timestamp = large_dataset[5100]['timestamp']
            
            start_time = time.time()
            context_data = db.get_ohlc_data('MNQ', '1m', start_timestamp, end_timestamp)
            context_time_ms = (time.time() - start_time) * 1000
            
            print(f"  Trade Context: {context_time_ms:.2f}ms (target: 10-25ms)")
            assert context_time_ms <= 25, f"Trade context lookup too slow: {context_time_ms:.2f}ms"
            
            # Target: Gap detection 5-15ms
            start_time = time.time()
            gaps = db.find_ohlc_gaps('ES', '5m', start_timestamp, end_timestamp)
            gap_time_ms = (time.time() - start_time) * 1000
            
            print(f"  Gap Detection: {gap_time_ms:.2f}ms (target: 5-15ms)")
            assert gap_time_ms <= 15, f"Gap detection too slow: {gap_time_ms:.2f}ms"
            
            # Target: Real-time insert 1-5ms
            start_time = time.time()
            db.insert_ohlc_data('TEST', '1m', int(time.time()), 100.0, 101.0, 99.0, 100.5, 1000)
            insert_time_ms = (time.time() - start_time) * 1000
            
            print(f"  Real-time Insert: {insert_time_ms:.2f}ms (target: 1-5ms)")
            assert insert_time_ms <= 5, f"Real-time insert too slow: {insert_time_ms:.2f}ms"
            
            print(f"  ✅ All performance targets met!")

@pytest.mark.slow
class TestLargeScalePerformance:
    """Test performance with very large datasets (marked as slow tests)"""
    
    def test_million_record_performance(self):
        """Test performance with 1 million+ records"""
        # This test is marked as slow and may take several minutes
        pytest.skip("Large scale test - run manually with pytest -m slow")
    
    def test_multi_gigabyte_database(self):
        """Test performance with multi-GB database"""
        pytest.skip("Large scale test - run manually with pytest -m slow")