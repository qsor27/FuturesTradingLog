"""
Extension methods for TradingLog_db.py - Chart Execution Data
This file contains additional methods that can be imported into the main TradingLog_db class.
"""

from typing import Dict, List, Any, Optional
import logging
import json
import hashlib
from datetime import datetime

# Get the same logger used by TradingLog_db
db_logger = logging.getLogger('database')


def get_position_executions_for_chart(self, position_id: int, timeframe: str = '1h', start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Get execution data formatted for chart arrow display with precise timestamps and positioning.
    
    Args:
        position_id: Position identifier  
        timeframe: Chart timeframe ('1m', '5m', '1h')
        start_date: Optional start date filter (ISO 8601)
        end_date: Optional end date filter (ISO 8601)
        
    Returns:
        Dictionary with executions, chart_bounds, and timeframe_info
    """
    try:
        # First get the position data to verify it exists
        position_data = self.get_position_executions(position_id)
        if not position_data:
            return None
        
        # Get related executions from position data
        related_executions = position_data.get('related_executions', [])
        if not related_executions:
            return None
        
        # Convert timeframe to milliseconds for timestamp alignment
        timeframe_ms = {
            '1m': 60000,      # 1 minute = 60 seconds = 60,000 ms
            '5m': 300000,     # 5 minutes = 300 seconds = 300,000 ms  
            '1h': 3600000     # 1 hour = 3600 seconds = 3,600,000 ms
        }.get(timeframe, 3600000)
        
        executions = []
        prices = []
        timestamps = []
        
        for execution in related_executions:
            # Convert execution to chart format
            chart_execution = self._format_execution_for_chart(execution, timeframe_ms)
            if chart_execution:
                executions.extend(chart_execution)  # Can return multiple (entry + exit)
                
                # Collect prices and timestamps for bounds calculation
                for exec_data in chart_execution:
                    prices.append(exec_data['price'])
                    timestamps.append(exec_data['timestamp_ms'])
        
        # Apply date filtering if specified
        if start_date or end_date:
            executions = self._filter_executions_by_date(executions, start_date, end_date)
        
        # Calculate chart bounds
        chart_bounds = self._calculate_chart_bounds(prices, timestamps)
        
        # Sort executions by timestamp
        executions.sort(key=lambda x: x['timestamp_ms'])
        
        return {
            'executions': executions,
            'chart_bounds': chart_bounds,
            'timeframe_info': {
                'selected': timeframe,
                'candle_duration_ms': timeframe_ms
            }
        }
        
    except Exception as e:
        db_logger.error(f"Error getting position executions for chart: {e}")
        return None

def _format_execution_for_chart(self, execution: Dict[str, Any], timeframe_ms: int) -> List[Dict[str, Any]]:
    """
    Format a single execution into chart arrow data (entry and exit if closed).
    
    Returns list because one execution record can generate multiple chart points.
    """
    try:
        chart_executions = []
        
        # Parse timestamps
        entry_time = execution.get('entry_time')
        exit_time = execution.get('exit_time')
        
        if not entry_time:
            return []
        
        # Entry execution
        entry_timestamp_ms = self._align_timestamp_to_timeframe(entry_time, timeframe_ms)
        
        entry_execution = {
            'id': execution['id'],
            'timestamp': entry_time,
            'timestamp_ms': entry_timestamp_ms,
            'price': float(execution['entry_price']),
            'quantity': int(execution['quantity']),
            'side': execution['side_of_market'].lower(),
            'execution_type': 'entry',
            'pnl_dollars': 0.00,  # Entry has no P&L yet
            'pnl_points': 0.00,
            'commission': float(execution.get('commission', 0)),
            'position_quantity': int(execution['quantity']),  # Position size after entry
            'avg_price': float(execution['entry_price'])
        }
        chart_executions.append(entry_execution)
        
        # Exit execution (if position is closed)
        if exit_time and execution.get('exit_price'):
            exit_timestamp_ms = self._align_timestamp_to_timeframe(exit_time, timeframe_ms)
            
            # Determine exit side (opposite of entry)
            exit_side = 'buy' if execution['side_of_market'].lower() == 'sell' else 'sell'
            
            exit_execution = {
                'id': execution['id'],
                'timestamp': exit_time,
                'timestamp_ms': exit_timestamp_ms,
                'price': float(execution['exit_price']),
                'quantity': int(execution['quantity']),
                'side': exit_side,
                'execution_type': 'exit',
                'pnl_dollars': float(execution.get('dollars_gain_loss', 0)),
                'pnl_points': float(execution.get('points_gain_loss', 0)),
                'commission': float(execution.get('commission', 0)),
                'position_quantity': 0,  # Position closed
                'avg_price': float(execution['exit_price'])
            }
            chart_executions.append(exit_execution)
        
        return chart_executions
        
    except Exception as e:
        db_logger.error(f"Error formatting execution for chart: {e}")
        return []

def _align_timestamp_to_timeframe(self, timestamp_str: str, timeframe_ms: int) -> int:
    """
    Align execution timestamp to chart candle boundaries for accurate positioning.
    """
    try:
        # Parse timestamp (handle various formats)
        if isinstance(timestamp_str, str):
            # Remove timezone if present and parse
            clean_timestamp = timestamp_str.replace('Z', '').replace('+00:00', '')
            dt = datetime.fromisoformat(clean_timestamp)
        else:
            dt = timestamp_str
        
        # Convert to milliseconds since epoch
        timestamp_ms = int(dt.timestamp() * 1000)
        
        # Align to timeframe boundaries
        # For 1m: align to minute boundary
        # For 5m: align to 5-minute boundary  
        # For 1h: align to hour boundary
        aligned_ms = (timestamp_ms // timeframe_ms) * timeframe_ms
        
        return aligned_ms
        
    except Exception as e:
        db_logger.error(f"Error aligning timestamp: {e}")
        # Return original timestamp as fallback
        return int(datetime.now().timestamp() * 1000)

def _calculate_chart_bounds(self, prices: List[float], timestamps: List[int]) -> Dict[str, float]:
    """
    Calculate optimal chart display bounds including execution price range with padding.
    """
    if not prices or not timestamps:
        return {
            'min_timestamp': 0,
            'max_timestamp': 0,
            'min_price': 0.0,
            'max_price': 0.0
        }
    
    min_price = min(prices)
    max_price = max(prices)
    min_timestamp = min(timestamps)
    max_timestamp = max(timestamps)
    
    # Add 5-point padding to price range for better visualization
    price_padding = 5.0
    
    # Add 10% time padding on both sides
    time_range = max_timestamp - min_timestamp
    time_padding = max(int(time_range * 0.1), 300000)  # At least 5 minutes
    
    return {
        'min_timestamp': min_timestamp - time_padding,
        'max_timestamp': max_timestamp + time_padding,
        'min_price': min_price - price_padding,
        'max_price': max_price + price_padding
    }

def _filter_executions_by_date(self, executions: List[Dict[str, Any]], start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """
    Filter executions by date range if specified.
    """
    if not start_date and not end_date:
        return executions
    
    try:
        filtered = []
        
        for execution in executions:
            exec_time = datetime.fromisoformat(execution['timestamp'].replace('Z', '').replace('+00:00', ''))
            
            # Check start date
            if start_date:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '').replace('+00:00', ''))
                if exec_time < start_dt:
                    continue
            
            # Check end date  
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '').replace('+00:00', ''))
                if exec_time > end_dt:
                    continue
            
            filtered.append(execution)
        
        return filtered
        
    except Exception as e:
        db_logger.error(f"Error filtering executions by date: {e}")
        return executions


def _generate_execution_cache_key(self, position_id: int, timeframe: str, start_date: str = None, end_date: str = None) -> str:
    """
    Generate consistent cache key for execution chart data.
    """
    key_data = f"exec_chart:{position_id}:{timeframe}:{start_date or 'None'}:{end_date or 'None'}"
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
    return f"execution_chart:{position_id}:{timeframe}:{key_hash}"

def get_cached_execution_chart_data(self, position_id: int, timeframe: str, start_date: str = None, end_date: str = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached execution chart data if available.
    """
    try:
        # Try to get Redis client from the class or import it
        redis_client = getattr(self, 'redis_client', None)
        if not redis_client:
            try:
                from services.redis_cache_service import RedisCacheService
                cache_service = RedisCacheService()
                redis_client = cache_service.redis_client
            except:
                return None
        
        if not redis_client:
            return None
        
        cache_key = self._generate_execution_cache_key(position_id, timeframe, start_date, end_date)
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            data = json.loads(cached_data)
            db_logger.debug(f"Execution chart cache HIT for position {position_id} {timeframe}")
            return data
        else:
            db_logger.debug(f"Execution chart cache MISS for position {position_id} {timeframe}")
            return None
            
    except Exception as e:
        db_logger.error(f"Error retrieving cached execution chart data: {e}")
        return None

def cache_execution_chart_data(self, position_id: int, timeframe: str, data: Dict[str, Any], 
                               start_date: str = None, end_date: str = None, ttl_hours: int = 2) -> bool:
    """
    Cache execution chart data with shorter TTL since positions change less frequently.
    
    Args:
        position_id: Position identifier
        timeframe: Chart timeframe
        data: Execution chart data to cache
        start_date: Optional start date filter
        end_date: Optional end date filter
        ttl_hours: Cache TTL in hours (default: 2 hours)
    """
    try:
        # Try to get Redis client from the class or import it
        redis_client = getattr(self, 'redis_client', None)
        if not redis_client:
            try:
                from services.redis_cache_service import RedisCacheService
                cache_service = RedisCacheService()
                redis_client = cache_service.redis_client
            except:
                return False
        
        if not redis_client:
            return False
        
        cache_key = self._generate_execution_cache_key(position_id, timeframe, start_date, end_date)
        ttl_seconds = ttl_hours * 60 * 60  # Convert hours to seconds
        
        # Store data with expiration
        redis_client.setex(
            cache_key,
            ttl_seconds,
            json.dumps(data, default=str)
        )
        
        db_logger.info(f"Cached execution chart data for position {position_id} {timeframe} (TTL: {ttl_hours} hours)")
        return True
        
    except Exception as e:
        db_logger.error(f"Error caching execution chart data: {e}")
        return False

def get_position_executions_for_chart_cached(self, position_id: int, timeframe: str = '1h', start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Enhanced version of get_position_executions_for_chart with Redis caching.
    
    This method first checks the cache, and if not found, computes the data and caches it.
    """
    try:
        # Try to get from cache first
        cached_data = self.get_cached_execution_chart_data(position_id, timeframe, start_date, end_date)
        if cached_data:
            return cached_data
        
        # Cache miss - compute the data
        chart_data = self.get_position_executions_for_chart(position_id, timeframe, start_date, end_date)
        
        # Cache the result if successful
        if chart_data:
            self.cache_execution_chart_data(position_id, timeframe, chart_data, start_date, end_date)
        
        return chart_data
        
    except Exception as e:
        db_logger.error(f"Error getting cached execution chart data: {e}")
        # Fallback to non-cached version
        return self.get_position_executions_for_chart(position_id, timeframe, start_date, end_date)

def invalidate_execution_chart_cache(self, position_id: int) -> bool:
    """
    Invalidate all cached execution chart data for a position.
    
    This should be called when position data is updated.
    """
    try:
        # Try to get Redis client
        redis_client = getattr(self, 'redis_client', None)
        if not redis_client:
            try:
                from services.redis_cache_service import RedisCacheService
                cache_service = RedisCacheService()
                redis_client = cache_service.redis_client
            except:
                return False
        
        if not redis_client:
            return False
        
        # Find all cache keys for this position
        pattern = f"execution_chart:{position_id}:*"
        keys = redis_client.keys(pattern)
        
        if keys:
            redis_client.delete(*keys)
            db_logger.info(f"Invalidated {len(keys)} execution chart cache entries for position {position_id}")
        
        return True
        
    except Exception as e:
        db_logger.error(f"Error invalidating execution chart cache: {e}")
        return False


# Monkey patch the methods into FuturesDB class
def patch_futures_db():
    """
    Add the chart execution methods to the FuturesDB class.
    """
    from scripts.TradingLog_db import FuturesDB
    
    FuturesDB.get_position_executions_for_chart = get_position_executions_for_chart
    FuturesDB._format_execution_for_chart = _format_execution_for_chart
    FuturesDB._align_timestamp_to_timeframe = _align_timestamp_to_timeframe
    FuturesDB._calculate_chart_bounds = _calculate_chart_bounds
    FuturesDB._filter_executions_by_date = _filter_executions_by_date
    
    # Add caching methods
    FuturesDB._generate_execution_cache_key = _generate_execution_cache_key
    FuturesDB.get_cached_execution_chart_data = get_cached_execution_chart_data
    FuturesDB.cache_execution_chart_data = cache_execution_chart_data
    FuturesDB.get_position_executions_for_chart_cached = get_position_executions_for_chart_cached
    FuturesDB.invalidate_execution_chart_cache = invalidate_execution_chart_cache


# Auto-patch when module is imported
patch_futures_db()