"""
Performance regression tests for futures trading log application
Tests critical performance characteristics and prevents regressions
"""

import pytest
import time
import sqlite3
import tempfile
import os
from typing import Dict, List, Any
from datetime import datetime, timedelta
import statistics

from position_service import PositionService
from data_service import DataService
from TradingLog_db import TradingLogDatabase


class TestPerformanceRegression:
    """Performance regression test suite"""
    
    # Performance thresholds (in seconds)
    POSITION_BUILDING_THRESHOLD = 2.0  # Max time for 1000 trades
    DATABASE_QUERY_THRESHOLD = 0.1     # Max time for typical query
    CHART_DATA_THRESHOLD = 0.05        # Max time for chart data query
    BULK_INSERT_THRESHOLD = 1.0        # Max time for 1000 record insert
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for performance testing"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield db_path
        os.unlink(db_path)
    
    @pytest.fixture
    def position_service(self, temp_db):
        """Create PositionService instance with temp database"""
        return PositionService(temp_db)
    
    @pytest.fixture
    def trading_db(self, temp_db):
        """Create TradingLogDatabase instance with temp database"""
        return TradingLogDatabase(temp_db)
    
    @pytest.fixture
    def large_trade_dataset(self):
        """Generate large dataset for performance testing"""
        trades = []
        base_time = datetime(2023, 1, 1, 9, 0, 0)
        
        # Generate 1000 trades (500 positions)
        for i in range(1000):
            # Alternate between buy and sell for position pairs
            side = 'Buy' if i % 2 == 0 else 'Sell'
            price = 4000.0 + (i % 100) * 0.25  # Price variation
            timestamp = base_time + timedelta(minutes=i)
            
            trades.append({
                'id': i + 1,
                'entry_execution_id': f'exec_{i+1:04d}',
                'instrument': 'ES',
                'account': 'TestAccount',
                'side_of_market': side,
                'quantity': 1,
                'entry_price': price,
                'exit_price': price,
                'entry_time': timestamp.isoformat(),
                'commission': 2.50,
                'deleted': 0
            })
        
        return trades
    
    def insert_test_trades(self, position_service, trades):
        """Helper to insert test trades into database"""
        with position_service as ps:
            for trade in trades:
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
    
    def measure_execution_time(self, func, *args, **kwargs):
        """Measure execution time of a function"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        return result, execution_time
    
    def test_position_building_performance(self, position_service, large_trade_dataset):
        """Test position building performance with large dataset"""
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            # Measure position building time
            result, execution_time = self.measure_execution_time(
                ps.rebuild_positions_from_trades
            )
            
            # Performance assertions
            assert execution_time < self.POSITION_BUILDING_THRESHOLD, \
                f"Position building took {execution_time:.3f}s, threshold is {self.POSITION_BUILDING_THRESHOLD}s"
            
            # Verify correctness
            assert result['positions_created'] == 500  # 1000 trades = 500 positions
            assert result['trades_processed'] == 1000
            
            # Log performance metrics
            positions_per_second = result['positions_created'] / execution_time
            trades_per_second = result['trades_processed'] / execution_time
            
            print(f"Position building performance:")
            print(f"  Execution time: {execution_time:.3f}s")
            print(f"  Positions/second: {positions_per_second:.1f}")
            print(f"  Trades/second: {trades_per_second:.1f}")
    
    def test_database_query_performance(self, position_service, large_trade_dataset):
        """Test database query performance"""
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            ps.rebuild_positions_from_trades()
            
            # Test various query patterns
            query_tests = [
                ("SELECT COUNT(*) FROM positions", "count_all"),
                ("SELECT * FROM positions WHERE position_status = 'closed'", "filter_by_status"),
                ("SELECT * FROM positions WHERE instrument = 'ES'", "filter_by_instrument"),
                ("SELECT * FROM positions ORDER BY entry_time DESC LIMIT 10", "order_and_limit"),
                ("SELECT account, COUNT(*) FROM positions GROUP BY account", "group_by_account")
            ]
            
            for query, description in query_tests:
                result, execution_time = self.measure_execution_time(
                    ps.cursor.execute, query
                )
                
                # Fetch results to ensure complete execution
                rows = ps.cursor.fetchall()
                
                assert execution_time < self.DATABASE_QUERY_THRESHOLD, \
                    f"Query '{description}' took {execution_time:.3f}s, threshold is {self.DATABASE_QUERY_THRESHOLD}s"
                
                print(f"Query '{description}': {execution_time:.3f}s ({len(rows)} rows)")
    
    def test_chart_data_performance(self, trading_db):
        """Test chart data query performance"""
        # Insert test OHLC data
        base_time = datetime(2023, 1, 1, 9, 0, 0)
        ohlc_data = []
        
        for i in range(1000):  # 1000 data points
            timestamp = base_time + timedelta(minutes=i)
            ohlc_data.append({
                'timestamp': timestamp.isoformat(),
                'open': 4000.0 + (i % 50) * 0.25,
                'high': 4000.0 + (i % 50) * 0.25 + 2.0,
                'low': 4000.0 + (i % 50) * 0.25 - 2.0,
                'close': 4000.0 + (i % 50) * 0.25 + 1.0,
                'volume': 1000 + (i % 100) * 10
            })
        
        with trading_db as db:
            # Insert test data
            for data_point in ohlc_data:
                db.cursor.execute("""
                    INSERT INTO ohlc_data (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data_point['timestamp'],
                    data_point['open'],
                    data_point['high'],
                    data_point['low'],
                    data_point['close'],
                    data_point['volume']
                ))
            
            # Test chart data queries
            chart_queries = [
                ("SELECT * FROM ohlc_data ORDER BY timestamp DESC LIMIT 100", "recent_data"),
                ("SELECT * FROM ohlc_data WHERE timestamp >= '2023-01-01 10:00:00'", "time_range"),
                ("SELECT timestamp, close FROM ohlc_data WHERE timestamp BETWEEN '2023-01-01 09:00:00' AND '2023-01-01 12:00:00'", "specific_range")
            ]
            
            for query, description in chart_queries:
                result, execution_time = self.measure_execution_time(
                    db.cursor.execute, query
                )
                
                rows = db.cursor.fetchall()
                
                assert execution_time < self.CHART_DATA_THRESHOLD, \
                    f"Chart query '{description}' took {execution_time:.3f}s, threshold is {self.CHART_DATA_THRESHOLD}s"
                
                print(f"Chart query '{description}': {execution_time:.3f}s ({len(rows)} rows)")
    
    def test_bulk_insert_performance(self, position_service):
        """Test bulk insert performance"""
        # Generate 1000 records for bulk insert
        records = []
        base_time = datetime(2023, 1, 1, 9, 0, 0)
        
        for i in range(1000):
            timestamp = base_time + timedelta(minutes=i)
            records.append((
                f'exec_{i+1:04d}',
                'ES',
                'TestAccount',
                'Buy' if i % 2 == 0 else 'Sell',
                1,
                4000.0 + (i % 100) * 0.25,
                4000.0 + (i % 100) * 0.25,
                timestamp.isoformat(),
                2.50,
                0
            ))
        
        with position_service as ps:
            # Measure bulk insert time
            start_time = time.time()
            
            ps.cursor.executemany("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            assert execution_time < self.BULK_INSERT_THRESHOLD, \
                f"Bulk insert took {execution_time:.3f}s, threshold is {self.BULK_INSERT_THRESHOLD}s"
            
            records_per_second = len(records) / execution_time
            print(f"Bulk insert performance: {execution_time:.3f}s ({records_per_second:.1f} records/second)")
    
    def test_position_pagination_performance(self, position_service, large_trade_dataset):
        """Test position pagination performance"""
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            ps.rebuild_positions_from_trades()
            
            # Test various pagination scenarios
            pagination_tests = [
                (10, 1, "small_page_first"),
                (50, 1, "medium_page_first"),
                (100, 1, "large_page_first"),
                (10, 5, "small_page_middle"),
                (50, 3, "medium_page_middle")
            ]
            
            for page_size, page_num, description in pagination_tests:
                result, execution_time = self.measure_execution_time(
                    ps.get_positions, page_size=page_size, page=page_num
                )
                
                positions, total_count, total_pages = result
                
                assert execution_time < self.DATABASE_QUERY_THRESHOLD, \
                    f"Pagination '{description}' took {execution_time:.3f}s, threshold is {self.DATABASE_QUERY_THRESHOLD}s"
                
                print(f"Pagination '{description}': {execution_time:.3f}s ({len(positions)} positions)")
    
    def test_position_statistics_performance(self, position_service, large_trade_dataset):
        """Test position statistics calculation performance"""
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            ps.rebuild_positions_from_trades()
            
            # Test statistics calculation
            result, execution_time = self.measure_execution_time(
                ps.get_position_statistics
            )
            
            assert execution_time < self.DATABASE_QUERY_THRESHOLD, \
                f"Statistics calculation took {execution_time:.3f}s, threshold is {self.DATABASE_QUERY_THRESHOLD}s"
            
            # Verify statistics are calculated correctly
            assert result['total_positions'] == 500
            assert result['closed_positions'] == 500
            assert result['open_positions'] == 0
            
            print(f"Statistics calculation: {execution_time:.3f}s")
    
    def test_memory_usage_during_processing(self, position_service, large_trade_dataset):
        """Test memory usage during large dataset processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure memory before processing
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            # Measure memory during processing
            memory_during = process.memory_info().rss / 1024 / 1024  # MB
            
            ps.rebuild_positions_from_trades()
            
            # Measure memory after processing
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = memory_after - memory_before
        
        # Memory usage should be reasonable (less than 100MB increase for 1000 trades)
        assert memory_increase < 100, \
            f"Memory usage increased by {memory_increase:.1f}MB, which seems excessive"
        
        print(f"Memory usage: {memory_before:.1f}MB -> {memory_after:.1f}MB (increase: {memory_increase:.1f}MB)")
    
    def test_concurrent_access_performance(self, position_service, large_trade_dataset):
        """Test performance under concurrent access scenarios"""
        import threading
        import queue
        
        self.insert_test_trades(position_service, large_trade_dataset)
        
        with position_service as ps:
            ps.rebuild_positions_from_trades()
            
            # Test concurrent read operations
            results_queue = queue.Queue()
            
            def read_positions():
                try:
                    start_time = time.time()
                    positions, _, _ = ps.get_positions(page_size=50)
                    end_time = time.time()
                    results_queue.put(('success', end_time - start_time))
                except Exception as e:
                    results_queue.put(('error', str(e)))
            
            # Start multiple concurrent reads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=read_positions)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Analyze results
            execution_times = []
            errors = []
            
            while not results_queue.empty():
                result_type, result_value = results_queue.get()
                if result_type == 'success':
                    execution_times.append(result_value)
                else:
                    errors.append(result_value)
            
            # No errors should occur
            assert len(errors) == 0, f"Concurrent access errors: {errors}"
            
            # All reads should complete within threshold
            max_time = max(execution_times) if execution_times else 0
            avg_time = statistics.mean(execution_times) if execution_times else 0
            
            assert max_time < self.DATABASE_QUERY_THRESHOLD * 2, \
                f"Slowest concurrent read took {max_time:.3f}s"
            
            print(f"Concurrent access: avg={avg_time:.3f}s, max={max_time:.3f}s")
    
    def test_performance_baseline_metrics(self, position_service, large_trade_dataset):
        """Establish baseline performance metrics for monitoring"""
        metrics = {}
        
        # Test dataset preparation
        start_time = time.time()
        self.insert_test_trades(position_service, large_trade_dataset)
        metrics['data_insertion_time'] = time.time() - start_time
        
        with position_service as ps:
            # Position building
            start_time = time.time()
            result = ps.rebuild_positions_from_trades()
            metrics['position_building_time'] = time.time() - start_time
            metrics['positions_created'] = result['positions_created']
            metrics['trades_processed'] = result['trades_processed']
            
            # Basic queries
            start_time = time.time()
            ps.cursor.execute("SELECT COUNT(*) FROM positions")
            ps.cursor.fetchone()
            metrics['count_query_time'] = time.time() - start_time
            
            # Pagination
            start_time = time.time()
            ps.get_positions(page_size=50, page=1)
            metrics['pagination_time'] = time.time() - start_time
            
            # Statistics
            start_time = time.time()
            ps.get_position_statistics()
            metrics['statistics_time'] = time.time() - start_time
        
        # Calculate throughput metrics
        metrics['position_building_throughput'] = metrics['positions_created'] / metrics['position_building_time']
        metrics['trade_processing_throughput'] = metrics['trades_processed'] / metrics['position_building_time']
        
        # Print baseline metrics for monitoring
        print("Performance Baseline Metrics:")
        for key, value in metrics.items():
            if 'time' in key:
                print(f"  {key}: {value:.3f}s")
            elif 'throughput' in key:
                print(f"  {key}: {value:.1f}/s")
            else:
                print(f"  {key}: {value}")
        
        # Store metrics for regression comparison
        # In a real implementation, you would store these in a database or file
        # for comparison in future test runs
        
        return metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])  # -s to see print statements