"""
Test Position Algorithms

Unit tests for the refactored position algorithm functions.
"""

import unittest
from datetime import datetime
from decimal import Decimal
from position_algorithms import (
    calculate_running_quantity,
    group_executions_by_position,
    calculate_position_pnl,
    validate_position_boundaries,
    aggregate_position_statistics,
    create_position_summary
)


class TestPositionAlgorithms(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.sample_executions = [
            {
                'id': 1,
                'instrument': 'ES 03-24',
                'account': 'Sim101',
                'side_of_market': 'Buy',
                'quantity': 2,
                'entry_price': 4500.25,
                'exit_price': None,
                'entry_time': datetime(2024, 1, 15, 9, 30, 0),
                'commission': 4.32
            },
            {
                'id': 2,
                'instrument': 'ES 03-24',
                'account': 'Sim101',
                'side_of_market': 'Sell',
                'quantity': 2,
                'entry_price': None,
                'exit_price': 4510.50,
                'entry_time': datetime(2024, 1, 15, 10, 15, 0),
                'commission': 4.32
            }
        ]
    
    def test_calculate_running_quantity_simple_position(self):
        """Test running quantity calculation for simple long position"""
        flows = calculate_running_quantity(self.sample_executions)
        
        self.assertEqual(len(flows), 2)
        
        # First execution: Buy 2 contracts
        self.assertEqual(flows[0].running_quantity, 2)
        self.assertEqual(flows[0].action_type, 'START')
        self.assertEqual(flows[0].signed_change, 2)
        
        # Second execution: Sell 2 contracts (close)
        self.assertEqual(flows[1].running_quantity, 0)
        self.assertEqual(flows[1].action_type, 'CLOSE')
        self.assertEqual(flows[1].signed_change, -2)
    
    def test_calculate_running_quantity_complex_position(self):
        """Test running quantity with multiple entries and partial exits"""
        complex_executions = [
            {
                'id': 1, 'side_of_market': 'Buy', 'quantity': 2, 
                'entry_time': datetime(2024, 1, 15, 9, 30), 'entry_price': 4500,
                'instrument': 'ES', 'account': 'Test', 'commission': 4
            },
            {
                'id': 2, 'side_of_market': 'Buy', 'quantity': 1,
                'entry_time': datetime(2024, 1, 15, 9, 35), 'entry_price': 4502,
                'instrument': 'ES', 'account': 'Test', 'commission': 2
            },
            {
                'id': 3, 'side_of_market': 'Sell', 'quantity': 1,
                'entry_time': datetime(2024, 1, 15, 10, 0), 'exit_price': 4505,
                'instrument': 'ES', 'account': 'Test', 'commission': 2
            },
            {
                'id': 4, 'side_of_market': 'Sell', 'quantity': 2,
                'entry_time': datetime(2024, 1, 15, 10, 15), 'exit_price': 4508,
                'instrument': 'ES', 'account': 'Test', 'commission': 4
            }
        ]
        
        flows = calculate_running_quantity(complex_executions)
        
        expected_quantities = [2, 3, 2, 0]
        expected_actions = ['START', 'ADD', 'REDUCE', 'CLOSE']
        
        for i, flow in enumerate(flows):
            self.assertEqual(flow.running_quantity, expected_quantities[i])
            self.assertEqual(flow.action_type, expected_actions[i])
    
    def test_group_executions_by_position(self):
        """Test grouping executions into discrete positions"""
        flows = calculate_running_quantity(self.sample_executions)
        positions = group_executions_by_position(flows)
        
        self.assertEqual(len(positions), 1)  # One complete position
        self.assertEqual(len(positions[0]), 2)  # Two executions in position
    
    def test_calculate_position_pnl_long_winner(self):
        """Test P&L calculation for profitable long position"""
        flows = calculate_running_quantity(self.sample_executions)
        pnl = calculate_position_pnl(flows, Decimal('50'))  # ES multiplier
        
        self.assertNotIn('error', pnl)
        self.assertTrue(pnl['is_long'])
        self.assertEqual(pnl['position_size'], 2)
        self.assertEqual(pnl['avg_entry_price'], 4500.25)
        self.assertEqual(pnl['avg_exit_price'], 4510.50)
        self.assertEqual(pnl['points_pnl'], 10.25)
        self.assertEqual(pnl['total_commission'], 8.64)
        
        # Check dollar P&L calculation
        expected_gross = 10.25 * 50 * 2  # points * multiplier * size
        expected_net = expected_gross - 8.64
        self.assertEqual(pnl['gross_pnl'], expected_gross)
        self.assertEqual(pnl['net_pnl'], expected_net)
    
    def test_calculate_position_pnl_short_position(self):
        """Test P&L calculation for short position"""
        short_executions = [
            {
                'id': 1, 'side_of_market': 'Sell', 'quantity': 1,
                'entry_time': datetime(2024, 1, 15, 9, 30), 'entry_price': 4500,
                'instrument': 'ES', 'account': 'Test', 'commission': 2
            },
            {
                'id': 2, 'side_of_market': 'Buy', 'quantity': 1,
                'entry_time': datetime(2024, 1, 15, 10, 0), 'exit_price': 4490,
                'instrument': 'ES', 'account': 'Test', 'commission': 2
            }
        ]
        
        flows = calculate_running_quantity(short_executions)
        pnl = calculate_position_pnl(flows, Decimal('50'))
        
        self.assertNotIn('error', pnl)
        self.assertFalse(pnl['is_long'])
        self.assertEqual(pnl['points_pnl'], 10.0)  # 4500 - 4490 for short
        self.assertGreater(pnl['net_pnl'], 0)  # Profitable short
    
    def test_validate_position_boundaries_valid(self):
        """Test validation of valid position boundaries"""
        flows = calculate_running_quantity(self.sample_executions)
        errors = validate_position_boundaries(flows)
        
        self.assertEqual(len(errors), 0)  # No validation errors
    
    def test_validate_position_boundaries_invalid(self):
        """Test validation catches invalid position boundaries"""
        # Create invalid executions that don't start from zero
        invalid_executions = [
            {
                'id': 1, 'side_of_market': 'Buy', 'quantity': 1,
                'entry_time': datetime(2024, 1, 15, 9, 30), 'entry_price': 4500,
                'instrument': 'ES', 'account': 'Test', 'commission': 2
            }
        ]
        
        flows = calculate_running_quantity(invalid_executions)
        # Manually set previous_quantity to simulate invalid state
        flows[0].previous_quantity = 5
        
        errors = validate_position_boundaries(flows)
        self.assertGreater(len(errors), 0)
        self.assertIn('does not start from zero', errors[0])
    
    def test_aggregate_position_statistics(self):
        """Test position statistics aggregation"""
        positions_data = [
            {'net_pnl': 100.0},
            {'net_pnl': -50.0},
            {'net_pnl': 200.0},
            {'net_pnl': -25.0}
        ]
        
        stats = aggregate_position_statistics(positions_data)
        
        self.assertEqual(stats['total_positions'], 4)
        self.assertEqual(stats['winning_positions'], 2)
        self.assertEqual(stats['losing_positions'], 2)
        self.assertEqual(stats['total_pnl'], 225.0)
        self.assertEqual(stats['win_rate'], 50.0)
        self.assertEqual(stats['avg_win'], 150.0)
        self.assertEqual(stats['avg_loss'], -37.5)
        self.assertEqual(stats['largest_win'], 200.0)
        self.assertEqual(stats['largest_loss'], -50.0)
    
    def test_create_position_summary(self):
        """Test comprehensive position summary creation"""
        flows = calculate_running_quantity(self.sample_executions)
        pnl = calculate_position_pnl(flows, Decimal('50'))
        summary = create_position_summary(flows, pnl)
        
        self.assertNotIn('error', summary)
        self.assertEqual(summary['instrument'], 'ES 03-24')
        self.assertEqual(summary['account'], 'Sim101')
        self.assertEqual(summary['status'], 'closed')
        self.assertEqual(summary['execution_count'], 2)
        self.assertEqual(summary['position_type'], 'Long')
        self.assertIn('flows', summary)
        self.assertEqual(len(summary['flows']), 2)
    
    def test_empty_executions(self):
        """Test handling of empty execution lists"""
        flows = calculate_running_quantity([])
        self.assertEqual(len(flows), 0)
        
        positions = group_executions_by_position([])
        self.assertEqual(len(positions), 0)
        
        stats = aggregate_position_statistics([])
        self.assertEqual(stats['total_positions'], 0)


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)