"""
Tests for BackgroundDataManager class
Tests the background-only data downloading system
"""
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from services.background_data_manager import BackgroundDataManager


class TestBackgroundDataManager:
    """Test the BackgroundDataManager class"""
    
    @pytest.fixture
    def mock_data_service(self):
        """Mock data service for testing"""
        data_service = Mock()
        data_service.fetch_ohlc_data.return_value = [
            {'instrument': 'ES', 'timeframe': '1m', 'timestamp': int(datetime.now().timestamp()),
             'open_price': 4500, 'high_price': 4505, 'low_price': 4495, 'close_price': 4502, 'volume': 1000}
        ]
        return data_service
    
    def test_background_data_manager_initialization(self, mock_data_service):
        """Test BackgroundDataManager initialization"""
        manager = BackgroundDataManager(mock_data_service)
        
        assert manager.is_running == False
        assert manager.ohlc_service == mock_data_service
