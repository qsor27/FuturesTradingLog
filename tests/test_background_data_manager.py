"""
Tests for BackgroundDataManager class
Tests the background-only data downloading system
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from services.background_data_manager import BackgroundDataManager
from services.redis_cache_service import get_cache_service


class TestBackgroundDataManager:
    """Test the BackgroundDataManager class"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for testing"""
        cache_service = Mock()
        cache_service.get_cached_instruments.return_value = ['ES', 'MNQ', 'YM']
        cache_service.get_cache_hit_rate.return_value = 0.95
        cache_service.get_instrument_activity.return_value = {
            'ES': {'last_access': datetime.now(), 'access_count': 10},
            'MNQ': {'last_access': datetime.now() - timedelta(hours=1), 'access_count': 5},
            'YM': {'last_access': datetime.now() - timedelta(hours=2), 'access_count': 3}
        }
        return cache_service
    
    @pytest.fixture
    def mock_data_service(self):
        """Mock data service for testing"""
        data_service = Mock()
        data_service.fetch_ohlc_data.return_value = [
            {'instrument': 'ES', 'timeframe': '1m', 'timestamp': int(datetime.now().timestamp()),
             'open_price': 4500, 'high_price': 4505, 'low_price': 4495, 'close_price': 4502, 'volume': 1000}
        ]
        return data_service
    
    def test_background_data_manager_initialization(self, mock_cache_service):
        """Test BackgroundDataManager initialization"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            assert manager.is_running == False
            assert manager.cache_service == mock_cache_service
            assert manager.priority_instruments == ['ES', 'MNQ', 'YM']
            assert manager.max_concurrent_instruments == 3
    
    def test_start_background_processing(self, mock_cache_service):
        """Test starting background processing"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            manager.start()
            assert manager.is_running == True
            assert manager.thread is not None
            assert manager.thread.daemon == True
            
            manager.stop()
    
    def test_stop_background_processing(self, mock_cache_service):
        """Test stopping background processing"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            manager.start()
            manager.stop()
            
            assert manager.is_running == False
    
    def test_priority_instrument_detection(self, mock_cache_service):
        """Test priority instrument detection based on user activity"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            priority_instruments = manager._get_priority_instruments()
            
            # Should return instruments sorted by recent activity
            assert priority_instruments == ['ES', 'MNQ', 'YM']
    
    def test_batch_processing_logic(self, mock_cache_service, mock_data_service):
        """Test batch processing for multiple instruments and timeframes"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service), \
             patch('services.background_data_manager.ohlc_service', mock_data_service):
            
            manager = BackgroundDataManager()
            
            # Test batch processing for single instrument
            result = manager._process_instrument_batch('ES', ['1m', '5m', '15m'])
            
            assert result['instrument'] == 'ES'
            assert result['success'] == True
            assert len(result['timeframes_processed']) == 3
    
    def test_cache_first_validation(self, mock_cache_service):
        """Test cache-first validation to avoid unnecessary API calls"""
        mock_cache_service.is_data_fresh.side_effect = lambda inst, tf: inst == 'ES' and tf == '1m'
        
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            # Should skip cached data
            needs_update = manager._check_cache_freshness('ES', '1m')
            assert needs_update == False
            
            # Should require update for non-cached data
            needs_update = manager._check_cache_freshness('ES', '5m')
            assert needs_update == True
    
    def test_parallel_processing_limit(self, mock_cache_service):
        """Test that parallel processing respects concurrent instrument limit"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            # Mock concurrent instruments tracking
            manager.active_instruments = set(['ES', 'MNQ', 'YM'])
            
            # Should not process more instruments when at limit
            can_process = manager._can_process_instrument('CL')
            assert can_process == False
            
            # Should allow processing when under limit
            manager.active_instruments.remove('YM')
            can_process = manager._can_process_instrument('CL')
            assert can_process == True
    
    def test_user_activity_tracking(self, mock_cache_service):
        """Test user activity tracking for prioritizing instruments"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            # Test tracking user access
            manager.track_user_access('ES', '1m')
            
            # Verify cache service was called to update activity
            mock_cache_service.update_instrument_activity.assert_called_with('ES', '1m')
    
    def test_real_time_gap_detection(self, mock_cache_service, mock_data_service):
        """Test real-time gap detection and immediate background filling"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service), \
             patch('services.background_data_manager.ohlc_service', mock_data_service):
            
            manager = BackgroundDataManager()
            
            # Mock gap detection
            mock_data_service.detect_gaps.return_value = [
                {'start': datetime.now() - timedelta(minutes=10), 'end': datetime.now() - timedelta(minutes=5)}
            ]
            
            # Test gap detection and filling
            gaps_filled = manager._detect_and_fill_gaps_immediately('ES', '1m')
            
            assert gaps_filled > 0
            mock_data_service.detect_gaps.assert_called_once()
    
    def test_error_handling_during_batch_processing(self, mock_cache_service, mock_data_service):
        """Test error handling during batch processing"""
        mock_data_service.fetch_ohlc_data.side_effect = Exception("API Error")
        
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service), \
             patch('services.background_data_manager.ohlc_service', mock_data_service):
            
            manager = BackgroundDataManager()
            
            # Should handle errors gracefully
            result = manager._process_instrument_batch('ES', ['1m'])
            
            assert result['success'] == False
            assert 'error' in result
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        # Test invalid configuration
        with pytest.raises(ValueError):
            BackgroundDataManager(config={
                'max_concurrent_instruments': 0,  # Invalid
                'update_interval': -1  # Invalid
            })
    
    def test_performance_monitoring(self, mock_cache_service):
        """Test performance monitoring and metrics collection"""
        with patch('services.background_data_manager.get_cache_service', return_value=mock_cache_service):
            manager = BackgroundDataManager()
            
            # Test metrics collection
            metrics = manager.get_performance_metrics()
            
            assert 'cache_hit_rate' in metrics
            assert 'active_instruments' in metrics
            assert 'background_processing_status' in metrics
            assert 'last_update_time' in metrics