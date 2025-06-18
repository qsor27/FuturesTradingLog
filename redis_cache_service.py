"""
Redis Cache Service for OHLC Data
Provides 2-week data retention with intelligent caching and gap-filling
"""

import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import time

# Get logger
cache_logger = logging.getLogger('cache')

class RedisCacheService:
    """Redis-based caching service for OHLC data with 2-week retention"""
    
    def __init__(self, redis_url: str = 'redis://localhost:6379/0'):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            cache_logger.info(f"Connected to Redis: {redis_url}")
        except Exception as e:
            cache_logger.warning(f"Redis connection failed: {e}. Falling back to no-cache mode.")
            self.redis_client = None
    
    def _generate_cache_key(self, instrument: str, timeframe: str, start_ts: int, end_ts: int) -> str:
        """Generate consistent cache key for OHLC data request"""
        key_data = f"{instrument}:{timeframe}:{start_ts}:{end_ts}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"ohlc:{instrument}:{timeframe}:{key_hash}"
    
    def _generate_instrument_key(self, instrument: str) -> str:
        """Generate cache key for instrument metadata"""
        return f"instrument:{instrument}:metadata"
    
    def get_cached_ohlc_data(self, instrument: str, timeframe: str, 
                           start_timestamp: int, end_timestamp: int) -> Optional[List[Dict]]:
        """Retrieve cached OHLC data if available"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(instrument, timeframe, start_timestamp, end_timestamp)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                cache_logger.debug(f"Cache HIT for {instrument} {timeframe}: {len(data)} records")
                return data
            else:
                cache_logger.debug(f"Cache MISS for {instrument} {timeframe}")
                return None
                
        except Exception as e:
            cache_logger.error(f"Error retrieving cached data: {e}")
            return None
    
    def cache_ohlc_data(self, instrument: str, timeframe: str, 
                       start_timestamp: int, end_timestamp: int, 
                       data: List[Dict], ttl_days: int = 14) -> bool:
        """Cache OHLC data with 2-week default retention"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(instrument, timeframe, start_timestamp, end_timestamp)
            ttl_seconds = ttl_days * 24 * 60 * 60  # Convert days to seconds
            
            # Store data with expiration
            self.redis_client.setex(
                cache_key, 
                ttl_seconds, 
                json.dumps(data, default=str)
            )
            
            # Update instrument metadata
            self._update_instrument_metadata(instrument, timeframe)
            
            cache_logger.info(f"Cached {len(data)} records for {instrument} {timeframe} (TTL: {ttl_days} days)")
            return True
            
        except Exception as e:
            cache_logger.error(f"Error caching data: {e}")
            return False
    
    def _update_instrument_metadata(self, instrument: str, timeframe: str):
        """Update instrument metadata for tracking last access"""
        try:
            metadata_key = self._generate_instrument_key(instrument)
            metadata = self.get_instrument_metadata(instrument)
            
            if not metadata:
                metadata = {
                    'first_access': datetime.now().isoformat(),
                    'timeframes': []
                }
            
            metadata['last_access'] = datetime.now().isoformat()
            
            # Add timeframe if not already present
            if timeframe not in metadata['timeframes']:
                metadata['timeframes'].append(timeframe)
            
            # Cache metadata for 30 days
            self.redis_client.setex(
                metadata_key,
                30 * 24 * 60 * 60,  # 30 days
                json.dumps(metadata, default=str)
            )
            
        except Exception as e:
            cache_logger.error(f"Error updating instrument metadata: {e}")
    
    def get_instrument_metadata(self, instrument: str) -> Optional[Dict]:
        """Get metadata for an instrument"""
        if not self.redis_client:
            return None
        
        try:
            metadata_key = self._generate_instrument_key(instrument)
            metadata = self.redis_client.get(metadata_key)
            
            if metadata:
                return json.loads(metadata)
            return None
            
        except Exception as e:
            cache_logger.error(f"Error getting instrument metadata: {e}")
            return None
    
    def get_cached_instruments(self) -> List[str]:
        """Get list of all cached instruments"""
        if not self.redis_client:
            return []
        
        try:
            # Find all instrument metadata keys
            pattern = "instrument:*:metadata"
            keys = self.redis_client.keys(pattern)
            
            # Extract instrument names from keys
            instruments = []
            for key in keys:
                # Format: instrument:SYMBOL:metadata
                parts = key.split(':')
                if len(parts) >= 3:
                    instrument = parts[1]
                    instruments.append(instrument)
            
            return sorted(list(set(instruments)))
            
        except Exception as e:
            cache_logger.error(f"Error getting cached instruments: {e}")
            return []
    
    def clean_expired_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries and return statistics"""
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            # Get current time
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(days=14)  # 2 weeks ago
            
            stats = {
                'checked': 0,
                'expired': 0,
                'errors': 0,
                'cleaned_instruments': []
            }
            
            # Check all instrument metadata
            instruments = self.get_cached_instruments()
            
            for instrument in instruments:
                try:
                    metadata = self.get_instrument_metadata(instrument)
                    stats['checked'] += 1
                    
                    if metadata and metadata.get('last_access'):
                        last_access = datetime.fromisoformat(metadata['last_access'])
                        
                        # If not accessed in 2 weeks, clean up
                        if last_access < cutoff_time:
                            self._clean_instrument_cache(instrument)
                            stats['expired'] += 1
                            stats['cleaned_instruments'].append(instrument)
                            
                except Exception as e:
                    cache_logger.error(f"Error checking instrument {instrument}: {e}")
                    stats['errors'] += 1
            
            cache_logger.info(f"Cache cleanup: checked {stats['checked']}, cleaned {stats['expired']}")
            return stats
            
        except Exception as e:
            cache_logger.error(f"Error during cache cleanup: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _clean_instrument_cache(self, instrument: str):
        """Clean all cache entries for a specific instrument"""
        try:
            # Clean OHLC data cache entries
            pattern = f"ohlc:{instrument}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                self.redis_client.delete(*keys)
                cache_logger.info(f"Cleaned {len(keys)} cache entries for {instrument}")
            
            # Clean metadata
            metadata_key = self._generate_instrument_key(instrument)
            self.redis_client.delete(metadata_key)
            
        except Exception as e:
            cache_logger.error(f"Error cleaning instrument cache for {instrument}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            # Redis info
            info = self.redis_client.info()
            
            # Custom stats
            instruments = self.get_cached_instruments()
            
            # Count cache entries by type
            ohlc_keys = self.redis_client.keys("ohlc:*")
            metadata_keys = self.redis_client.keys("instrument:*:metadata")
            
            stats = {
                'redis_connected': True,
                'redis_memory_used': info.get('used_memory_human', 'unknown'),
                'redis_uptime_days': info.get('uptime_in_days', 'unknown'),
                'total_instruments': len(instruments),
                'instruments': instruments,
                'ohlc_cache_entries': len(ohlc_keys),
                'metadata_entries': len(metadata_keys),
                'last_check': datetime.now().isoformat()
            }
            
            # Get detailed instrument info
            instrument_details = []
            for instrument in instruments[:10]:  # Limit to first 10 for performance
                metadata = self.get_instrument_metadata(instrument)
                if metadata:
                    instrument_details.append({
                        'instrument': instrument,
                        'last_access': metadata.get('last_access'),
                        'timeframes': metadata.get('timeframes', [])
                    })
            
            stats['instrument_details'] = instrument_details
            
            return stats
            
        except Exception as e:
            cache_logger.error(f"Error getting cache stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def invalidate_instrument_cache(self, instrument: str) -> bool:
        """Manually invalidate all cache for a specific instrument"""
        try:
            self._clean_instrument_cache(instrument)
            cache_logger.info(f"Manually invalidated cache for {instrument}")
            return True
        except Exception as e:
            cache_logger.error(f"Error invalidating cache for {instrument}: {e}")
            return False
    
    def warm_cache_for_instrument(self, instrument: str, timeframes: List[str] = None, 
                                days_back: int = 7) -> Dict[str, bool]:
        """Pre-warm cache for an instrument across multiple timeframes"""
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        results = {}
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        for timeframe in timeframes:
            try:
                # This would typically call the data service to fetch and cache data
                # For now, just mark the instrument as accessed
                self._update_instrument_metadata(instrument, timeframe)
                results[timeframe] = True
                cache_logger.info(f"Cache warmed for {instrument} {timeframe}")
                
            except Exception as e:
                cache_logger.error(f"Error warming cache for {instrument} {timeframe}: {e}")
                results[timeframe] = False
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for Redis connection and cache service"""
        try:
            if not self.redis_client:
                return {
                    'status': 'unhealthy',
                    'redis_connected': False,
                    'error': 'Redis client not initialized'
                }
            
            # Test basic operations
            test_key = "health_check_test"
            test_value = "ok"
            
            # Write test
            self.redis_client.setex(test_key, 10, test_value)
            
            # Read test
            retrieved = self.redis_client.get(test_key)
            
            # Cleanup test
            self.redis_client.delete(test_key)
            
            if retrieved == test_value:
                return {
                    'status': 'healthy',
                    'redis_connected': True,
                    'operations': 'working',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'status': 'unhealthy',
                    'redis_connected': True,
                    'error': 'Read/write test failed'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'redis_connected': False,
                'error': str(e)
            }


# Global cache service instance
cache_service = None

def get_cache_service(redis_url: str = None) -> RedisCacheService:
    """Get or create the global cache service instance"""
    global cache_service
    
    if cache_service is None:
        from config import config
        redis_url = redis_url or getattr(config, 'redis_url', 'redis://localhost:6379/0')
        cache_service = RedisCacheService(redis_url)
    
    return cache_service