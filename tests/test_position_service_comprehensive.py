"""
Comprehensive test suite for position_service.py position logic
Tests all critical edge cases and position building scenarios
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, patch

from position_service import PositionService


class TestPositionServiceComprehensive:
    """Comprehensive test suite for position building logic"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield db_path
        os.unlink(db_path)
    
    @pytest.fixture
    def position_service(self, temp_db):
        """Create PositionService instance with temp database"""
        return PositionService(temp_db)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data for testing"""
        base_time = datetime(2023, 1, 1, 9, 0, 0)
        return [
            {
                'id': 1,
                'entry_execution_id': 'exec_001',
                'instrument': 'ES',
                'account': 'Test001',
                'side_of_market': 'Buy',
                'quantity': 2,
                'entry_price': 4000.0,
                'exit_price': 4000.0,
                'entry_time': base_time.isoformat(),
                'commission': 2.50,
                'deleted': 0
            },
            {
                'id': 2,
                'entry_execution_id': 'exec_002',
                'instrument': 'ES',
                'account': 'Test001',
                'side_of_market': 'Sell',
                'quantity': 2,
                'entry_price': 4010.0,
                'exit_price': 4010.0,
                'entry_time': (base_time + timedelta(minutes=30)).isoformat(),
                'commission': 2.50,
                'deleted': 0
            }
        ]
    
    def test_position_service_context_manager(self, position_service):
        """Test PositionService context manager functionality"""
        with position_service as ps:
            assert ps.conn is not None
            assert ps.cursor is not None
            
            # Test that tables are created
            ps.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in ps.cursor.fetchall()]
            assert 'positions' in tables
            assert 'position_executions' in tables
    
    def test_empty_trades_handling(self, position_service):
        """Test handling of empty trades list"""
        with position_service as ps:
            # Mock empty trades query
            ps.cursor.execute = Mock(return_value=Mock())
            ps.cursor.fetchall = Mock(return_value=[])
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 0
            assert result['trades_processed'] == 0
    
    def test_simple_long_position_building(self, position_service):
        """Test basic long position: Buy → Sell"""
        with position_service as ps:
            # Insert test trades
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_001', 'ES', 'Test001', 'Buy', 2, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0))
            
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_002', 'ES', 'Test001', 'Sell', 2, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0))
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 1
            assert result['trades_processed'] == 2
            
            # Verify position data
            ps.cursor.execute("SELECT * FROM positions")
            positions = ps.cursor.fetchall()
            assert len(positions) == 1
            
            position = dict(positions[0])
            assert position['position_type'] == 'Long'
            assert position['position_status'] == 'closed'
            assert position['total_quantity'] == 2
            assert position['average_entry_price'] == 4000.0
            assert position['average_exit_price'] == 4010.0
    
    def test_simple_short_position_building(self, position_service):
        """Test basic short position: Sell → Buy"""
        with position_service as ps:
            # Insert test trades
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_001', 'ES', 'Test001', 'Sell', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0))
            
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_002', 'ES', 'Test001', 'Buy', 1, 3990.0, 3990.0, '2023-01-01 10:00:00', 2.50, 0))
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 1
            
            # Verify position data
            ps.cursor.execute("SELECT * FROM positions")
            positions = ps.cursor.fetchall()
            position = dict(positions[0])
            
            assert position['position_type'] == 'Short'
            assert position['position_status'] == 'closed'
            assert position['total_quantity'] == 1
    
    def test_position_scaling_scenario(self, position_service):
        """Test position scaling (adding to existing position)"""
        with position_service as ps:
            # Insert scaling trades: Buy 1, Buy 2, Sell 3
            trades = [
                ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Buy', 2, 4005.0, 4005.0, '2023-01-01 09:30:00', 2.50, 0),
                ('exec_003', 'ES', 'Test001', 'Sell', 3, 4020.0, 4020.0, '2023-01-01 10:00:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 1
            assert result['trades_processed'] == 3
            
            # Verify position has correct scaling data
            ps.cursor.execute("SELECT * FROM positions")
            position = dict(ps.cursor.fetchone())
            
            assert position['position_type'] == 'Long'
            assert position['position_status'] == 'closed'
            assert position['total_quantity'] == 3
            assert position['max_quantity'] == 3
            assert position['execution_count'] == 3
    
    def test_position_reversal_detection(self, position_service):
        """Test position reversal: Long → Short without reaching zero"""
        with position_service as ps:
            # Insert reversal trades: Buy 2, Sell 5 (reverse to Short 3)
            trades = [
                ('exec_001', 'ES', 'Test001', 'Buy', 2, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Sell', 5, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            # Should create 2 positions: closed Long + open Short
            assert result['positions_created'] == 2
            
            # Verify positions
            ps.cursor.execute("SELECT * FROM positions ORDER BY id")
            positions = [dict(row) for row in ps.cursor.fetchall()]
            
            # First position: closed Long
            assert positions[0]['position_type'] == 'Long'
            assert positions[0]['position_status'] == 'closed'
            
            # Second position: open Short
            assert positions[1]['position_type'] == 'Short'
            assert positions[1]['position_status'] == 'open'
    
    def test_multiple_instruments_handling(self, position_service):
        """Test handling of multiple instruments in same account"""
        with position_service as ps:
            # Insert trades for different instruments
            trades = [
                ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0),
                ('exec_003', 'NQ', 'Test001', 'Sell', 2, 15000.0, 15000.0, '2023-01-01 09:30:00', 2.50, 0),
                ('exec_004', 'NQ', 'Test001', 'Buy', 2, 14980.0, 14980.0, '2023-01-01 10:30:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 2
            
            # Verify separate positions for each instrument
            ps.cursor.execute("SELECT instrument, position_type FROM positions")
            instruments = [dict(row) for row in ps.cursor.fetchall()]
            
            assert len(instruments) == 2
            assert any(p['instrument'] == 'ES' and p['position_type'] == 'Long' for p in instruments)
            assert any(p['instrument'] == 'NQ' and p['position_type'] == 'Short' for p in instruments)
    
    def test_multiple_accounts_handling(self, position_service):
        """Test handling of multiple accounts"""
        with position_service as ps:
            # Insert trades for different accounts
            trades = [
                ('exec_001', 'ES', 'Account_A', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Account_A', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0),
                ('exec_003', 'ES', 'Account_B', 'Sell', 2, 4005.0, 4005.0, '2023-01-01 09:30:00', 2.50, 0),
                ('exec_004', 'ES', 'Account_B', 'Buy', 2, 3995.0, 3995.0, '2023-01-01 10:30:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 2
            
            # Verify separate positions for each account
            ps.cursor.execute("SELECT account, position_type FROM positions")
            accounts = [dict(row) for row in ps.cursor.fetchall()]
            
            assert len(accounts) == 2
            assert any(p['account'] == 'Account_A' and p['position_type'] == 'Long' for p in accounts)
            assert any(p['account'] == 'Account_B' and p['position_type'] == 'Short' for p in accounts)
    
    def test_open_position_handling(self, position_service):
        """Test handling of open (unclosed) positions"""
        with position_service as ps:
            # Insert only opening trade
            ps.cursor.execute("""
                INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                  quantity, entry_price, exit_price, entry_time, commission, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('exec_001', 'ES', 'Test001', 'Buy', 2, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0))
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 1
            
            # Verify open position
            ps.cursor.execute("SELECT * FROM positions")
            position = dict(ps.cursor.fetchone())
            
            assert position['position_type'] == 'Long'
            assert position['position_status'] == 'open'
            assert position['exit_time'] is None
            assert position['average_exit_price'] == position['average_entry_price']
    
    def test_invalid_trade_data_handling(self, position_service):
        """Test handling of invalid trade data"""
        with position_service as ps:
            # Insert invalid trades
            invalid_trades = [
                ('exec_001', '', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),  # Missing instrument
                ('exec_002', 'ES', '', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),  # Missing account
                ('exec_003', 'ES', 'Test001', 'Invalid', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),  # Invalid side
                ('exec_004', 'ES', 'Test001', 'Buy', 0, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0)  # Zero quantity
            ]
            
            for trade in invalid_trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            # Should handle gracefully with no positions created
            assert result['positions_created'] == 0
            assert result['trades_processed'] == 0
    
    def test_deleted_trades_exclusion(self, position_service):
        """Test that deleted trades are excluded from position building"""
        with position_service as ps:
            # Insert trades with some marked as deleted
            trades = [
                ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 1),  # Deleted
                ('exec_003', 'ES', 'Test001', 'Sell', 1, 4020.0, 4020.0, '2023-01-01 11:00:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            # Should create 1 position from 2 non-deleted trades
            assert result['positions_created'] == 1
            assert result['trades_processed'] == 2
    
    def test_fifo_pnl_calculation(self, position_service):
        """Test FIFO P&L calculation for complex positions"""
        with position_service as ps:
            # Insert complex scaling scenario
            trades = [
                ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Buy', 2, 4005.0, 4005.0, '2023-01-01 09:30:00', 2.50, 0),
                ('exec_003', 'ES', 'Test001', 'Sell', 2, 4020.0, 4020.0, '2023-01-01 10:00:00', 2.50, 0),
                ('exec_004', 'ES', 'Test001', 'Sell', 1, 4025.0, 4025.0, '2023-01-01 10:30:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            result = ps.rebuild_positions_from_trades()
            
            assert result['positions_created'] == 1
            
            # Verify FIFO P&L calculation
            ps.cursor.execute("SELECT * FROM positions")
            position = dict(ps.cursor.fetchone())
            
            assert position['position_status'] == 'closed'
            assert position['total_points_pnl'] > 0  # Should be profitable
    
    def test_instrument_multiplier_application(self, position_service):
        """Test that instrument multipliers are applied correctly"""
        with position_service as ps:
            # Mock instrument multiplier
            with patch.object(ps, '_get_instrument_multiplier', return_value=50.0):
                # Insert simple long position
                trades = [
                    ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                    ('exec_002', 'ES', 'Test001', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0)
                ]
                
                for trade in trades:
                    ps.cursor.execute("""
                        INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                          quantity, entry_price, exit_price, entry_time, commission, deleted)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, trade)
                
                result = ps.rebuild_positions_from_trades()
                
                assert result['positions_created'] == 1
                
                # Verify multiplier was applied
                ps.cursor.execute("SELECT * FROM positions")
                position = dict(ps.cursor.fetchone())
                
                expected_dollar_pnl = 10.0 * 50.0 * 1  # points * multiplier * quantity
                assert position['total_dollars_pnl'] == expected_dollar_pnl
    
    def test_position_statistics_calculation(self, position_service):
        """Test position statistics calculation"""
        with position_service as ps:
            # Insert multiple positions
            trades = [
                # Winning position
                ('exec_001', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Test001', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0),
                # Losing position
                ('exec_003', 'ES', 'Test001', 'Buy', 1, 4020.0, 4020.0, '2023-01-01 11:00:00', 2.50, 0),
                ('exec_004', 'ES', 'Test001', 'Sell', 1, 4015.0, 4015.0, '2023-01-01 12:00:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            ps.rebuild_positions_from_trades()
            
            # Get statistics
            stats = ps.get_position_statistics()
            
            assert stats['total_positions'] == 2
            assert stats['closed_positions'] == 2
            assert stats['open_positions'] == 0
            assert stats['winning_positions'] == 1
            assert stats['win_rate'] == 50.0
            assert stats['instruments_traded'] == 1
            assert stats['accounts_traded'] == 1
    
    def test_position_pagination(self, position_service):
        """Test position pagination functionality"""
        with position_service as ps:
            # Insert multiple positions
            for i in range(5):
                trades = [
                    (f'exec_{i*2+1}', 'ES', 'Test001', 'Buy', 1, 4000.0, 4000.0, f'2023-01-01 0{i+9}:00:00', 2.50, 0),
                    (f'exec_{i*2+2}', 'ES', 'Test001', 'Sell', 1, 4010.0, 4010.0, f'2023-01-01 {i+10}:00:00', 2.50, 0)
                ]
                
                for trade in trades:
                    ps.cursor.execute("""
                        INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                          quantity, entry_price, exit_price, entry_time, commission, deleted)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, trade)
            
            ps.rebuild_positions_from_trades()
            
            # Test pagination
            positions, total_count, total_pages = ps.get_positions(page_size=2, page=1)
            
            assert len(positions) == 2
            assert total_count == 5
            assert total_pages == 3
            
            # Test second page
            positions_page2, _, _ = ps.get_positions(page_size=2, page=2)
            assert len(positions_page2) == 2
    
    def test_position_filtering(self, position_service):
        """Test position filtering functionality"""
        with position_service as ps:
            # Insert positions with different accounts and instruments
            trades = [
                ('exec_001', 'ES', 'Account_A', 'Buy', 1, 4000.0, 4000.0, '2023-01-01 09:00:00', 2.50, 0),
                ('exec_002', 'ES', 'Account_A', 'Sell', 1, 4010.0, 4010.0, '2023-01-01 10:00:00', 2.50, 0),
                ('exec_003', 'NQ', 'Account_B', 'Buy', 1, 15000.0, 15000.0, '2023-01-01 11:00:00', 2.50, 0),
                ('exec_004', 'NQ', 'Account_B', 'Sell', 1, 15010.0, 15010.0, '2023-01-01 12:00:00', 2.50, 0)
            ]
            
            for trade in trades:
                ps.cursor.execute("""
                    INSERT INTO trades (entry_execution_id, instrument, account, side_of_market, 
                                      quantity, entry_price, exit_price, entry_time, commission, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            ps.rebuild_positions_from_trades()
            
            # Test account filtering
            positions_account_a, _, _ = ps.get_positions(account='Account_A')
            assert len(positions_account_a) == 1
            assert positions_account_a[0]['account'] == 'Account_A'
            
            # Test instrument filtering
            positions_es, _, _ = ps.get_positions(instrument='ES')
            assert len(positions_es) == 1
            assert positions_es[0]['instrument'] == 'ES'
            
            # Test status filtering
            positions_closed, _, _ = ps.get_positions(status='closed')
            assert len(positions_closed) == 2
            assert all(p['position_status'] == 'closed' for p in positions_closed)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])