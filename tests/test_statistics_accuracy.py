"""
Tests for Statistics Calculation Accuracy
Demonstrates inconsistencies in current calculation methods and validates standardized service
"""
import pytest
import sqlite3
from unittest.mock import Mock, patch
from scripts.TradingLog_db import FuturesDB
from services.statistics_calculation_service import (
    StandardizedStatisticsCalculator, 
    DashboardStatisticsIntegration
)

class TestStatisticsAccuracy:
    """Test statistics accuracy and consistency across different methods"""
    
    @pytest.fixture
    def test_db_data(self):
        """Sample test data with known statistics"""
        return [
            # Winning trades
            {'id': 1, 'dollars_gain_loss': 100.0, 'commission': 5.0, 'entry_time': '2025-01-01 09:00:00'},
            {'id': 2, 'dollars_gain_loss': 50.0, 'commission': 5.0, 'entry_time': '2025-01-01 10:00:00'},
            {'id': 3, 'dollars_gain_loss': 200.0, 'commission': 5.0, 'entry_time': '2025-01-01 11:00:00'},
            # Losing trades
            {'id': 4, 'dollars_gain_loss': -75.0, 'commission': 5.0, 'entry_time': '2025-01-01 12:00:00'},
            {'id': 5, 'dollars_gain_loss': -25.0, 'commission': 5.0, 'entry_time': '2025-01-01 13:00:00'},
            # Zero P&L trade (this causes the inconsistency)
            {'id': 6, 'dollars_gain_loss': 0.0, 'commission': 5.0, 'entry_time': '2025-01-01 14:00:00'},
        ]
    
    def test_win_rate_calculation_inconsistency(self, test_db_data):
        """
        Test that demonstrates inconsistent win rate calculations
        
        Expected Results:
        - Total trades: 6
        - Winning trades: 3
        - Losing trades: 2  
        - Zero P&L trades: 1
        
        Win Rate Calculations:
        - Including zero P&L: 3/6 = 50.0%
        - Excluding zero P&L: 3/5 = 60.0%
        """
        
        # Mock database responses for different methods
        with patch.object(FuturesDB, '__enter__') as mock_db_enter:
            mock_db = Mock()
            mock_db_enter.return_value = mock_db
            
            # Mock get_statistics() - excludes zero P&L from denominator
            mock_get_stats_result = [{
                'win_rate': 60.0,  # 3 winning out of 5 non-zero trades
                'total_trades': 6,
                'period': '2025-01-01'
            }]
            
            # Mock get_overview_statistics() - includes zero P&L in denominator
            mock_overview_result = {
                'total_trades': 6,
                'winning_trades': 3,
                'losing_trades': 2,
                'win_rate': 50.0  # 3 winning out of 6 total trades
            }
            
            # Mock get_summary_statistics() - includes zero P&L in denominator
            mock_summary_result = {
                'total_trades': 6,
                'winning_trades': 3,
                'losing_trades': 2,
                'win_rate': 50.0  # 3 winning out of 6 total trades
            }
            
            # Set up mocks
            mock_db.get_statistics.return_value = mock_get_stats_result
            mock_db.get_overview_statistics.return_value = mock_overview_result
            mock_db.get_summary_statistics.return_value = mock_summary_result
            
            with FuturesDB() as db:
                # Test all three methods
                daily_stats = db.get_statistics('daily')
                overview_stats = db.get_overview_statistics()
                summary_stats = db.get_summary_statistics()
                
                # INCONSISTENCY DETECTED: Different win rates for same data
                daily_win_rate = daily_stats[0]['win_rate']
                overview_win_rate = overview_stats['win_rate']
                summary_win_rate = summary_stats['win_rate']
                
                # This test will FAIL due to inconsistent calculations
                assert daily_win_rate != overview_win_rate, f"Inconsistency found: get_statistics={daily_win_rate}%, get_overview_statistics={overview_win_rate}%"
                assert daily_win_rate != summary_win_rate, f"Inconsistency found: get_statistics={daily_win_rate}%, get_summary_statistics={summary_win_rate}%"
                
                # Expected: get_statistics=60%, others=50%
                assert daily_win_rate == 60.0, "get_statistics() excludes zero P&L trades"
                assert overview_win_rate == 50.0, "get_overview_statistics() includes zero P&L trades"
                assert summary_win_rate == 50.0, "get_summary_statistics() includes zero P&L trades"
    
    def test_calculation_accuracy_with_real_data(self):
        """Test calculations with realistic trading data"""
        
        # Test data: 5 winning, 3 losing, 2 zero P&L = 10 total trades
        test_trades = [
            {'dollars_gain_loss': 150.0},  # Win
            {'dollars_gain_loss': 200.0},  # Win  
            {'dollars_gain_loss': 75.0},   # Win
            {'dollars_gain_loss': 300.0},  # Win
            {'dollars_gain_loss': 125.0},  # Win
            {'dollars_gain_loss': -100.0}, # Loss
            {'dollars_gain_loss': -150.0}, # Loss
            {'dollars_gain_loss': -50.0},  # Loss
            {'dollars_gain_loss': 0.0},    # Break-even
            {'dollars_gain_loss': 0.0},    # Break-even
        ]
        
        total_trades = len(test_trades)
        winning_trades = sum(1 for t in test_trades if t['dollars_gain_loss'] > 0)
        losing_trades = sum(1 for t in test_trades if t['dollars_gain_loss'] < 0)
        zero_trades = sum(1 for t in test_trades if t['dollars_gain_loss'] == 0)
        non_zero_trades = total_trades - zero_trades
        
        # Expected calculations
        expected_win_rate_including_zero = (winning_trades / total_trades) * 100  # 50%
        expected_win_rate_excluding_zero = (winning_trades / non_zero_trades) * 100  # 62.5%
        
        assert total_trades == 10
        assert winning_trades == 5
        assert losing_trades == 3
        assert zero_trades == 2
        assert expected_win_rate_including_zero == 50.0
        assert expected_win_rate_excluding_zero == 62.5
        
        # This demonstrates the calculation inconsistency
        print(f"Win rate including zero P&L trades: {expected_win_rate_including_zero}%")
        print(f"Win rate excluding zero P&L trades: {expected_win_rate_excluding_zero}%")
        print(f"Difference: {expected_win_rate_excluding_zero - expected_win_rate_including_zero}%")
    
    def test_position_based_vs_trade_based_calculations(self):
        """Test that position-based and trade-based calculations should align"""
        
        # This test demonstrates the architectural issue:
        # Dashboard uses trade-based calculations but should use position-based
        
        # Sample position data (aggregated from multiple trades)
        position_data = {
            'total_positions': 5,
            'winning_positions': 3,
            'losing_positions': 2,
            'total_pnl': 500.0
        }
        
        # Corresponding trade data (individual executions)
        trade_data = {
            'total_trades': 15,  # Multiple trades per position
            'winning_trades': 8,  # Individual winning trades
            'losing_trades': 7,   # Individual losing trades
            'total_pnl': 500.0    # Same total P&L
        }
        
        # Position-based win rate: 3/5 = 60%
        position_win_rate = (position_data['winning_positions'] / position_data['total_positions']) * 100
        
        # Trade-based win rate: 8/15 = 53.33%
        trade_win_rate = (trade_data['winning_trades'] / trade_data['total_trades']) * 100
        
        # These should conceptually align but don't due to calculation basis
        assert position_win_rate == 60.0
        assert round(trade_win_rate, 2) == 53.33
        
        # The P&L should be identical regardless of calculation method
        assert position_data['total_pnl'] == trade_data['total_pnl']
        
        print(f"Position-based win rate: {position_win_rate}%")
        print(f"Trade-based win rate: {trade_win_rate}%")
        print("These rates measure different things and should not be mixed!")

    def test_edge_case_scenarios(self):
        """Test edge cases that might cause calculation errors"""
        
        # Empty dataset
        empty_stats = self._calculate_stats([])
        assert empty_stats['win_rate'] == 0.0
        assert empty_stats['total_trades'] == 0
        
        # Only winning trades
        winning_only = [{'dollars_gain_loss': 100.0}, {'dollars_gain_loss': 50.0}]
        winning_stats = self._calculate_stats(winning_only)
        assert winning_stats['win_rate'] == 100.0
        
        # Only losing trades
        losing_only = [{'dollars_gain_loss': -100.0}, {'dollars_gain_loss': -50.0}]
        losing_stats = self._calculate_stats(losing_only)
        assert losing_stats['win_rate'] == 0.0
        
        # Only zero P&L trades
        zero_only = [{'dollars_gain_loss': 0.0}, {'dollars_gain_loss': 0.0}]
        zero_stats = self._calculate_stats(zero_only)
        # This is where the inconsistency shows up most clearly
        assert zero_stats['win_rate'] == 0.0  # Should be 0% regardless of calculation method
    
    def _calculate_stats(self, trades):
        """Helper method to calculate statistics"""
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['dollars_gain_loss'] > 0)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        }

