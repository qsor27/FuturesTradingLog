"""
Chart Data Service - Business logic for chart data operations

Extracted from routes/chart_data.py to separate business logic from HTTP handling
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

from ...domain.interfaces.chart_service_interface import IChartDataService, IChartPerformanceService

logger = logging.getLogger('chart_data_service')


class ChartDataService(IChartDataService):
    """
    Application service for chart data operations
    
    Handles OHLC data requests, resolution adaptation, and performance optimization
    """
    
    def __init__(self, ohlc_service=None):
        self.ohlc_service = ohlc_service
    
    def get_chart_data(self, instrument: str, timeframe: str = '1m', 
                      days: int = 1) -> Dict[str, Any]:
        """
        Get chart data for instrument with specified timeframe and duration
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            days: Number of days of data to retrieve
            
        Returns:
            Dictionary with chart data and metadata
        """
        try:
            if not self.ohlc_service:
                raise ValueError("OHLC service not available")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get raw data from OHLC service
            raw_data = self.ohlc_service.get_chart_data(
                instrument, timeframe, start_date, end_date
            )
            
            # Format for TradingView Lightweight Charts
            chart_data = self._format_for_tradingview(raw_data)
            
            return {
                'success': True,
                'data': chart_data,
                'instrument': instrument,
                'timeframe': timeframe,
                'days': days,
                'count': len(chart_data),
                'has_data': len(chart_data) > 0,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting chart data for {instrument}: {e}")
            return {
                'success': False,
                'error': str(e),
                'instrument': instrument,
                'timeframe': timeframe,
                'days': days,
                'data': [],
                'count': 0,
                'has_data': False
            }
    
    def get_adaptive_chart_data(self, instrument: str, timeframe: str = '1h', 
                               days: int = 1) -> Dict[str, Any]:
        """
        Get chart data with automatic resolution adaptation for performance
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Requested timeframe
            days: Number of days of data to retrieve
            
        Returns:
            Dictionary with adaptive chart data and metadata
        """
        try:
            # Determine optimal resolution based on data range
            optimal_timeframe = self._get_optimal_resolution(days, timeframe)
            
            # Estimate candle count for performance validation
            estimated_candles = self._estimate_candle_count(days, optimal_timeframe)
            
            # Get chart data with optimal resolution
            result = self.get_chart_data(instrument, optimal_timeframe, days)
            
            # Add adaptation metadata
            result.update({
                'requested_timeframe': timeframe,
                'optimal_timeframe': optimal_timeframe,
                'estimated_candles': estimated_candles,
                'resolution_adapted': timeframe != optimal_timeframe,
                'adaptation_reason': self._get_adaptation_reason(days, timeframe, optimal_timeframe)
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting adaptive chart data for {instrument}: {e}")
            return {
                'success': False,
                'error': str(e),
                'instrument': instrument,
                'data': [],
                'count': 0,
                'has_data': False
            }
    
    def get_chart_data_with_trades(self, instrument: str, timeframe: str = '1m',
                                  days: int = 1, account: Optional[str] = None) -> Dict[str, Any]:
        """
        Get chart data with trade markers overlaid
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe
            days: Number of days of data
            account: Optional account filter for trades
            
        Returns:
            Dictionary with chart data and trade markers
        """
        try:
            # Get basic chart data
            chart_result = self.get_chart_data(instrument, timeframe, days)
            
            if not chart_result['success']:
                return chart_result
            
            # Get trade data for the same period
            trade_markers = self._get_trade_markers(
                instrument, 
                chart_result['start_date'], 
                chart_result['end_date'],
                account
            )
            
            # Add trade markers to result
            chart_result.update({
                'trade_markers': trade_markers,
                'has_trades': len(trade_markers) > 0,
                'trade_count': len(trade_markers)
            })
            
            return chart_result
            
        except Exception as e:
            logger.error(f"Error getting chart data with trades for {instrument}: {e}")
            return {
                'success': False,
                'error': str(e),
                'instrument': instrument,
                'data': [],
                'trade_markers': [],
                'has_trades': False
            }
    
    def validate_chart_request(self, instrument: str, timeframe: str, 
                             days: int) -> Dict[str, Any]:
        """
        Validate chart data request parameters
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe
            days: Number of days of data
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Validate timeframe
            supported_timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
            if timeframe not in supported_timeframes:
                validation_result['errors'].append(
                    f"Unsupported timeframe: {timeframe}. Supported: {supported_timeframes}"
                )
            
            # Validate days
            if days <= 0:
                validation_result['errors'].append("Days must be positive")
            elif days > 365:
                validation_result['warnings'].append(
                    f"Large date range ({days} days) may impact performance"
                )
            
            # Validate instrument
            if not instrument or not instrument.strip():
                validation_result['errors'].append("Instrument cannot be empty")
            
            # Estimate performance impact
            estimated_candles = self._estimate_candle_count(days, timeframe)
            if estimated_candles > 10000:
                validation_result['warnings'].append(
                    f"Large dataset ({estimated_candles} estimated candles) may impact performance"
                )
            
            validation_result['valid'] = len(validation_result['errors']) == 0
            
        except Exception as e:
            logger.error(f"Error validating chart request: {e}")
            validation_result['valid'] = False
            validation_result['errors'].append(f"Validation error: {e}")
        
        return validation_result
    
    def _format_for_tradingview(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Format raw OHLC data for TradingView Lightweight Charts
        
        Args:
            raw_data: Raw OHLC data from database
            
        Returns:
            List of formatted chart data points
        """
        chart_data = []
        
        for record in raw_data:
            chart_data.append({
                'time': record.get('timestamp'),
                'open': record.get('open_price'),
                'high': record.get('high_price'),
                'low': record.get('low_price'),
                'close': record.get('close_price'),
                'volume': record.get('volume') or 0
            })
        
        return chart_data
    
    def _get_optimal_resolution(self, duration_days: int, 
                               requested_timeframe: str = None) -> str:
        """
        Determine optimal resolution based on data range to maintain performance
        
        Args:
            duration_days: Number of days of data
            requested_timeframe: Originally requested timeframe
            
        Returns:
            Optimal timeframe string
        """
        # For very large ranges, force lower resolution regardless of request
        if duration_days > 90:  # > 3 months
            return '1d'  # Daily candles
        elif duration_days > 30:  # > 1 month
            return '4h'  # 4-hour candles
        elif duration_days > 7:   # > 1 week
            return '1h'  # Hourly candles
        elif duration_days > 1:   # > 1 day
            return '15m'  # 15-minute candles
        else:
            return requested_timeframe or '1m'  # Use requested or 1-minute for small ranges
    
    def _estimate_candle_count(self, duration_days: int, timeframe: str) -> int:
        """
        Estimate number of candles for performance validation
        
        Args:
            duration_days: Number of days
            timeframe: Chart timeframe
            
        Returns:
            Estimated number of candles
        """
        timeframe_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15,
            '1h': 60, '4h': 240, '1d': 1440
        }
        
        total_minutes = duration_days * 24 * 60
        candle_minutes = timeframe_minutes.get(timeframe, 1)
        
        # Account for market hours (roughly 23/24 hours for futures)
        market_factor = 0.96  # ~23 hours of 24
        
        return int(total_minutes * market_factor / candle_minutes)
    
    def _get_adaptation_reason(self, days: int, requested: str, optimal: str) -> str:
        """
        Get reason for timeframe adaptation
        
        Args:
            days: Number of days
            requested: Requested timeframe
            optimal: Optimal timeframe
            
        Returns:
            Adaptation reason string
        """
        if requested == optimal:
            return "No adaptation needed"
        
        if days > 90:
            return "Large date range (>3 months) - adapted to daily resolution"
        elif days > 30:
            return "Large date range (>1 month) - adapted to 4-hour resolution"
        elif days > 7:
            return "Large date range (>1 week) - adapted to hourly resolution"
        elif days > 1:
            return "Large date range (>1 day) - adapted to 15-minute resolution"
        else:
            return "Performance optimization"
    
    def _get_trade_markers(self, instrument: str, start_date: str, end_date: str,
                          account: Optional[str] = None) -> List[Dict]:
        """
        Get trade markers for overlaying on chart
        
        Args:
            instrument: Trading instrument
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            account: Optional account filter
            
        Returns:
            List of trade marker dictionaries
        """
        try:
            # This would typically query the database for trades
            # For now, return empty list as placeholder
            return []
            
        except Exception as e:
            logger.error(f"Error getting trade markers: {e}")
            return []


class ChartPerformanceService(IChartPerformanceService):
    """
    Service for monitoring and optimizing chart performance
    """
    
    def __init__(self):
        self.performance_stats = {}
    
    def track_request_performance(self, instrument: str, timeframe: str, 
                                 days: int, response_time: float, 
                                 candle_count: int):
        """
        Track performance metrics for chart requests
        
        Args:
            instrument: Trading instrument
            timeframe: Chart timeframe
            days: Number of days requested
            response_time: Response time in seconds
            candle_count: Number of candles returned
        """
        key = f"{instrument}_{timeframe}_{days}"
        
        if key not in self.performance_stats:
            self.performance_stats[key] = {
                'requests': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'total_candles': 0,
                'avg_candles': 0
            }
        
        stats = self.performance_stats[key]
        stats['requests'] += 1
        stats['total_time'] += response_time
        stats['avg_time'] = stats['total_time'] / stats['requests']
        stats['max_time'] = max(stats['max_time'], response_time)
        stats['min_time'] = min(stats['min_time'], response_time)
        stats['total_candles'] += candle_count
        stats['avg_candles'] = stats['total_candles'] / stats['requests']
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics
        
        Returns:
            Dictionary with performance statistics
        """
        return {
            'total_requests': sum(stats['requests'] for stats in self.performance_stats.values()),
            'average_response_time': sum(stats['avg_time'] for stats in self.performance_stats.values()) / len(self.performance_stats) if self.performance_stats else 0,
            'slowest_requests': sorted(
                [(key, stats['max_time']) for key, stats in self.performance_stats.items()],
                key=lambda x: x[1], reverse=True
            )[:10],
            'request_details': self.performance_stats
        }