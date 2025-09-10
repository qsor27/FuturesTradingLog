"""
Tests for BackgroundDataManager class
Tests the background-only data downloading system
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from services.background_data_manager import BackgroundDataManager


class TestBackgroundDataManager:
    """Test the BackgroundDataManager class"""
    
    @pytest.fixture
    def mock_data_service(self):
        """Mock data service for testing"""
        data_service = Mock()
        data_service.update_all_active_instruments.return_value = ['ES', 'MNQ', 'YM']
        return data_service
    
    def test_background_data_manager_initialization(self, mock_data_service):
        """Test BackgroundDataManager initialization"""
        manager = BackgroundDataManager(mock_data_service)
        
        assert manager.is_running == False
        assert manager.ohlc_service == mock_data_service
        assert isinstance(manager.user_access_log, dict)
        assert manager.config is not None
    
    def test_track_user_access(self, mock_data_service):
        """Test user access tracking"""
        manager = BackgroundDataManager(mock_data_service)
        
        # Track access
        manager.track_user_access('ES', '1m')
        
        # Verify tracking
        key = 'ES:1m'
        assert key in manager.user_access_log
        assert manager.user_access_log[key]['count'] == 1
        assert manager.user_access_log[key]['last_access'] is not None
        
        # Track again
        manager.track_user_access('ES', '1m')
        assert manager.user_access_log[key]['count'] == 2
    
    def test_get_performance_metrics(self, mock_data_service):
        """Test performance metrics collection"""
        manager = BackgroundDataManager(mock_data_service)
        
        # Track some access to test metrics
        manager.track_user_access('ES', '1m')
        manager.track_user_access('MNQ', '5m')
        
        metrics = manager.get_performance_metrics()
        
        assert 'background_processing_status' in metrics
        assert 'cache_hit_rate' in metrics
        assert 'active_instruments' in metrics
        assert metrics['active_instruments'] == 2  # Two instruments tracked
    
    @patch('config.BACKGROUND_DATA_CONFIG', {'enabled': True, 'all_timeframes': ['1m', '5m']})
    def test_run_update_enabled(self, mock_data_service):
        """Test run_update when enabled"""
        manager = BackgroundDataManager(mock_data_service)
        
        manager.run_update()
        
        # Verify the update was called
        mock_data_service.update_all_active_instruments.assert_called_once_with(
            timeframes=['1m', '5m']
        )
    
    @patch('config.BACKGROUND_DATA_CONFIG', {'enabled': False})
    def test_run_update_disabled(self, mock_data_service):
        """Test run_update when disabled"""
        manager = BackgroundDataManager(mock_data_service)
        
        manager.run_update()
        
        # Verify the update was not called
        mock_data_service.update_all_active_instruments.assert_not_called()
    
    @patch('config.BACKGROUND_DATA_CONFIG', {'enabled': False})
    def test_start_disabled(self, mock_data_service):
        """Test start when disabled"""
        manager = BackgroundDataManager(mock_data_service)
        
        # Should not start when disabled
        result = manager.start()
        
        # start() should return None when disabled
        assert result is None
    
    @patch('config.BACKGROUND_DATA_CONFIG', {'enabled': True, 'full_update_interval': 1})
    @patch('threading.Thread')
    def test_start_enabled(self, mock_thread, mock_data_service):
        """Test start when enabled"""
        manager = BackgroundDataManager(mock_data_service)
        
        manager.start()
        
        # Verify thread was created and started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