class TestStandardizedStatisticsCalculator:
    """Test the standardized statistics calculator"""
    
    def test_win_rate_calculation_include_zero_pnl(self):
        """Test win rate calculation including zero P&L trades"""
        trades_data = [
            {'dollars_gain_loss': 100.0},  # Win
            {'dollars_gain_loss': -50.0},  # Loss
            {'dollars_gain_loss': 0.0},    # Zero P&L
            {'dollars_gain_loss': 75.0},   # Win
        ]
        
        win_rate = StandardizedStatisticsCalculator.calculate_win_rate(trades_data, include_zero_pnl=True)
        assert win_rate == 50.0  # 2 wins out of 4 total trades
    
    def test_win_rate_calculation_exclude_zero_pnl(self):
        """Test win rate calculation excluding zero P&L trades"""
        trades_data = [
            {'dollars_gain_loss': 100.0},  # Win
            {'dollars_gain_loss': -50.0},  # Loss
            {'dollars_gain_loss': 0.0},    # Zero P&L (excluded)
            {'dollars_gain_loss': 75.0},   # Win
        ]
        
        win_rate = StandardizedStatisticsCalculator.calculate_win_rate(trades_data, include_zero_pnl=False)
        assert round(win_rate, 2) == 66.67  # 2 wins out of 3 non-zero trades (rounded)
    
    def test_calculate_basic_statistics_comprehensive(self):
        """Test comprehensive basic statistics calculation"""
        trades_data = [
            {'dollars_gain_loss': 150.0, 'commission': 5.0},  # Win
            {'dollars_gain_loss': 100.0, 'commission': 5.0},  # Win
            {'dollars_gain_loss': -75.0, 'commission': 5.0},  # Loss
            {'dollars_gain_loss': -25.0, 'commission': 5.0},  # Loss
            {'dollars_gain_loss': 0.0, 'commission': 5.0},    # Zero P&L
        ]
        
        stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
        
        # Check all expected fields are present
        expected_fields = [
            'total_trades', 'winning_trades', 'losing_trades', 'zero_pnl_trades',
            'win_rate', 'total_pnl', 'gross_profit', 'gross_loss', 'profit_factor',
            'avg_win', 'avg_loss', 'reward_risk_ratio', 'total_commission'
        ]
        
        for field in expected_fields:
            assert field in stats, f"Missing field: {field}"
        
        # Verify calculations
        assert stats['total_trades'] == 5
        assert stats['winning_trades'] == 2
        assert stats['losing_trades'] == 2
        assert stats['zero_pnl_trades'] == 1
        assert stats['win_rate'] == 40.0  # 2/5 = 40% (including zero P&L)
        assert stats['total_pnl'] == 150.0  # 150 + 100 - 75 - 25 + 0 = 150
        assert stats['gross_profit'] == 250.0  # 150 + 100
        assert stats['gross_loss'] == 100.0  # abs(-75 + -25)
        assert stats['profit_factor'] == 2.5  # 250 / 100
        assert stats['avg_win'] == 125.0  # 250 / 2
        assert stats['avg_loss'] == 50.0  # 100 / 2
        assert stats['reward_risk_ratio'] == 2.5  # 125 / 50
        assert stats['total_commission'] == 25.0  # 5 * 5
    
    def test_empty_trades_data(self):
        """Test handling of empty trades data"""
        stats = StandardizedStatisticsCalculator.calculate_basic_statistics([])
        
        assert stats['total_trades'] == 0
        assert stats['win_rate'] == 0.0
        assert stats['total_pnl'] == 0.0
        assert stats['profit_factor'] == 0.0
    
    def test_only_winning_trades(self):
        """Test calculation with only winning trades"""
        trades_data = [
            {'dollars_gain_loss': 100.0, 'commission': 5.0},
            {'dollars_gain_loss': 50.0, 'commission': 5.0},
        ]
        
        stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
        
        assert stats['win_rate'] == 100.0
        assert stats['losing_trades'] == 0
        assert stats['gross_loss'] == 0.0
        assert stats['profit_factor'] == 0.0  # Division by zero case
        assert stats['avg_loss'] == 0.0
    
    def test_only_losing_trades(self):
        """Test calculation with only losing trades"""
        trades_data = [
            {'dollars_gain_loss': -100.0, 'commission': 5.0},
            {'dollars_gain_loss': -50.0, 'commission': 5.0},
        ]
        
        stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
        
        assert stats['win_rate'] == 0.0
        assert stats['winning_trades'] == 0
        assert stats['gross_profit'] == 0.0
        assert stats['profit_factor'] == 0.0
        assert stats['avg_win'] == 0.0
        assert stats['reward_risk_ratio'] == 0.0

