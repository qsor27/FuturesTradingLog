"""
Tests for Performance API endpoints
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime, date
from app import app

class TestPerformanceAPI:
    """Test performance API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def sample_daily_performance(self):
        """Sample daily performance data for testing"""
        return {
            'daily_pnl': 1250.50,
            'total_trades': 8,
            'winning_trades': 5,
            'losing_trades': 3,
            'date': '2025-09-09'
        }
    
    @pytest.fixture
    def sample_weekly_performance(self):
        """Sample weekly performance data for testing"""
        return {
            'weekly_pnl': 4750.25,
            'total_trades': 32,
            'winning_trades': 20,
            'losing_trades': 12,
            'week_start': '2025-09-09',
            'week_end': '2025-09-15'
        }
    
    @pytest.fixture
    def empty_performance_data(self):
        """Empty performance data for testing edge cases"""
        return {
            'daily_pnl': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0
        }

    # Daily Performance Tests
    @patch('routes.performance.get_daily_performance')
    def test_get_daily_performance_success(self, mock_get_daily, client, sample_daily_performance):
        """Test successful daily performance retrieval"""
        mock_get_daily.return_value = sample_daily_performance
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['daily_pnl'] == 1250.50
        assert data['total_trades'] == 8
        assert data['winning_trades'] == 5
        assert data['losing_trades'] == 3
        assert 'date' in data
        mock_get_daily.assert_called_once()
    
    @patch('routes.performance.get_daily_performance')
    def test_get_daily_performance_empty_data(self, mock_get_daily, client, empty_performance_data):
        """Test daily performance with no trades"""
        empty_daily = {**empty_performance_data, 'date': '2025-09-09'}
        mock_get_daily.return_value = empty_daily
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['daily_pnl'] == 0.0
        assert data['total_trades'] == 0
        assert data['winning_trades'] == 0
        assert data['losing_trades'] == 0
        mock_get_daily.assert_called_once()
    
    @patch('routes.performance.get_daily_performance')
    def test_get_daily_performance_negative_pnl(self, mock_get_daily, client):
        """Test daily performance with negative P&L"""
        negative_performance = {
            'daily_pnl': -850.75,
            'total_trades': 5,
            'winning_trades': 1,
            'losing_trades': 4,
            'date': '2025-09-09'
        }
        mock_get_daily.return_value = negative_performance
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['daily_pnl'] == -850.75
        assert data['total_trades'] == 5
        assert data['winning_trades'] == 1
        assert data['losing_trades'] == 4
        mock_get_daily.assert_called_once()
    
    @patch('routes.performance.get_daily_performance')
    def test_get_daily_performance_database_error(self, mock_get_daily, client):
        """Test daily performance with database error"""
        mock_get_daily.side_effect = Exception("Database connection failed")
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        mock_get_daily.assert_called_once()

    # Weekly Performance Tests
    @patch('routes.performance.get_weekly_performance')
    def test_get_weekly_performance_success(self, mock_get_weekly, client, sample_weekly_performance):
        """Test successful weekly performance retrieval"""
        mock_get_weekly.return_value = sample_weekly_performance
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['weekly_pnl'] == 4750.25
        assert data['total_trades'] == 32
        assert data['winning_trades'] == 20
        assert data['losing_trades'] == 12
        assert 'week_start' in data
        assert 'week_end' in data
        mock_get_weekly.assert_called_once()
    
    @patch('routes.performance.get_weekly_performance')
    def test_get_weekly_performance_empty_data(self, mock_get_weekly, client, empty_performance_data):
        """Test weekly performance with no trades"""
        empty_weekly = {
            **empty_performance_data, 
            'weekly_pnl': 0.0,
            'week_start': '2025-09-09',
            'week_end': '2025-09-15'
        }
        mock_get_weekly.return_value = empty_weekly
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['weekly_pnl'] == 0.0
        assert data['total_trades'] == 0
        assert data['winning_trades'] == 0
        assert data['losing_trades'] == 0
        mock_get_weekly.assert_called_once()
    
    @patch('routes.performance.get_weekly_performance')
    def test_get_weekly_performance_negative_pnl(self, mock_get_weekly, client):
        """Test weekly performance with negative P&L"""
        negative_performance = {
            'weekly_pnl': -2450.30,
            'total_trades': 18,
            'winning_trades': 6,
            'losing_trades': 12,
            'week_start': '2025-09-09',
            'week_end': '2025-09-15'
        }
        mock_get_weekly.return_value = negative_performance
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['weekly_pnl'] == -2450.30
        assert data['total_trades'] == 18
        assert data['winning_trades'] == 6
        assert data['losing_trades'] == 12
        mock_get_weekly.assert_called_once()
    
    @patch('routes.performance.get_weekly_performance')
    def test_get_weekly_performance_database_error(self, mock_get_weekly, client):
        """Test weekly performance with database error"""
        mock_get_weekly.side_effect = Exception("Database connection failed")
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        mock_get_weekly.assert_called_once()

    # Performance Calculation Service Tests
    @patch('services.performance_service.FuturesDB')
    def test_daily_performance_calculation(self, mock_db_class):
        """Test daily performance calculation logic"""
        from services.performance_service import calculate_daily_performance
        
        # Mock database data - need to mock the full chain
        mock_db = Mock()
        mock_db_class.return_value.__enter__ = Mock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = Mock(return_value=None)
        
        # Create mock rows that behave like sqlite3.Row objects
        mock_rows = []
        for pnl in [150.25, -75.50, 200.00]:
            mock_row = Mock()
            mock_row.__getitem__ = Mock(side_effect=lambda key, p=pnl: p if key == 'realized_pnl' else 'closed')
            mock_rows.append(mock_row)
        
        # Mock the method chain: _execute_with_monitoring().fetchall()
        mock_result = Mock()
        mock_result.fetchall.return_value = mock_rows
        mock_db._execute_with_monitoring.return_value = mock_result
        
        result = calculate_daily_performance(date(2025, 9, 9))
        
        assert result['daily_pnl'] == 274.75  # Sum of realized P&L
        assert result['total_trades'] == 3
        assert result['winning_trades'] == 2  # Positive P&L
        assert result['losing_trades'] == 1   # Negative P&L
        assert result['date'] == '2025-09-09'
    
    @patch('services.performance_service.FuturesDB')
    def test_weekly_performance_calculation(self, mock_db_class):
        """Test weekly performance calculation logic"""
        from services.performance_service import calculate_weekly_performance
        
        # Mock database data - need to mock the full chain
        mock_db = Mock()
        mock_db_class.return_value.__enter__ = Mock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = Mock(return_value=None)
        
        # Create mock rows that behave like sqlite3.Row objects
        mock_rows = []
        for pnl in [150.25, -75.50, 200.00, 89.75, -125.00]:
            mock_row = Mock()
            mock_row.__getitem__ = Mock(side_effect=lambda key, p=pnl: p if key == 'realized_pnl' else 'closed')
            mock_rows.append(mock_row)
        
        # Mock the method chain: _execute_with_monitoring().fetchall()
        mock_result = Mock()
        mock_result.fetchall.return_value = mock_rows
        mock_db._execute_with_monitoring.return_value = mock_result
        
        result = calculate_weekly_performance(date(2025, 9, 9))
        
        assert result['weekly_pnl'] == 239.50  # Sum of realized P&L
        assert result['total_trades'] == 5
        assert result['winning_trades'] == 3   # Positive P&L
        assert result['losing_trades'] == 2    # Negative P&L
        assert 'week_start' in result
        assert 'week_end' in result

    # Edge Case Tests
    @patch('routes.performance.get_daily_performance')
    def test_daily_performance_only_winning_trades(self, mock_get_daily, client):
        """Test daily performance with only winning trades"""
        winning_only = {
            'daily_pnl': 850.50,
            'total_trades': 4,
            'winning_trades': 4,
            'losing_trades': 0,
            'date': '2025-09-09'
        }
        mock_get_daily.return_value = winning_only
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['winning_trades'] == 4
        assert data['losing_trades'] == 0
        assert data['daily_pnl'] > 0
    
    @patch('routes.performance.get_weekly_performance')
    def test_weekly_performance_only_losing_trades(self, mock_get_weekly, client):
        """Test weekly performance with only losing trades"""
        losing_only = {
            'weekly_pnl': -1250.75,
            'total_trades': 6,
            'winning_trades': 0,
            'losing_trades': 6,
            'week_start': '2025-09-09',
            'week_end': '2025-09-15'
        }
        mock_get_weekly.return_value = losing_only
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['winning_trades'] == 0
        assert data['losing_trades'] == 6
        assert data['weekly_pnl'] < 0

    # Redis Caching Tests
    @patch('routes.performance.redis_client')
    @patch('routes.performance.get_daily_performance')
    def test_daily_performance_caching(self, mock_get_daily, mock_redis, client, sample_daily_performance):
        """Test daily performance caching functionality"""
        # Mock Redis to simulate cache miss and successful set
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_get_daily.return_value = sample_daily_performance
        
        # Also ensure REDIS_AVAILABLE is True for this test
        with patch('routes.performance.REDIS_AVAILABLE', True):
            response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        mock_get_daily.assert_called_once()
        mock_redis.setex.assert_called_once()  # Cache should be set
    
    @patch('routes.performance.redis_client')
    def test_daily_performance_cache_hit(self, mock_redis, client, sample_daily_performance):
        """Test daily performance cache hit"""
        cached_data = json.dumps(sample_daily_performance)
        mock_redis.get.return_value = cached_data
        
        # Also ensure REDIS_AVAILABLE is True for this test
        with patch('routes.performance.REDIS_AVAILABLE', True):
            response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == sample_daily_performance
        mock_redis.get.assert_called_once()

    # Response Time Tests
    @patch('routes.performance.get_daily_performance')
    def test_daily_performance_response_time(self, mock_get_daily, client, sample_daily_performance):
        """Test that daily performance responds within acceptable time limits"""
        import time
        mock_get_daily.return_value = sample_daily_performance
        
        start_time = time.time()
        response = client.get('/api/performance/daily')
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response.status_code == 200
        assert response_time < 0.1  # Should respond within 100ms
    
    @patch('routes.performance.get_weekly_performance')
    def test_weekly_performance_response_time(self, mock_get_weekly, client, sample_weekly_performance):
        """Test that weekly performance responds within acceptable time limits"""
        import time
        mock_get_weekly.return_value = sample_weekly_performance
        
        start_time = time.time()
        response = client.get('/api/performance/weekly')
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response.status_code == 200
        assert response_time < 0.1  # Should respond within 100ms

    # JSON Response Format Tests
    @patch('routes.performance.get_daily_performance')
    def test_daily_performance_json_format(self, mock_get_daily, client, sample_daily_performance):
        """Test that daily performance returns proper JSON format"""
        mock_get_daily.return_value = sample_daily_performance
        
        response = client.get('/api/performance/daily')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        
        # Verify required fields exist
        required_fields = ['daily_pnl', 'total_trades', 'winning_trades', 'losing_trades', 'date']
        for field in required_fields:
            assert field in data
        
        # Verify data types
        assert isinstance(data['daily_pnl'], (int, float))
        assert isinstance(data['total_trades'], int)
        assert isinstance(data['winning_trades'], int)
        assert isinstance(data['losing_trades'], int)
        assert isinstance(data['date'], str)
    
    @patch('routes.performance.get_weekly_performance')
    def test_weekly_performance_json_format(self, mock_get_weekly, client, sample_weekly_performance):
        """Test that weekly performance returns proper JSON format"""
        mock_get_weekly.return_value = sample_weekly_performance
        
        response = client.get('/api/performance/weekly')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        
        # Verify required fields exist
        required_fields = ['weekly_pnl', 'total_trades', 'winning_trades', 'losing_trades', 'week_start', 'week_end']
        for field in required_fields:
            assert field in data
        
        # Verify data types
        assert isinstance(data['weekly_pnl'], (int, float))
        assert isinstance(data['total_trades'], int)
        assert isinstance(data['winning_trades'], int)
        assert isinstance(data['losing_trades'], int)
        assert isinstance(data['week_start'], str)
        assert isinstance(data['week_end'], str)