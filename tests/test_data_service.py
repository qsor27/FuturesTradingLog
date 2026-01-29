"""
Tests for OHLC Data Service functionality
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
from services.data_service import OHLCDataService

class TestOHLCDataService:
    """Test OHLC data service operations"""
    
    @pytest.fixture
    def service(self):
        """Create data service instance for testing"""
        return OHLCDataService()
    
    @pytest.fixture
    def mock_yfinance_data(self):
        """Mock yfinance data response"""
        # Create mock DataFrame
        dates = pd.date_range(start='2024-01-01 09:30:00', periods=100, freq='1min')
        data = pd.DataFrame({
            'Open': [100.0 + i * 0.1 for i in range(100)],
            'High': [101.0 + i * 0.1 for i in range(100)],
            'Low': [99.0 + i * 0.1 for i in range(100)],
            'Close': [100.5 + i * 0.1 for i in range(100)],
            'Volume': [1000 + i * 10 for i in range(100)]
        }, index=dates)
        return data
    
    @pytest.mark.integration
    def test_symbol_mapping(self, service):
        """Test instrument symbol mapping to yfinance symbols"""
        test_cases = {
            'MNQ': 'NQ=F',
            'MNQ SEP25': 'NQ=F',  # Should extract base symbol
            'ES': 'ES=F',
            'YM': 'YM=F',
            'UNKNOWN': 'UNKNOWN=F'  # Should default format
        }
        
        for instrument, expected in test_cases.items():
            result = service._get_yfinance_symbol(instrument)
            assert result == expected, f"Expected {expected} for {instrument}, got {result}"
    
    def test_timeframe_conversion(self, service):
        """Test timeframe conversion to yfinance format"""
        test_cases = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d',
            'unknown': '1m'  # Should default to 1m
        }
        
        for timeframe, expected in test_cases.items():
            result = service._convert_timeframe_to_yfinance(timeframe)
            assert result == expected, f"Expected {expected} for {timeframe}, got {result}"
    
    @pytest.mark.integration
    def test_rate_limiting(self, service):
        """Test rate limiting between API requests"""
        # Set a short delay for testing
        service.rate_limit_delay = 0.1
        
        start_time = time.time()
        
        # First call should be immediate
        service._enforce_rate_limit()
        first_call_time = time.time() - start_time
        assert first_call_time < 0.05, "First call should be immediate"
        
        # Second call should be delayed
        service._enforce_rate_limit()
        second_call_time = time.time() - start_time
        assert second_call_time >= 0.1, "Second call should be delayed by rate limit"
    
    @pytest.mark.integration
    @patch('data_service.yf.Ticker')
    def test_fetch_ohlc_data_success(self, mock_ticker, service, mock_yfinance_data):
        """Test successful OHLC data fetching"""
        # Setup mock
        mock_instance = Mock()
        mock_instance.history.return_value = mock_yfinance_data
        mock_ticker.return_value = mock_instance
        
        # Test fetch
        start_date = datetime(2024, 1, 1, 9, 30)
        end_date = datetime(2024, 1, 1, 11, 30)
        
        result = service.fetch_ohlc_data('MNQ', '1m', start_date, end_date)
        
        # Verify results
        assert len(result) == 100, "Should return 100 records"
        assert result[0]['instrument'] == 'MNQ'
        assert result[0]['timeframe'] == '1m'
        assert 'timestamp' in result[0]
        assert 'open_price' in result[0]
        assert 'high_price' in result[0]
        assert 'low_price' in result[0]
        assert 'close_price' in result[0]
        assert 'volume' in result[0]
        
        # Verify ticker was called correctly
        mock_ticker.assert_called_once_with('NQ=F')
        mock_instance.history.assert_called_once()
    
    @pytest.mark.integration
    @patch('data_service.yf.Ticker')
    def test_fetch_ohlc_data_empty_response(self, mock_ticker, service):
        """Test handling of empty yfinance response"""
        # Setup mock to return empty DataFrame
        mock_instance = Mock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        result = service.fetch_ohlc_data('MNQ', '1m', start_date, end_date)
        
        assert result == [], "Should return empty list for empty response"
    
    @patch('data_service.yf.Ticker')
    def test_fetch_ohlc_data_exception(self, mock_ticker, service):
        """Test handling of yfinance API exceptions"""
        # Setup mock to raise exception
        mock_ticker.side_effect = Exception("API Error")
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        result = service.fetch_ohlc_data('MNQ', '1m', start_date, end_date)
        
        assert result == [], "Should return empty list on exception"
    
    def test_market_hours_validation(self, service):
        """Test market hours validation logic"""
        # Test cases for different times
        test_cases = [
            # (datetime, expected_open)
            (datetime(2024, 1, 6, 10, 0), False),   # Saturday - closed
            (datetime(2024, 1, 7, 23, 0), True),    # Sunday 11 PM UTC - open
            (datetime(2024, 1, 7, 20, 0), False),   # Sunday 8 PM UTC - closed
            (datetime(2024, 1, 8, 21, 30), False),  # Monday maintenance break
            (datetime(2024, 1, 8, 23, 0), True),    # Monday after maintenance
            (datetime(2024, 1, 12, 20, 0), True),   # Friday 8 PM UTC - open
            (datetime(2024, 1, 12, 15, 0), True),   # Friday 3 PM UTC - open
        ]
        
        for test_datetime, expected in test_cases:
            result = service.is_market_open(test_datetime)
            assert result == expected, f"Market hours check failed for {test_datetime}"
    
    @patch('data_service.FuturesDB')
    def test_detect_and_fill_gaps_no_gaps(self, mock_db_class, service):
        """Test gap detection when no gaps exist"""
        # Setup mock database
        mock_db = Mock()
        mock_db.find_ohlc_gaps.return_value = []
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        result = service.detect_and_fill_gaps('MNQ', '1m', start_date, end_date)
        
        assert result == True, "Should return True when no gaps"
        mock_db.find_ohlc_gaps.assert_called_once()
    
    @patch('data_service.FuturesDB')
    @patch.object(OHLCDataService, 'fetch_ohlc_data')
    @patch.object(OHLCDataService, 'is_market_open')
    def test_detect_and_fill_gaps_with_gaps(self, mock_market_open, mock_fetch, mock_db_class, service):
        """Test gap detection and filling when gaps exist"""
        # Setup mocks
        mock_db = Mock()
        gap_start = int(datetime(2024, 1, 1, 10, 0).timestamp())
        gap_end = int(datetime(2024, 1, 1, 11, 0).timestamp())
        mock_db.find_ohlc_gaps.return_value = [(gap_start, gap_end)]
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        mock_market_open.return_value = True
        mock_fetch.return_value = [
            {
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': gap_start + 60,
                'open_price': 100.0,
                'high_price': 101.0,
                'low_price': 99.0,
                'close_price': 100.5,
                'volume': 1000
            }
        ]
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        result = service.detect_and_fill_gaps('MNQ', '1m', start_date, end_date)
        
        assert result == True, "Should successfully fill gaps"
        mock_fetch.assert_called_once()
        mock_db.insert_ohlc_data.assert_called_once()
    
    @patch('data_service.FuturesDB')
    @patch.object(OHLCDataService, 'detect_and_fill_gaps')
    def test_get_chart_data(self, mock_fill_gaps, mock_db_class, service):
        """Test chart data retrieval with gap filling"""
        # Setup mocks
        mock_db = Mock()
        mock_db.get_ohlc_data.return_value = [
            {
                'instrument': 'MNQ',
                'timeframe': '1m',
                'timestamp': 1234567890,
                'open_price': 100.0,
                'high_price': 101.0,
                'low_price': 99.0,
                'close_price': 100.5,
                'volume': 1000
            }
        ]
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_fill_gaps.return_value = True
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        result = service.get_chart_data('MNQ', '1m', start_date, end_date)
        
        assert len(result) == 1, "Should return chart data"
        assert result[0]['instrument'] == 'MNQ'
        mock_fill_gaps.assert_called_once()
        mock_db.get_ohlc_data.assert_called_once()
    
    @patch('data_service.FuturesDB')
    @patch.object(OHLCDataService, 'fetch_ohlc_data')
    def test_update_recent_data(self, mock_fetch, mock_db_class, service):
        """Test updating recent data for multiple timeframes"""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        sample_data = {
            'instrument': 'MNQ',
            'timeframe': '1m',
            'timestamp': 1234567890,
            'open_price': 100.0,
            'high_price': 101.0,
            'low_price': 99.0,
            'close_price': 100.5,
            'volume': 1000
        }
        mock_fetch.return_value = [sample_data]
        
        result = service.update_recent_data('MNQ', ['1m', '5m'])
        
        assert result == True, "Should successfully update data"
        assert mock_fetch.call_count == 2, "Should fetch data for 2 timeframes"
        assert mock_db.insert_ohlc_data.call_count == 2, "Should insert data for 2 timeframes"
    
    def test_init_configuration(self, service):
        """Test service initialization and configuration"""
        assert service.rate_limit_delay == 1.0, "Should have 1 second rate limit"
        assert 'MNQ' in service.symbol_mapping, "Should have MNQ mapping"
        assert service.symbol_mapping['MNQ'] == 'NQ=F', "MNQ should map to NQ=F"
        assert service.maintenance_break == (21, 22), "Should have correct maintenance hours"
    
    @patch('data_service.time.sleep')
    def test_rate_limit_enforcement(self, mock_sleep, service):
        """Test that rate limiting actually enforces delays"""
        service.rate_limit_delay = 1.0
        service.last_request_time = time.time() - 0.5  # 0.5 seconds ago
        
        service._enforce_rate_limit()
        
        # Should have slept for approximately 0.5 seconds
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert 0.4 <= sleep_time <= 0.6, f"Should sleep for ~0.5 seconds, slept for {sleep_time}"
    
    def test_extract_base_symbol(self, service):
        """Test extraction of base symbol from contract names"""
        test_cases = {
            'MNQ SEP25': 'MNQ',
            'ES DEC24': 'ES', 
            'YM': 'YM',
            'NQ MAR25': 'NQ',
            'CL JUN24': 'CL'
        }
        
        for contract, expected_base in test_cases.items():
            result = service._get_yfinance_symbol(contract)
            expected_symbol = service.symbol_mapping.get(expected_base, f"{expected_base}=F")
            assert result == expected_symbol, f"Failed to extract base symbol from {contract}"