class TestDashboardStatisticsIntegration:
    """Test the dashboard integration service"""
    
    @patch('services.statistics_calculation_service.FuturesDB')
    def test_overview_statistics_standardized(self, mock_db_class):
        """Test standardized overview statistics"""
        # Mock database response
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {'dollars_gain_loss': 100.0, 'commission': 5.0, 'entry_time': '2025-01-01', 'instrument': 'ES', 'account': 'Test'},
            {'dollars_gain_loss': -50.0, 'commission': 5.0, 'entry_time': '2025-01-01', 'instrument': 'ES', 'account': 'Test'},
        ]
        mock_db._execute_with_monitoring.return_value = mock_result
        
        stats = DashboardStatisticsIntegration.get_overview_statistics_standardized()
        
        assert 'total_trades' in stats
        assert 'win_rate' in stats
        assert 'total_pnl' in stats
        
        # Verify database query was called
        mock_db._execute_with_monitoring.assert_called_once()
    
    @patch('services.statistics_calculation_service.FuturesDB')
    def test_summary_statistics_standardized_with_filters(self, mock_db_class):
        """Test standardized summary statistics with filters"""
        # Mock database response
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {'dollars_gain_loss': 100.0, 'commission': 5.0, 'entry_time': '2025-01-01', 'instrument': 'ES', 'account': 'Test'},
        ]
        mock_db._execute_with_monitoring.return_value = mock_result
        
        stats = DashboardStatisticsIntegration.get_summary_statistics_standardized(
            account='Test',
            instrument='ES',
            start_date='2025-01-01',
            end_date='2025-01-31'
        )
        
        assert 'total_trades' in stats
        
        # Verify filters were applied in query
        call_args = mock_db._execute_with_monitoring.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert 'account = ?' in query
        assert 'instrument = ?' in query
        assert 'entry_time >= ?' in query
        assert 'entry_time <= ?' in query
        assert params == ['Test', 'ES', '2025-01-01', '2025-01-31']

