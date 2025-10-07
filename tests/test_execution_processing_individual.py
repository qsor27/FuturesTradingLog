"""
Test suite for ExecutionProcessing - Individual Execution Output Format

Tests verify that ExecutionProcessing outputs individual executions (Entry/Exit)
instead of pre-paired round-trip trades, enabling the position builder to perform
FIFO matching and calculate positions correctly.
"""
import pytest
import pandas as pd
from datetime import datetime
from scripts.ExecutionProcessing import process_trades


class TestIndividualExecutionOutput:
    """Test cases for individual execution output format"""

    @pytest.fixture
    def sample_executions_df(self):
        """
        Sample executions representing:
        - Account Sim101: Buy 1 Entry, Buy 1 Entry, Sell 2 Exit
        - Account Sim102: Sell 1 Entry, Buy 1 Exit
        """
        return pd.DataFrame({
            'ID': ['E001', 'E002', 'E003', 'E004', 'E005'],
            'Account': ['Sim101', 'Sim101', 'Sim101', 'Sim102', 'Sim102'],
            'Instrument': ['MES 12-24', 'MES 12-24', 'MES 12-24', 'MES 12-24', 'MES 12-24'],
            'Time': [
                '2024-10-01 09:30:00',
                '2024-10-01 09:31:00',
                '2024-10-01 09:32:00',
                '2024-10-01 09:30:00',
                '2024-10-01 09:31:00'
            ],
            'Action': ['Buy', 'Buy', 'Sell', 'Sell', 'Buy'],
            'E/X': ['Entry', 'Entry', 'Exit', 'Entry', 'Exit'],
            'Quantity': [1, 1, 2, 1, 1],
            'Price': [24992.00, 24992.00, 24988.00, 24992.00, 24988.00],
            'Commission': ['$1.24', '$1.24', '$2.48', '$1.24', '$1.24']
        })

    @pytest.fixture
    def multipliers(self):
        """Instrument multipliers for testing"""
        return {'MES': 5.0}

    def test_outputs_individual_executions(self, sample_executions_df, multipliers):
        """Test that process_trades outputs 5 individual executions, not paired trades"""
        result = process_trades(sample_executions_df, multipliers)

        # Should return 5 individual executions (one per CSV row)
        assert len(result) == 5, f"Expected 5 individual executions, got {len(result)}"

    def test_entry_execution_format(self, sample_executions_df, multipliers):
        """Test that Entry executions have correct format with exit_price=None"""
        result = process_trades(sample_executions_df, multipliers)

        # Find the first Entry execution (E001)
        entry_exec = next((r for r in result if r['execution_id'] == 'E001'), None)
        assert entry_exec is not None, "Entry execution E001 not found"

        # Verify Entry execution fields
        assert entry_exec['Account'] == 'Sim101'
        assert entry_exec['Instrument'] == 'MES 12-24'
        assert entry_exec['action'] == 'Buy'
        assert entry_exec['entry_exit'] == 'Entry'
        assert entry_exec['quantity'] == 1
        assert entry_exec['entry_price'] == 24992.00
        assert entry_exec['entry_time'] is not None
        assert entry_exec['exit_price'] is None, "Entry executions should have exit_price=None"
        assert entry_exec['exit_time'] is None, "Entry executions should have exit_time=None"
        assert entry_exec['commission'] == 1.24

    def test_exit_execution_format(self, sample_executions_df, multipliers):
        """Test that Exit executions are stored as individual records (not paired)"""
        result = process_trades(sample_executions_df, multipliers)

        # Find the first Exit execution (E003)
        exit_exec = next((r for r in result if r['execution_id'] == 'E003'), None)
        assert exit_exec is not None, "Exit execution E003 not found"

        # Verify Exit execution fields
        assert exit_exec['Account'] == 'Sim101'
        assert exit_exec['Instrument'] == 'MES 12-24'
        assert exit_exec['action'] == 'Sell'
        assert exit_exec['entry_exit'] == 'Exit'
        assert exit_exec['quantity'] == 2
        assert exit_exec['exit_price'] == 24988.00
        assert exit_exec['exit_time'] is not None
        # For exits stored as individual records, we don't pre-match entry_price
        # The position builder will handle FIFO matching
        assert exit_exec['entry_price'] is None or exit_exec['entry_price'] == 0.0
        assert exit_exec['commission'] == 2.48

    def test_account_separation(self, sample_executions_df, multipliers):
        """Test that executions maintain account separation"""
        result = process_trades(sample_executions_df, multipliers)

        # Count executions per account
        sim101_executions = [r for r in result if r['Account'] == 'Sim101']
        sim102_executions = [r for r in result if r['Account'] == 'Sim102']

        assert len(sim101_executions) == 3, f"Expected 3 executions for Sim101, got {len(sim101_executions)}"
        assert len(sim102_executions) == 2, f"Expected 2 executions for Sim102, got {len(sim102_executions)}"

    def test_execution_id_preservation(self, sample_executions_df, multipliers):
        """Test that original execution IDs are preserved"""
        result = process_trades(sample_executions_df, multipliers)

        execution_ids = [r['execution_id'] for r in result]
        expected_ids = ['E001', 'E002', 'E003', 'E004', 'E005']

        assert set(execution_ids) == set(expected_ids), \
            f"Expected IDs {expected_ids}, got {execution_ids}"

    def test_no_fifo_pairing_in_processing(self, sample_executions_df, multipliers):
        """Test that process_trades does NOT perform FIFO pairing"""
        result = process_trades(sample_executions_df, multipliers)

        # Verify that we don't have any pre-calculated P&L or matched trades
        # Each execution should be independent
        for execution in result:
            # Entry executions should not have exit information
            if execution['entry_exit'] == 'Entry':
                assert execution['exit_price'] is None
                assert execution['exit_time'] is None
                # No P&L calculation at this stage
                assert 'points_pnl' not in execution or execution['points_pnl'] is None
                assert 'dollars_pnl' not in execution or execution['dollars_pnl'] is None

    def test_chronological_ordering(self, sample_executions_df, multipliers):
        """Test that executions are ordered chronologically within each account"""
        result = process_trades(sample_executions_df, multipliers)

        # Check Sim101 executions are in time order
        sim101_executions = [r for r in result if r['Account'] == 'Sim101']
        sim101_times = [r['entry_time'] or r['exit_time'] for r in sim101_executions]

        # Verify chronological order
        for i in range(len(sim101_times) - 1):
            assert sim101_times[i] <= sim101_times[i+1], \
                f"Executions not in chronological order for Sim101"


