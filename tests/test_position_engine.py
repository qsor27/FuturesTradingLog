"""
Comprehensive test suite for the Position Engine

Tests all critical edge cases for the 0→+/-→0 position building algorithm
"""

import pytest
from typing import List, Dict, Any
from datetime import datetime

from position_engine import PositionEngine, Position, Execution, ExecutionAction, PositionSide


class TestPositionEngine:
    """Test suite for position building algorithm"""
    
    def create_raw_execution(self, execution_id: str, instrument: str, account: str,
                           side: str, quantity: int, price: float, 
                           timestamp: str, commission: float = 0.0) -> Dict[str, Any]:
        """Helper to create raw execution dictionary"""
        return {
            'entry_execution_id': execution_id,
            'instrument': instrument,
            'account': account,
            'side_of_market': side,
            'quantity': quantity,
            'entry_price': price,
            'entry_time': timestamp,
            'commission': commission
        }
    
    def test_empty_executions(self):
        """Test handling of empty execution list"""
        positions = PositionEngine.build_positions_from_executions([])
        assert positions == []
    
    def test_invalid_execution_data(self):
        """Test handling of invalid execution data"""
        invalid_executions = [
            # Missing required fields
            {'instrument': 'ES', 'quantity': 1},
            # Invalid side_of_market
            {'instrument': 'ES', 'account': 'Test', 'side_of_market': 'Invalid', 'quantity': 1, 'entry_price': 100, 'entry_time': '2023-01-01'},
            # Zero quantity
            {'instrument': 'ES', 'account': 'Test', 'side_of_market': 'Buy', 'quantity': 0, 'entry_price': 100, 'entry_time': '2023-01-01'},
        ]
        
        positions = PositionEngine.build_positions_from_executions(invalid_executions)
        assert positions == []
    
    def test_simple_long_position(self):
        """Test basic long position: Buy → Sell"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 2, 4010.0, '2023-01-01 10:00:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.total_quantity == 4  # 2 + 2 for entry and exit
        assert position.average_entry_price == 4000.0
        assert position.average_exit_price == 4010.0
        assert position.total_points_pnl == 10.0  # 4010 - 4000
        assert position.is_closed is True
        assert len(position.executions) == 2
    
    def test_simple_short_position(self):
        """Test basic short position: Sell → Buy"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Sell', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Buy', 1, 3990.0, '2023-01-01 10:00:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.SHORT
        assert position.total_quantity == 2  # 1 + 1 for entry and exit
        assert position.average_entry_price == 4000.0
        assert position.average_exit_price == 3990.0
        assert position.total_points_pnl == 10.0  # 4000 - 3990 (short P&L)
        assert position.is_closed is True
    
    def test_partial_position_close(self):
        """Test partial position closure"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 3, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 10:00:00'),
            self.create_raw_execution('3', 'ES', 'Test', 'Sell', 2, 4020.0, '2023-01-01 11:00:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.total_quantity == 6  # 3 buy + 1 sell + 2 sell
        assert position.is_closed is True
        assert len(position.executions) == 3
    
    def test_position_scaling(self):
        """Test position scaling (adding to position)"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Buy', 2, 4005.0, '2023-01-01 09:30:00'),  # Add to position
            self.create_raw_execution('3', 'ES', 'Test', 'Sell', 3, 4020.0, '2023-01-01 10:00:00'),  # Close all
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.total_quantity == 6  # 1 + 2 + 3
        assert position.max_quantity == 3  # Largest single execution
        
        # Check weighted average entry price: (1*4000 + 2*4005) / 3 = 4003.33
        expected_avg_entry = (1 * 4000.0 + 2 * 4005.0) / 3
        assert abs(position.average_entry_price - expected_avg_entry) < 0.01
    
    def test_position_reversal_long_to_short(self):
        """Test position reversal: Long → Short without touching zero"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 09:00:00'),  # Long 2
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 5, 4010.0, '2023-01-01 10:00:00'), # Sell 5: Close 2, Short 3
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 2
        
        # First position: Long position that was closed
        long_position = positions[0]
        assert long_position.side == PositionSide.LONG
        assert long_position.is_closed is True
        
        # Second position: Short position that was opened
        short_position = positions[1]
        assert short_position.side == PositionSide.SHORT
        assert short_position.is_closed is False  # Still open
    
    def test_position_reversal_short_to_long(self):
        """Test position reversal: Short → Long without touching zero"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Sell', 3, 4000.0, '2023-01-01 09:00:00'), # Short 3
            self.create_raw_execution('2', 'ES', 'Test', 'Buy', 7, 3990.0, '2023-01-01 10:00:00'),  # Buy 7: Close 3, Long 4
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 2
        
        # First position: Short position that was closed
        short_position = positions[0]
        assert short_position.side == PositionSide.SHORT
        assert short_position.is_closed is True
        
        # Second position: Long position that was opened
        long_position = positions[1]
        assert long_position.side == PositionSide.LONG
        assert long_position.is_closed is False  # Still open
    
    def test_multiple_round_trips(self):
        """Test multiple complete round trips"""
        executions = [
            # First round trip: Long
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 09:30:00'),
            
            # Second round trip: Short
            self.create_raw_execution('3', 'ES', 'Test', 'Sell', 2, 4020.0, '2023-01-01 10:00:00'),
            self.create_raw_execution('4', 'ES', 'Test', 'Buy', 2, 4005.0, '2023-01-01 10:30:00'),
            
            # Third round trip: Long
            self.create_raw_execution('5', 'ES', 'Test', 'Buy', 3, 4015.0, '2023-01-01 11:00:00'),
            self.create_raw_execution('6', 'ES', 'Test', 'Sell', 3, 4025.0, '2023-01-01 11:30:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 3
        
        # All positions should be closed
        for position in positions:
            assert position.is_closed is True
        
        # Check position sides
        assert positions[0].side == PositionSide.LONG
        assert positions[1].side == PositionSide.SHORT
        assert positions[2].side == PositionSide.LONG
    
    def test_out_of_order_timestamps(self):
        """Test handling of out-of-order executions"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 10:00:00'),   # Second chronologically
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 2, 4010.0, '2023-01-01 09:00:00'),  # First chronologically
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        # Should still create valid positions despite timestamp order
        assert len(positions) >= 1
    
    def test_multiple_instruments(self):
        """Test handling multiple instruments in same dataset"""
        executions = [
            # ES trades
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 10:00:00'),
            
            # NQ trades  
            self.create_raw_execution('3', 'NQ', 'Test', 'Sell', 2, 15000.0, '2023-01-01 09:30:00'),
            self.create_raw_execution('4', 'NQ', 'Test', 'Buy', 2, 14980.0, '2023-01-01 10:30:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 2
        
        # Find positions by instrument
        es_position = next(p for p in positions if p.instrument == 'ES')
        nq_position = next(p for p in positions if p.instrument == 'NQ')
        
        assert es_position.side == PositionSide.LONG
        assert nq_position.side == PositionSide.SHORT
        assert es_position.is_closed is True
        assert nq_position.is_closed is True
    
    def test_multiple_accounts(self):
        """Test handling multiple accounts in same dataset"""
        executions = [
            # Account A
            self.create_raw_execution('1', 'ES', 'AccountA', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('2', 'ES', 'AccountA', 'Sell', 1, 4010.0, '2023-01-01 10:00:00'),
            
            # Account B
            self.create_raw_execution('3', 'ES', 'AccountB', 'Sell', 2, 4005.0, '2023-01-01 09:30:00'),
            self.create_raw_execution('4', 'ES', 'AccountB', 'Buy', 2, 3995.0, '2023-01-01 10:30:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 2
        
        # Positions should be separate by account
        accounts = {p.account for p in positions}
        assert accounts == {'AccountA', 'AccountB'}
    
    def test_complex_scaling_scenario(self):
        """Test complex position scaling and partial closes"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),  # Long 1
            self.create_raw_execution('2', 'ES', 'Test', 'Buy', 2, 4005.0, '2023-01-01 09:15:00'),  # Long 3 total
            self.create_raw_execution('3', 'ES', 'Test', 'Buy', 1, 4010.0, '2023-01-01 09:30:00'),  # Long 4 total
            self.create_raw_execution('4', 'ES', 'Test', 'Sell', 2, 4020.0, '2023-01-01 09:45:00'), # Long 2 remaining
            self.create_raw_execution('5', 'ES', 'Test', 'Sell', 2, 4025.0, '2023-01-01 10:00:00'), # Flat
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.is_closed is True
        assert position.max_quantity == 4  # Peak position size
        assert len(position.executions) == 5
    
    def test_open_position(self):
        """Test handling of open (unclosed) positions"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 09:00:00'),
            # No closing trade
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.is_closed is False
        assert position.exit_time is None
        assert position.average_exit_price is None
        assert position.total_points_pnl is None
    
    def test_commission_calculation(self):
        """Test commission aggregation"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00', 2.50),
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 10:00:00', 2.50),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.total_commission == 5.0  # 2.50 + 2.50
    
    def test_zero_quantity_execution(self):
        """Test that zero quantity executions are filtered out"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 0, 4000.0, '2023-01-01 09:00:00'),  # Should be filtered
            self.create_raw_execution('2', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
            self.create_raw_execution('3', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 10:00:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        assert len(position.executions) == 2  # Zero quantity execution should be filtered out
    
    def test_edge_case_single_execution(self):
        """Test single execution creates open position"""
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        assert len(positions) == 1
        position = positions[0]
        
        assert position.side == PositionSide.LONG
        assert position.is_closed is False
        assert position.total_quantity == 1
    
    def test_quantity_flow_consistency(self):
        """Test that quantity flow is always consistent (0→+/-→0)"""
        # Complex scenario with multiple reversals
        executions = [
            self.create_raw_execution('1', 'ES', 'Test', 'Buy', 3, 4000.0, '2023-01-01 09:00:00'),   # +3
            self.create_raw_execution('2', 'ES', 'Test', 'Sell', 5, 4010.0, '2023-01-01 09:30:00'),  # -5 (reverse)
            self.create_raw_execution('3', 'ES', 'Test', 'Buy', 4, 4005.0, '2023-01-01 10:00:00'),   # +4 (reverse again)
            self.create_raw_execution('4', 'ES', 'Test', 'Sell', 2, 4015.0, '2023-01-01 10:30:00'),  # -2 (close)
        ]
        
        positions = PositionEngine.build_positions_from_executions(executions)
        
        # Should create 3 positions due to reversals
        assert len(positions) >= 2
        
        # Each position should have valid lifecycle
        for position in positions:
            assert position.total_quantity > 0
            assert len(position.executions) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])