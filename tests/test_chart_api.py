"""
Tests for Chart Data API endpoints
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime
from app import app

class TestChartAPI:
    """Test chart data API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def sample_ohlc_data(self):
        """Sample OHLC data for testing"""
        return [
            {
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': 1640995200,  # 2022-01-01 00:00:00
                'open_price': 100.0,
                'high_price': 101.0,
                'low_price': 99.0,
                'close_price': 100.5,
                'volume': 1000
            },
            {
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': 1640995260,  # 2022-01-01 00:01:00
                'open_price': 100.5,
                'high_price': 102.0,
                'low_price': 100.0,
                'close_price': 101.5,
                'volume': 1200
            }
        ]
    
    @patch('routes.chart_data.ohlc_service')
    def test_get_chart_data_success(self, mock_service, client, sample_ohlc_data):
        """Test successful chart data retrieval"""
        mock_service.get_chart_data.return_value = sample_ohlc_data
        
        response = client.get('/api/chart-data/MNQ?timeframe=1m&days=1')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] == True
        assert data['instrument'] == 'MNQ'
        assert data['timeframe'] == '1m'
        assert data['count'] == 2
        assert len(data['data']) == 2
        
        # Check data format for TradingView
        chart_point = data['data'][0]
        assert 'time' in chart_point
        assert 'open' in chart_point
        assert 'high' in chart_point
        assert 'low' in chart_point
        assert 'close' in chart_point
        assert 'volume' in chart_point
        
        assert chart_point['time'] == 1640995200
        assert chart_point['open'] == 100.0
        assert chart_point['high'] == 101.0
        assert chart_point['low'] == 99.0
        assert chart_point['close'] == 100.5
        assert chart_point['volume'] == 1000
    
    @patch('routes.chart_data.ohlc_service')
    def test_get_chart_data_with_parameters(self, mock_service, client):
        """Test chart data API with different parameters"""
        mock_service.get_chart_data.return_value = []
        
        # Test with custom timeframe and days
        response = client.get('/api/chart-data/ES?timeframe=5m&days=7')
        
        assert response.status_code == 200
        mock_service.get_chart_data.assert_called_once()
        
        # Check the call arguments
        call_args = mock_service.get_chart_data.call_args
        assert call_args[0][0] == 'ES'  # instrument
        assert call_args[0][1] == '5m'  # timeframe
        # call_args[0][2] and [3] are start_date and end_date (datetime objects)
        
        # Test default parameters
        mock_service.get_chart_data.reset_mock()
        response = client.get('/api/chart-data/MNQ')
        
        call_args = mock_service.get_chart_data.call_args
        assert call_args[0][0] == 'MNQ'
        assert call_args[0][1] == '1m'  # default timeframe
    
    @patch('routes.chart_data.ohlc_service')
    def test_get_chart_data_service_error(self, mock_service, client):
        """Test chart data API when service raises exception"""
        mock_service.get_chart_data.side_effect = Exception("Service error")
        
        response = client.get('/api/chart-data/MNQ')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'error' in data
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_trade_markers_success(self, mock_db_class, client):
        """Test successful trade markers retrieval"""
        # Setup mock database
        mock_db = Mock()
        mock_trade = {
            'id': 123,
            'entry_time': '2022-01-01T10:00:00',
            'entry_price': 100.0,
            'exit_time': '2022-01-01T11:00:00',
            'exit_price': 102.0,
            'side_of_market': 'Long',
            'dollars_gain_loss': 50.0
        }
        mock_db.get_trade.return_value = mock_trade
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/trade-markers/123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] == True
        assert data['trade_id'] == 123
        assert len(data['markers']) == 2  # Entry and exit markers
        
        # Check entry marker
        entry_marker = data['markers'][0]
        assert entry_marker['position'] == 'belowBar'
        assert entry_marker['color'] == '#2196F3'  # Blue for long
        assert entry_marker['shape'] == 'arrowUp'
        assert 'Entry: 100.0' in entry_marker['text']
        
        # Check exit marker
        exit_marker = data['markers'][1]
        assert exit_marker['position'] == 'aboveBar'
        assert exit_marker['color'] == '#4CAF50'  # Green for profit
        assert exit_marker['shape'] == 'arrowDown'
        assert 'Exit: 102.0' in exit_marker['text']
        assert '$50.00' in exit_marker['text']
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_trade_markers_short_trade(self, mock_db_class, client):
        """Test trade markers for short trade"""
        mock_db = Mock()
        mock_trade = {
            'id': 124,
            'entry_time': '2022-01-01T10:00:00',
            'entry_price': 100.0,
            'exit_time': '2022-01-01T11:00:00',
            'exit_price': 98.0,
            'side_of_market': 'Short',
            'dollars_gain_loss': 50.0
        }
        mock_db.get_trade.return_value = mock_trade
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/trade-markers/124')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check short entry marker
        entry_marker = data['markers'][0]
        assert entry_marker['color'] == '#F44336'  # Red for short
        assert entry_marker['shape'] == 'arrowDown'
        
        # Check short exit marker
        exit_marker = data['markers'][1]
        assert exit_marker['shape'] == 'arrowUp'
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_trade_markers_loss_trade(self, mock_db_class, client):
        """Test trade markers for losing trade"""
        mock_db = Mock()
        mock_trade = {
            'id': 125,
            'entry_time': '2022-01-01T10:00:00',
            'entry_price': 100.0,
            'exit_time': '2022-01-01T11:00:00',
            'exit_price': 98.0,
            'side_of_market': 'Long',
            'dollars_gain_loss': -50.0
        }
        mock_db.get_trade.return_value = mock_trade
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/trade-markers/125')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check exit marker for loss
        exit_marker = data['markers'][1]
        assert exit_marker['color'] == '#F44336'  # Red for loss
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_trade_markers_not_found(self, mock_db_class, client):
        """Test trade markers when trade not found"""
        mock_db = Mock()
        mock_db.get_trade.return_value = None
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/trade-markers/999')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] == False
        assert data['error'] == 'Trade not found'
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_trade_markers_partial_data(self, mock_db_class, client):
        """Test trade markers with partial trade data"""
        mock_db = Mock()
        mock_trade = {
            'id': 126,
            'entry_time': '2022-01-01T10:00:00',
            'entry_price': 100.0,
            'exit_time': None,  # No exit yet
            'exit_price': None,
            'side_of_market': 'Long',
            'dollars_gain_loss': None
        }
        mock_db.get_trade.return_value = mock_trade
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/trade-markers/126')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] == True
        assert len(data['markers']) == 1  # Only entry marker
        
        entry_marker = data['markers'][0]
        assert 'Entry: 100.0' in entry_marker['text']
    
    @patch('routes.chart_data.ohlc_service')
    def test_update_instrument_data_success(self, mock_service, client):
        """Test successful instrument data update"""
        mock_service.update_recent_data.return_value = True
        
        with patch('routes.chart_data.FuturesDB') as mock_db_class:
            mock_db = Mock()
            mock_db.get_ohlc_count.return_value = 5000
            mock_db_class.return_value.__enter__.return_value = mock_db
            
            response = client.get('/api/update-data/MNQ')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] == True
            assert 'Updated data for MNQ' in data['message']
            assert data['total_records'] == 5000
            
            # Verify service was called with default timeframes
            mock_service.update_recent_data.assert_called_once_with('MNQ', ['1m', '5m', '15m', '1h', '4h', '1d'])
    
    @patch('routes.chart_data.ohlc_service')
    def test_update_instrument_data_custom_timeframes(self, mock_service, client):
        """Test instrument data update with custom timeframes"""
        mock_service.update_recent_data.return_value = True
        
        with patch('routes.chart_data.FuturesDB') as mock_db_class:
            mock_db = Mock()
            mock_db.get_ohlc_count.return_value = 2000
            mock_db_class.return_value.__enter__.return_value = mock_db
            
            response = client.get('/api/update-data/ES?timeframes=1m&timeframes=5m')
            
            assert response.status_code == 200
            
            # Verify service was called with custom timeframes
            mock_service.update_recent_data.assert_called_once_with('ES', ['1m', '5m'])
    
    @patch('routes.chart_data.ohlc_service')
    def test_update_instrument_data_failure(self, mock_service, client):
        """Test instrument data update failure"""
        mock_service.update_recent_data.return_value = False
        
        response = client.get('/api/update-data/MNQ')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] == False
        assert data['error'] == 'Failed to update data'
    
    @patch('routes.chart_data.FuturesDB')
    def test_get_available_instruments(self, mock_db_class, client):
        """Test getting list of available instruments"""
        mock_db = Mock()
        mock_db.cursor = Mock()
        mock_db.cursor.fetchall.return_value = [('MNQ',), ('ES',), ('YM',), ('RTY',)]
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/api/instruments')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] == True
        assert len(data['instruments']) == 4
        assert 'MNQ' in data['instruments']
        assert 'ES' in data['instruments']
        
        # Verify SQL query was executed
        mock_db.cursor.execute.assert_called_once()
        sql_query = mock_db.cursor.execute.call_args[0][0]
        assert 'DISTINCT instrument' in sql_query
        assert 'UNION' in sql_query  # Should query both trades and ohlc_data tables
    
    @patch('routes.chart_data.FuturesDB')
    def test_chart_page_render(self, mock_db_class, client):
        """Test chart page rendering"""
        mock_db = Mock()
        mock_db.get_trades.return_value = [
            {
                'id': 1,
                'instrument': 'MNQ',
                'side_of_market': 'Long',
                'entry_price': 100.0,
                'dollars_gain_loss': 50.0
            }
        ]
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        response = client.get('/chart/MNQ')
        
        assert response.status_code == 200
        assert b'MNQ' in response.data
        assert b'chart' in response.data.lower()
        
        # Verify database query for recent trades
        mock_db.get_trades.assert_called_once_with(filters={'instrument': 'MNQ'}, limit=10)
    
    def test_chart_data_api_endpoints_exist(self, client):
        """Test that all chart API endpoints exist"""
        endpoints = [
            '/api/chart-data/MNQ',
            '/api/trade-markers/1', 
            '/api/update-data/MNQ',
            '/api/instruments',
            '/chart/MNQ'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not return 404 (endpoint exists)
            assert response.status_code != 404, f"Endpoint {endpoint} should exist"
    
    @patch('routes.chart_data.ohlc_service')
    def test_chart_data_volume_handling(self, mock_service, client):
        """Test chart data API handles missing volume correctly"""
        data_with_none_volume = [
            {
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': 1640995200,
                'open_price': 100.0,
                'high_price': 101.0,
                'low_price': 99.0,
                'close_price': 100.5,
                'volume': None  # None volume
            }
        ]
        mock_service.get_chart_data.return_value = data_with_none_volume
        
        response = client.get('/api/chart-data/MNQ')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        chart_point = data['data'][0]
        assert chart_point['volume'] == 0  # Should convert None to 0