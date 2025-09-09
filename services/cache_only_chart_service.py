"""
Cache-Only Chart Service for Futures Trading Log
Ensures chart requests NEVER trigger data downloads
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from services.redis_cache_service import get_cache_service
from services.background_data_manager import background_data_manager
from scripts.TradingLog_db import FuturesDB
from config import config

# Get logger
chart_logger = logging.getLogger('cache_only_chart')

class CacheOnlyChartService:
    """
    Chart service that ONLY serves data from cache
    - Never triggers Yahoo Finance API calls
    - Provides cache status indicators
    - Graceful degradation for incomplete data
    - Real-time monitoring of data freshness
    """
    
    def __init__(self):
        """Initialize the cache-only chart service"""
        self.logger = chart_logger
        self.cache_service = get_cache_service() if config.cache_enabled else None
        
        if self.cache_service:
            self.logger.info("Cache-Only Chart Service: Redis cache service initialized")
        else:
            self.logger.warning("Cache-Only Chart Service: Cache service disabled, using database only")
    
    def get_chart_data(self, instrument: str, timeframe: str, 
                      start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get chart data from cache only - NEVER triggers downloads
        
        Returns:
            Dict containing:
            - success: bool
            - data: List[Dict] - OHLC data points
            - cache_status: Dict - Information about data freshness
            - metadata: Dict - Additional information
        """
        try:
            start_time = datetime.now()
            
            # Track user access for prioritization
            if background_data_manager and hasattr(background_data_manager, 'track_user_access'):
                background_data_manager.track_user_access(instrument, timeframe)
            
            # Try cache first if available
            cache_data = None
            cache_hit = False
            
            if self.cache_service:
                start_timestamp = int(start_date.timestamp())
                end_timestamp = int(end_date.timestamp())
                
                cache_data = self.cache_service.get_cached_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp
                )
                
                if cache_data:
                    cache_hit = True
                    self.logger.debug(f"Cache hit for {instrument} {timeframe}: {len(cache_data)} records")
            
            # If no cache data, fall back to database (but still no API calls)
            if not cache_data:
                cache_data = self._get_database_data(instrument, timeframe, start_date, end_date)
                self.logger.debug(f"Database fallback for {instrument} {timeframe}: {len(cache_data)} records")
            
            # Format data for TradingView Lightweight Charts
            formatted_data = self._format_chart_data(cache_data)
            
            # Get cache status information
            cache_status = self._get_cache_status(instrument, timeframe)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000  # in milliseconds
            
            # Prepare response
            response = {
                'success': True,
                'data': formatted_data,
                'instrument': instrument,
                'timeframe': timeframe,
                'count': len(formatted_data),
                'has_data': len(formatted_data) > 0,
                'cache_status': cache_status,
                'metadata': {
                    'cache_hit': cache_hit,
                    'processing_time_ms': processing_time,
                    'data_source': 'cache' if cache_hit else 'database',
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
            # Add warnings if data is incomplete or stale
            if cache_status['is_stale']:
                response['warnings'] = ['Data may be outdated. Background refresh in progress.']
            
            if cache_status['completeness_score'] < 0.95:
                if 'warnings' not in response:
                    response['warnings'] = []
                response['warnings'].append(f"Data is {cache_status['completeness_score']:.1%} complete. Background filling in progress.")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting cache-only chart data for {instrument} {timeframe}: {e}")
            
            return {
                'success': False,
                'data': [],
                'instrument': instrument,
                'timeframe': timeframe,
                'count': 0,
                'has_data': False,
                'error': str(e),
                'cache_status': {'is_fresh': False, 'is_stale': True, 'completeness_score': 0.0},
                'metadata': {'cache_hit': False, 'data_source': 'error'}
            }
    
    def _get_database_data(self, instrument: str, timeframe: str, 
                          start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get data directly from database (fallback when cache unavailable)"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            with FuturesDB() as db:
                data = db.get_ohlc_data(instrument, timeframe, start_timestamp, end_timestamp, limit=None)
                
                # If no data found with exact name, try base instrument name
                if not data:
                    base_instrument = self._get_base_instrument(instrument)
                    if base_instrument != instrument:
                        self.logger.debug(f"No data for {instrument}, trying base instrument {base_instrument}")
                        data = db.get_ohlc_data(base_instrument, timeframe, start_timestamp, end_timestamp, limit=None)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting database data for {instrument} {timeframe}: {e}")
            return []
    
    def _get_base_instrument(self, instrument: str) -> str:
        """Extract base instrument symbol (e.g., 'MNQ SEP25' -> 'MNQ')"""
        return instrument.split(' ')[0] if ' ' in instrument else instrument
    
    def _format_chart_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Format raw OHLC data for TradingView Lightweight Charts"""
        try:
            formatted_data = []
            
            for record in raw_data:
                # Handle different data formats (from cache vs database)
                if 'time' in record:
                    # Already formatted for TradingView
                    formatted_data.append(record)
                else:
                    # Convert from database format
                    timestamp = record.get('timestamp')
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    elif isinstance(timestamp, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp)
                    
                    formatted_record = {
                        'time': int(timestamp.timestamp()),
                        'open': float(record.get('open_price', 0)),
                        'high': float(record.get('high_price', 0)),
                        'low': float(record.get('low_price', 0)),
                        'close': float(record.get('close_price', 0)),
                        'volume': int(record.get('volume', 0) or 0)
                    }
                    formatted_data.append(formatted_record)
            
            # Sort by timestamp to ensure correct order
            formatted_data.sort(key=lambda x: x['time'])
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error formatting chart data: {e}")
            return []
    
    def _get_cache_status(self, instrument: str, timeframe: str) -> Dict[str, Any]:
        """Get comprehensive cache status information"""
        try:
            if not self.cache_service:
                return {
                    'is_fresh': False,
                    'is_stale': True,
                    'last_update': None,
                    'completeness_score': 0.0,
                    'background_processing': background_data_manager.is_running if background_data_manager else False,
                    'cache_available': False
                }
            
            # Check if data is fresh
            is_fresh = self.cache_service.is_data_fresh(instrument, timeframe)
            
            # Get last update time
            last_update = self.cache_service.get_last_update_time(instrument, timeframe)
            
            # Calculate completeness score
            completeness_score = self._calculate_completeness_score(instrument, timeframe)
            
            # Check background processing status
            background_status = background_data_manager.is_running if background_data_manager else False
            
            return {
                'is_fresh': is_fresh,
                'is_stale': not is_fresh,
                'last_update': last_update.isoformat() if last_update else None,
                'completeness_score': completeness_score,
                'background_processing': background_status,
                'cache_available': True,
                'data_age_minutes': self._get_data_age_minutes(last_update) if last_update else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache status for {instrument} {timeframe}: {e}")
            return {
                'is_fresh': False,
                'is_stale': True,
                'last_update': None,
                'completeness_score': 0.0,
                'background_processing': False,
                'cache_available': False,
                'error': str(e)
            }
    
    def _calculate_completeness_score(self, instrument: str, timeframe: str) -> float:
        """Calculate data completeness score (0.0 to 1.0)"""
        try:
            if not self.cache_service:
                return 0.0
            
            # Get expected vs actual data points for recent period
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=24)  # Check last 24 hours
            
            # Calculate expected data points based on timeframe
            expected_points = self._calculate_expected_data_points(timeframe, start_date, end_date)
            
            # Get actual data points from cache
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            actual_data = self.cache_service.get_cached_ohlc_data(
                instrument, timeframe, start_timestamp, end_timestamp
            )
            
            actual_points = len(actual_data) if actual_data else 0
            
            # Calculate completeness score
            if expected_points == 0:
                return 1.0  # No data expected
            
            score = min(actual_points / expected_points, 1.0)
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating completeness score for {instrument} {timeframe}: {e}")
            return 0.0
    
    def _calculate_expected_data_points(self, timeframe: str, start_date: datetime, end_date: datetime) -> int:
        """Calculate expected number of data points for a timeframe and date range"""
        try:
            # Convert timeframe to minutes
            timeframe_minutes = {
                '1m': 1,
                '3m': 3,
                '5m': 5,
                '15m': 15,
                '1h': 60,
                '4h': 240,
                '1d': 1440
            }
            
            minutes_per_point = timeframe_minutes.get(timeframe, 1)
            total_minutes = (end_date - start_date).total_seconds() / 60
            
            # Account for market hours (futures trade ~23 hours per day)
            market_hours_factor = 23 / 24 if timeframe != '1d' else 5 / 7  # 5 trading days per week for daily
            
            expected_points = int((total_minutes / minutes_per_point) * market_hours_factor)
            
            return max(expected_points, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating expected data points: {e}")
            return 0
    
    def _get_data_age_minutes(self, last_update: datetime) -> int:
        """Get age of data in minutes"""
        try:
            if not last_update:
                return None
            
            age = datetime.now() - last_update
            return int(age.total_seconds() / 60)
            
        except Exception as e:
            self.logger.error(f"Error calculating data age: {e}")
            return None
    
    def get_cache_health_status(self) -> Dict[str, Any]:
        """Get overall cache health status"""
        try:
            if not self.cache_service:
                return {
                    'status': 'unavailable',
                    'cache_enabled': False,
                    'background_processing': background_data_manager.is_running if background_data_manager else False
                }
            
            # Get overall cache statistics
            cache_stats = self.cache_service.get_cache_stats()
            
            # Get background processing metrics
            bg_metrics = background_data_manager.get_performance_metrics() if background_data_manager else {}
            
            # Calculate overall health score
            cache_hit_rate = bg_metrics.get('cache_hit_rate', 0.0)
            
            health_score = cache_hit_rate
            if health_score >= 0.95:
                status = 'excellent'
            elif health_score >= 0.90:
                status = 'good'
            elif health_score >= 0.80:
                status = 'fair'
            else:
                status = 'poor'
            
            return {
                'status': status,
                'health_score': health_score,
                'cache_enabled': True,
                'cache_hit_rate': cache_hit_rate,
                'total_instruments': cache_stats.get('total_instruments', 0),
                'total_cache_entries': cache_stats.get('ohlc_cache_entries', 0),
                'background_processing': bg_metrics.get('background_processing_status') == 'running',
                'last_background_update': bg_metrics.get('last_update_time'),
                'active_instruments': bg_metrics.get('active_instruments', 0),
                'error_count': bg_metrics.get('error_count', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache health status: {e}")
            return {
                'status': 'error',
                'cache_enabled': False,
                'error': str(e)
            }
    
    def get_instrument_status(self, instrument: str) -> Dict[str, Any]:
        """Get detailed status for a specific instrument"""
        try:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
            timeframe_status = {}
            
            for timeframe in timeframes:
                status = self._get_cache_status(instrument, timeframe)
                timeframe_status[timeframe] = status
            
            # Calculate overall instrument health
            fresh_count = sum(1 for status in timeframe_status.values() if status.get('is_fresh', False))
            overall_health = fresh_count / len(timeframes)
            
            return {
                'instrument': instrument,
                'overall_health': overall_health,
                'timeframe_status': timeframe_status,
                'background_processing': background_data_manager.is_running if background_data_manager else False,
                'is_priority_instrument': instrument in background_data_manager.config.get('priority_instruments', []) if background_data_manager else False
            }
            
        except Exception as e:
            self.logger.error(f"Error getting instrument status for {instrument}: {e}")
            return {
                'instrument': instrument,
                'overall_health': 0.0,
                'error': str(e)
            }


# Global instance
cache_only_chart_service = CacheOnlyChartService()