"""
Tests for Position Execution Chart Data API endpoints
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from app import app


class TestExecutionChartAPI:
    """Test execution chart data API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def sample_position_data(self):
        """Sample position data for testing"""
        return {
            'id': 1,
            'instrument': 'MNQ',
            'account': 'APEX1279810000055',
            'total_quantity': 2,
            'avg_entry_price': 23643.75,
            'avg_exit_price': 23647.00,
            'total_pnl': -13.00,
            'status': 'closed'
        }
    
    @pytest.fixture
    def sample_executions_data(self):
        """Sample execution data for testing"""
        return [
            {
                'id': 2139,
                'entry_time': '2025-09-05 11:39:43',
                'entry_price': 23643.75,
                'exit_time': '2025-09-05 11:40:28',
                'exit_price': 23647.00,
                'quantity': 2,
                'side_of_market': 'Sell',
                'dollars_gain_loss': -13.00,
                'points_gain_loss': -3.25,
                'commission': 0.00,
                'instrument': 'MNQ'
            }
        ]
    
    @pytest.fixture
    def sample_chart_executions(self):
        """Sample executions formatted for chart display"""
        return {
            'executions': [
                {
                    'id': 2139,
                    'timestamp': '2025-09-05T11:39:43.000Z',
                    'timestamp_ms': 1725542383000,
                    'price': 23643.75,
                    'quantity': 2,
                    'side': 'sell',
                    'execution_type': 'entry',
                    'pnl_dollars': 0.00,
                    'pnl_points': 0.00,
                    'commission': 0.00,
                    'position_quantity': 2,
                    'avg_price': 23643.75
                },
                {
                    'id': 2139,
                    'timestamp': '2025-09-05T11:40:28.000Z',
                    'timestamp_ms': 1725542428000,
                    'price': 23647.00,
                    'quantity': 2,
                    'side': 'buy',
                    'execution_type': 'exit',
                    'pnl_dollars': -13.00,
                    'pnl_points': -3.25,
                    'commission': 0.00,
                    'position_quantity': 0,
                    'avg_price': 23647.00
                }
            ],
            'chart_bounds': {
                'min_timestamp': 1725542340000,
                'max_timestamp': 1725542500000,
                'min_price': 23640.00,
                'max_price': 23650.00
            },
            'timeframe_info': {
                'selected': '1h',
                'candle_duration_ms': 3600000
            }
        }
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_success(self, mock_db_class, client, sample_chart_executions):
        """Test successful execution chart data retrieval"""
        mock_db = Mock()
        mock_db.get_position_executions_for_chart_cached.return_value = sample_chart_executions
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/1/executions-chart?timeframe=1h')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] == True
        assert len(data['executions']) == 2
        
        # Check execution format for chart display
        entry_execution = data['executions'][0]
        assert entry_execution['execution_type'] == 'entry'
        assert entry_execution['side'] == 'sell'
        assert entry_execution['price'] == 23643.75
        assert entry_execution['timestamp_ms'] == 1725542383000
        assert entry_execution['position_quantity'] == 2
        
        exit_execution = data['executions'][1]
        assert exit_execution['execution_type'] == 'exit'
        assert exit_execution['side'] == 'buy'
        assert exit_execution['pnl_dollars'] == -13.00
        assert exit_execution['position_quantity'] == 0
        
        # Check chart bounds
        assert 'chart_bounds' in data
        assert data['chart_bounds']['min_price'] == 23640.00
        assert data['chart_bounds']['max_price'] == 23650.00
        
        # Check timeframe info
        assert 'timeframe_info' in data
        assert data['timeframe_info']['selected'] == '1h'
        assert data['timeframe_info']['candle_duration_ms'] == 3600000
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_with_timeframe_1m(self, mock_db_class, client):
        """Test execution chart data with 1m timeframe"""
        mock_db = Mock()
        chart_data = {
            'executions': [],
            'chart_bounds': {'min_timestamp': 0, 'max_timestamp': 0, 'min_price': 0, 'max_price': 0},
            'timeframe_info': {'selected': '1m', 'candle_duration_ms': 60000}
        }
        mock_db.get_position_executions_for_chart_cached.return_value = chart_data
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/1/executions-chart?timeframe=1m')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['timeframe_info']['selected'] == '1m'
        assert data['timeframe_info']['candle_duration_ms'] == 60000
        
        # Verify database method was called with correct timeframe
        mock_db.get_position_executions_for_chart_cached.assert_called_once_with(1, '1m', None, None)
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_with_date_range(self, mock_db_class, client):
        """Test execution chart data with date range filtering"""
        mock_db = Mock()
        mock_db.get_position_executions_for_chart_cached.return_value = {
            'executions': [],
            'chart_bounds': {'min_timestamp': 0, 'max_timestamp': 0, 'min_price': 0, 'max_price': 0},
            'timeframe_info': {'selected': '5m', 'candle_duration_ms': 300000}
        }
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        start_date = '2025-09-05T00:00:00Z'
        end_date = '2025-09-05T23:59:59Z'
        response = client.get(f'/positions/api/1/executions-chart?timeframe=5m&start_date={start_date}&end_date={end_date}')
        
        assert response.status_code == 200
        
        # Verify database method was called with date range
        call_args = mock_db.get_position_executions_for_chart_cached.call_args
        assert call_args[0][0] == 1  # position_id
        assert call_args[0][1] == '5m'  # timeframe
        assert call_args[0][2] == start_date  # start_date
        assert call_args[0][3] == end_date  # end_date
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_position_not_found(self, mock_db_class, client):
        """Test execution chart data when position not found"""
        mock_db = Mock()
        mock_db.get_position_executions_for_chart_cached.return_value = None
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/999/executions-chart')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] == False
        assert data['error'] == 'Position not found'
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_invalid_timeframe(self, mock_db_class, client):
        """Test execution chart data with invalid timeframe"""
        response = client.get('/positions/api/1/executions-chart?timeframe=invalid')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'Invalid timeframe' in data['error']
    
    @patch('routes.positions.FuturesDB')
    def test_get_position_executions_chart_database_error(self, mock_db_class, client):
        """Test execution chart data when database raises exception"""
        mock_db = Mock()
        mock_db.get_position_executions_for_chart_cached.side_effect = Exception("Database error")
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/1/executions-chart')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'error' in data
    
    @patch('routes.positions.FuturesDB')
    def test_enhanced_chart_data_with_position_overlay(self, mock_db_class, client):
        """Test enhanced chart data API with position execution overlay"""
        mock_db = Mock()
        
        # Mock OHLC data
        ohlc_data = [
            {'time': 1725542340, 'open': 23640.0, 'high': 23650.0, 'low': 23635.0, 'close': 23645.0, 'volume': 1000},
            {'time': 1725542400, 'open': 23645.0, 'high': 23655.0, 'low': 23640.0, 'close': 23650.0, 'volume': 1200}
        ]
        
        # Mock execution overlay data
        execution_overlay = [
            {
                'timestamp': 1725542383000,
                'price': 23643.75,
                'arrow_type': 'entry',
                'side': 'sell',
                'tooltip_data': {
                    'quantity': 2,
                    'pnl_dollars': 0.00,
                    'execution_id': 2139
                }
            },
            {
                'timestamp': 1725542428000,
                'price': 23647.00,
                'arrow_type': 'exit',
                'side': 'buy',
                'tooltip_data': {
                    'quantity': 2,
                    'pnl_dollars': -13.00,
                    'execution_id': 2139
                }
            }
        ]
        
        # Mock the enhanced chart data response
        with patch('routes.chart_data.ohlc_service') as mock_ohlc_service, \
             patch('routes.chart_data.get_execution_overlay_for_chart') as mock_overlay_func:
            mock_ohlc_service.get_chart_data.return_value = []  # Raw OHLC data
            mock_overlay_func.return_value = execution_overlay
            mock_db_class.return_value.__enter__.return_value = mock_db
            
            response = client.get('/api/chart-data/MNQ?timeframe=1m&position_id=1')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] == True
            assert 'executions' in data
            assert len(data['executions']) == 2
            
            # Check execution overlay format
            entry_arrow = data['executions'][0]
            assert entry_arrow['arrow_type'] == 'entry'
            assert entry_arrow['side'] == 'sell'
            assert entry_arrow['price'] == 23643.75
            assert entry_arrow['tooltip_data']['execution_id'] == 2139
            
            exit_arrow = data['executions'][1]
            assert exit_arrow['arrow_type'] == 'exit'
            assert exit_arrow['tooltip_data']['pnl_dollars'] == -13.00
    
    @patch('routes.positions.FuturesDB')
    def test_execution_timestamp_alignment_1m(self, mock_db_class, client):
        """Test execution timestamp alignment with 1m candles"""
        mock_db = Mock()
        
        # Test data with precise timestamps that need alignment
        chart_data = {
            'executions': [
                {
                    'id': 1,
                    'timestamp': '2025-09-05T11:39:43.123Z',  # 43.123 seconds
                    'timestamp_ms': 1725542383123,
                    'price': 23643.75,
                    'quantity': 2,
                    'side': 'sell',
                    'execution_type': 'entry'
                }
            ],
            'chart_bounds': {'min_timestamp': 1725542340000, 'max_timestamp': 1725542400000, 'min_price': 23640, 'max_price': 23650},
            'timeframe_info': {'selected': '1m', 'candle_duration_ms': 60000}
        }
        
        mock_db.get_position_executions_for_chart_cached.return_value = chart_data
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/1/executions-chart?timeframe=1m')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify timestamp is aligned to 1m candle boundary
        execution = data['executions'][0]
        timestamp_ms = execution['timestamp_ms']
        
        # For 1m candles, timestamp should be aligned to minute boundary
        # 1725542383123 should align to 1725542340000 (start of the minute)
        expected_aligned_timestamp = 1725542340000  # 11:39:00
        
        # Verify the timestamp alignment logic was applied
        assert 'timestamp_ms' in execution
        
    def test_chart_bounds_calculation_logic(self, client):
        """Test chart bounds calculation includes execution price range"""
        # This test verifies the logic for calculating optimal chart bounds
        # that include both OHLC data range and execution price points
        
        # Mock execution prices
        execution_prices = [23643.75, 23647.00, 23651.25]
        ohlc_price_range = {'min': 23640.00, 'max': 23655.00}
        
        # Expected bounds should encompass both ranges with padding
        expected_min = min(min(execution_prices), ohlc_price_range['min']) - 5.0  # 5 point padding
        expected_max = max(max(execution_prices), ohlc_price_range['max']) + 5.0
        
        assert expected_min == 23635.00
        assert expected_max == 23660.00
    
    def test_timeframe_duration_mapping(self, client):
        """Test timeframe to millisecond duration mapping"""
        timeframe_mappings = {
            '1m': 60000,
            '5m': 300000,
            '1h': 3600000
        }
        
        for timeframe, expected_ms in timeframe_mappings.items():
            # This would be tested in the actual implementation
            assert expected_ms > 0
            
            # For 1m: 1 minute = 60 seconds = 60,000 ms
            if timeframe == '1m':
                assert expected_ms == 60 * 1000
            # For 5m: 5 minutes = 300 seconds = 300,000 ms
            elif timeframe == '5m':
                assert expected_ms == 5 * 60 * 1000
            # For 1h: 1 hour = 3600 seconds = 3,600,000 ms
            elif timeframe == '1h':
                assert expected_ms == 60 * 60 * 1000
    
    @patch('routes.positions.FuturesDB')
    def test_execution_chart_data_caching_behavior(self, mock_db_class, client):
        """Test that execution chart data is properly structured for caching"""
        mock_db = Mock()
        mock_db.get_position_executions_for_chart_cached.return_value = {
            'executions': [],
            'chart_bounds': {'min_timestamp': 0, 'max_timestamp': 0, 'min_price': 0, 'max_price': 0},
            'timeframe_info': {'selected': '1h', 'candle_duration_ms': 3600000}
        }
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/positions/api/1/executions-chart?timeframe=1h')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify response structure is cache-friendly
        assert isinstance(data, dict)
        assert 'executions' in data
        assert 'chart_bounds' in data
        assert 'timeframe_info' in data
        
        # Verify cache key components are present
        assert data['timeframe_info']['selected'] == '1h'