class TestExecutionFieldMapping:
    """Test correct field mapping for individual execution records"""

    @pytest.fixture
    def single_entry_df(self):
        """Single entry execution"""
        return pd.DataFrame({
            'ID': ['E123'],
            'Account': ['Sim101'],
            'Instrument': ['MES 12-24'],
            'Time': ['2024-10-01 09:30:00'],
            'Action': ['Buy'],
            'E/X': ['Entry'],
            'Quantity': [2],
            'Price': [24992.50],
            'Commission': ['$2.48']
        })

    @pytest.fixture
    def single_exit_df(self):
        """Single exit execution"""
        return pd.DataFrame({
            'ID': ['E456'],
            'Account': ['Sim101'],
            'Instrument': ['MES 12-24'],
            'Time': ['2024-10-01 09:35:00'],
            'Action': ['Sell'],
            'E/X': ['Exit'],
            'Quantity': [2],
            'Price': [24995.00],
            'Commission': ['$2.48']
        })

    def test_entry_field_mapping(self, single_entry_df):
        """Test field mapping for entry execution"""
        result = process_trades(single_entry_df, {'MES': 5.0})

        assert len(result) == 1
        entry = result[0]

        # Required fields for Entry execution
        assert entry['execution_id'] == 'E123'
        assert entry['Account'] == 'Sim101'
        assert entry['Instrument'] == 'MES 12-24'
        assert entry['action'] == 'Buy'
        assert entry['entry_exit'] == 'Entry'
        assert entry['quantity'] == 2
        assert entry['entry_price'] == 24992.50
        assert entry['exit_price'] is None
        assert entry['commission'] == 2.48

        # Verify timestamp is parsed correctly
        expected_time = pd.to_datetime('2024-10-01 09:30:00')
        actual_time = entry['entry_time']
        assert actual_time == expected_time

    def test_exit_field_mapping(self, single_exit_df):
        """Test field mapping for exit execution"""
        result = process_trades(single_exit_df, {'MES': 5.0})

        assert len(result) == 1
        exit_exec = result[0]

        # Required fields for Exit execution
        assert exit_exec['execution_id'] == 'E456'
        assert exit_exec['Account'] == 'Sim101'
        assert exit_exec['Instrument'] == 'MES 12-24'
        assert exit_exec['action'] == 'Sell'
        assert exit_exec['entry_exit'] == 'Exit'
        assert exit_exec['quantity'] == 2
        assert exit_exec['exit_price'] == 24995.00
        assert exit_exec['entry_price'] is None or exit_exec['entry_price'] == 0.0
        assert exit_exec['commission'] == 2.48

        # Verify timestamp is parsed correctly
        expected_time = pd.to_datetime('2024-10-01 09:35:00')
        actual_time = exit_exec['exit_time']
        assert actual_time == expected_time