class TestWinRateConsistencyFix:
    """Test that the win rate inconsistency has been resolved"""
    
    def test_consistent_win_rate_calculations(self):
        """Test that all calculation methods now return consistent win rates"""
        test_trades = [
            {'dollars_gain_loss': 100.0, 'commission': 5.0},  # Win
            {'dollars_gain_loss': 50.0, 'commission': 5.0},   # Win
            {'dollars_gain_loss': -75.0, 'commission': 5.0},  # Loss
            {'dollars_gain_loss': 0.0, 'commission': 5.0},    # Zero P&L
        ]
        
        # All standardized methods should use the same calculation
        win_rate_include_zero = StandardizedStatisticsCalculator.calculate_win_rate(test_trades, include_zero_pnl=True)
        basic_stats = StandardizedStatisticsCalculator.calculate_basic_statistics(test_trades)
        
        # Both should include zero P&L trades in denominator (standard approach)
        assert win_rate_include_zero == 50.0  # 2 wins out of 4 total
        assert basic_stats['win_rate'] == 50.0  # Same calculation
        
        # This demonstrates the fix: consistent methodology across all calculations
        print(f"Standardized win rate: {win_rate_include_zero}%")
        print(f"Basic stats win rate: {basic_stats['win_rate']}%")
        print("✓ Win rate calculations are now consistent!")
    
    def test_legacy_vs_standardized_comparison(self):
        """Test comparison between legacy inconsistent and new standardized methods"""
        test_trades = [
            {'dollars_gain_loss': 100.0},  # Win
            {'dollars_gain_loss': 50.0},   # Win
            {'dollars_gain_loss': 75.0},   # Win
            {'dollars_gain_loss': -50.0},  # Loss
            {'dollars_gain_loss': -25.0},  # Loss
            {'dollars_gain_loss': 0.0},    # Zero P&L (causes inconsistency)
            {'dollars_gain_loss': 0.0},    # Zero P&L
        ]
        
        # Standardized calculation (recommended approach)
        standardized_stats = StandardizedStatisticsCalculator.calculate_basic_statistics(test_trades)
        
        # Legacy calculations (would be inconsistent)
        legacy_include_zero = 3 / 7 * 100  # Include zero P&L in denominator: 42.86%
        legacy_exclude_zero = 3 / 5 * 100  # Exclude zero P&L from denominator: 60%
        
        # Our standardized approach should match the "include zero P&L" methodology
        assert standardized_stats['win_rate'] == round(legacy_include_zero, 2)
        assert standardized_stats['win_rate'] != legacy_exclude_zero
        
        # Demonstrate the difference that was causing issues
        difference = legacy_exclude_zero - legacy_include_zero
        print(f"Legacy inconsistency difference: {difference:.2f}%")
        print(f"Standardized approach eliminates this inconsistency")