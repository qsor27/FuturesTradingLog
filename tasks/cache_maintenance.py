"""
Cache Maintenance Tasks

Celery tasks for Redis cache cleanup, optimization, and monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from celery import Task
from celery_app import app
from config import config
from redis_cache_service import get_cache_service

logger = logging.getLogger('cache_maintenance')


class CallbackTask(Task):
    """Base task class with error handling and monitoring"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f'Cache maintenance task {task_id} failed: {exc}')
        logger.error(f'Exception info: {einfo}')
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f'Cache maintenance task {task_id} completed successfully')


@app.task(base=CallbackTask, bind=True)
def cleanup_expired_cache(self):
    """
    Clean up expired cache entries and optimize cache usage
    Scheduled to run daily at 2 AM
    """
    try:
        logger.info("Starting cache cleanup and maintenance")
        
        cache_service = get_cache_service()
        if not cache_service:
            logger.info("Cache service not available, skipping cleanup")
            return {'status': 'skipped', 'reason': 'cache_not_available'}
        
        # Get cache statistics before cleanup
        initial_stats = _get_cache_stats(cache_service)
        
        # Clean up expired keys
        expired_keys_deleted = _cleanup_expired_keys(cache_service)
        
        # Clean up old chart data cache
        old_chart_keys_deleted = _cleanup_old_chart_cache(cache_service)
        
        # Clean up orphaned cache keys
        orphaned_keys_deleted = _cleanup_orphaned_keys(cache_service)
        
        # Optimize memory usage
        memory_optimized = _optimize_cache_memory(cache_service)
        
        # Get cache statistics after cleanup
        final_stats = _get_cache_stats(cache_service)
        
        total_deleted = expired_keys_deleted + old_chart_keys_deleted + orphaned_keys_deleted
        
        logger.info(f"Cache cleanup completed: {total_deleted} keys deleted, memory optimization: {memory_optimized}")
        
        return {
            'status': 'success',
            'expired_keys_deleted': expired_keys_deleted,
            'old_chart_keys_deleted': old_chart_keys_deleted,
            'orphaned_keys_deleted': orphaned_keys_deleted,
            'total_keys_deleted': total_deleted,
            'memory_optimized': memory_optimized,
            'stats_before': initial_stats,
            'stats_after': final_stats
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_cache: {e}")
        raise self.retry(exc=e, countdown=3600, max_retries=2)  # 1 hour delay


@app.task(base=CallbackTask, bind=True)
def warm_cache_for_instruments(self, instruments: List[str] = None):
    """
    Pre-warm cache for frequently accessed instruments
    
    Args:
        instruments: List of instruments to warm cache for (defaults to active instruments)
    """
    try:
        cache_service = get_cache_service()
        if not cache_service:
            logger.info("Cache service not available, skipping cache warming")
            return {'status': 'skipped', 'reason': 'cache_not_available'}
        
        if not instruments:
            instruments = _get_active_instruments()
        
        if not instruments:
            logger.info("No instruments found for cache warming")
            return {'status': 'no_instruments', 'warmed_instruments': 0}
        
        logger.info(f"Warming cache for {len(instruments)} instruments: {instruments}")
        
        warmed_count = 0
        results = {}
        
        for instrument in instruments:
            try:
                # Warm cache for common timeframes and ranges
                instrument_results = _warm_instrument_cache(cache_service, instrument)
                results[instrument] = instrument_results
                
                if instrument_results.get('success', False):
                    warmed_count += 1
                    logger.info(f"Cache warmed for {instrument}")
                    
            except Exception as e:
                logger.error(f"Error warming cache for {instrument}: {e}")
                results[instrument] = {'success': False, 'error': str(e)}
        
        return {
            'status': 'success',
            'warmed_instruments': warmed_count,
            'total_instruments': len(instruments),
            'details': results
        }
        
    except Exception as e:
        logger.error(f"Error in warm_cache_for_instruments: {e}")
        raise self.retry(exc=e, countdown=600, max_retries=2)  # 10 minute delay


@app.task(base=CallbackTask, bind=True)
def monitor_cache_performance(self):
    """
    Monitor cache hit rates and performance metrics
    """
    try:
        cache_service = get_cache_service()
        if not cache_service:
            return {'status': 'skipped', 'reason': 'cache_not_available'}
        
        # Get detailed cache statistics
        stats = _get_detailed_cache_stats(cache_service)
        
        # Calculate performance metrics
        hit_rate = _calculate_hit_rate(stats)
        memory_usage = _calculate_memory_usage(stats)
        
        # Check for performance issues
        warnings = []
        if hit_rate < 0.7:  # Less than 70% hit rate
            warnings.append(f"Low cache hit rate: {hit_rate:.2%}")
        
        if memory_usage > 0.9:  # More than 90% memory usage
            warnings.append(f"High memory usage: {memory_usage:.2%}")
        
        # Log warnings
        for warning in warnings:
            logger.warning(warning)
        
        return {
            'status': 'success',
            'hit_rate': hit_rate,
            'memory_usage': memory_usage,
            'warnings': warnings,
            'detailed_stats': stats
        }
        
    except Exception as e:
        logger.error(f"Error in monitor_cache_performance: {e}")
        return {'status': 'error', 'error': str(e)}


@app.task(base=CallbackTask, bind=True)
def invalidate_cache_pattern(self, pattern: str):
    """
    Invalidate cache keys matching a pattern
    
    Args:
        pattern: Redis pattern to match keys for invalidation
    """
    try:
        cache_service = get_cache_service()
        if not cache_service:
            return {'status': 'skipped', 'reason': 'cache_not_available'}
        
        logger.info(f"Invalidating cache keys matching pattern: {pattern}")
        
        deleted_count = cache_service.delete_pattern(pattern)
        
        logger.info(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
        
        return {
            'status': 'success',
            'pattern': pattern,
            'keys_deleted': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error invalidating cache pattern {pattern}: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


def _get_cache_stats(cache_service) -> Dict[str, Any]:
    """Get basic cache statistics"""
    try:
        info = cache_service.redis.info()
        return {
            'used_memory': info.get('used_memory', 0),
            'used_memory_human': info.get('used_memory_human', '0B'),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'connected_clients': info.get('connected_clients', 0),
            'total_commands_processed': info.get('total_commands_processed', 0)
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}


def _get_detailed_cache_stats(cache_service) -> Dict[str, Any]:
    """Get detailed cache statistics for performance monitoring"""
    try:
        info = cache_service.redis.info()
        memory_info = cache_service.redis.info('memory')
        
        return {
            'memory': {
                'used_memory': memory_info.get('used_memory', 0),
                'used_memory_peak': memory_info.get('used_memory_peak', 0),
                'used_memory_rss': memory_info.get('used_memory_rss', 0),
                'maxmemory': memory_info.get('maxmemory', 0)
            },
            'keyspace': {
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'expires': info.get('expired_keys', 0),
                'evicted': info.get('evicted_keys', 0)
            },
            'connections': {
                'connected_clients': info.get('connected_clients', 0),
                'total_connections_received': info.get('total_connections_received', 0)
            },
            'commands': {
                'total_commands_processed': info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0)
            }
        }
    except Exception as e:
        logger.error(f"Error getting detailed cache stats: {e}")
        return {}


def _calculate_hit_rate(stats: Dict[str, Any]) -> float:
    """Calculate cache hit rate"""
    try:
        keyspace = stats.get('keyspace', {})
        hits = keyspace.get('hits', 0)
        misses = keyspace.get('misses', 0)
        
        if hits + misses == 0:
            return 0.0
        
        return hits / (hits + misses)
    except Exception:
        return 0.0


def _calculate_memory_usage(stats: Dict[str, Any]) -> float:
    """Calculate memory usage percentage"""
    try:
        memory = stats.get('memory', {})
        used = memory.get('used_memory', 0)
        max_mem = memory.get('maxmemory', 0)
        
        if max_mem == 0:
            return 0.0
        
        return used / max_mem
    except Exception:
        return 0.0


def _cleanup_expired_keys(cache_service) -> int:
    """Clean up expired cache keys"""
    try:
        # Redis automatically handles expired keys, but we can force cleanup
        # This is more of a monitoring function
        initial_info = cache_service.redis.info()
        initial_expired = initial_info.get('expired_keys', 0)
        
        # Force expiration of some keys by scanning
        cursor = 0
        deleted_count = 0
        
        while True:
            cursor, keys = cache_service.redis.scan(cursor, count=1000)
            
            for key in keys:
                try:
                    ttl = cache_service.redis.ttl(key)
                    if ttl == -2:  # Key is expired
                        cache_service.redis.delete(key)
                        deleted_count += 1
                except Exception:
                    continue
            
            if cursor == 0:
                break
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up expired keys: {e}")
        return 0


def _cleanup_old_chart_cache(cache_service) -> int:
    """Clean up old chart data cache entries"""
    try:
        # Find chart cache keys older than 7 days
        cutoff_timestamp = (datetime.now() - timedelta(days=7)).timestamp()
        
        cursor = 0
        deleted_count = 0
        
        while True:
            cursor, keys = cache_service.redis.scan(cursor, match="chart_data:*", count=1000)
            
            for key in keys:
                try:
                    # Check if key has timestamp information
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
                    
                    # Extract timestamp from key if present
                    # This depends on the key format used in the application
                    if ':ts:' in key_str:
                        timestamp_part = key_str.split(':ts:')[1].split(':')[0]
                        key_timestamp = float(timestamp_part)
                        
                        if key_timestamp < cutoff_timestamp:
                            cache_service.redis.delete(key)
                            deleted_count += 1
                except Exception:
                    continue
            
            if cursor == 0:
                break
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up old chart cache: {e}")
        return 0


def _cleanup_orphaned_keys(cache_service) -> int:
    """Clean up orphaned cache keys that no longer have valid data"""
    try:
        # This would involve checking if the referenced data still exists
        # For now, we'll implement a simple pattern-based cleanup
        
        orphaned_patterns = [
            "temp:*",  # Temporary keys
            "session:*",  # Old session keys
            "lock:*"  # Lock keys that might be stuck
        ]
        
        deleted_count = 0
        
        for pattern in orphaned_patterns:
            try:
                cursor = 0
                while True:
                    cursor, keys = cache_service.redis.scan(cursor, match=pattern, count=1000)
                    
                    for key in keys:
                        try:
                            # Check if key is older than 1 hour for temp keys
                            if pattern.startswith("temp:") or pattern.startswith("lock:"):
                                ttl = cache_service.redis.ttl(key)
                                if ttl == -1:  # No expiration set
                                    cache_service.redis.delete(key)
                                    deleted_count += 1
                        except Exception:
                            continue
                    
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"Error cleaning up pattern {pattern}: {e}")
                continue
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up orphaned keys: {e}")
        return 0


def _optimize_cache_memory(cache_service) -> bool:
    """Optimize cache memory usage"""
    try:
        # Run memory optimization commands
        cache_service.redis.memory_purge()  # Redis 4.0+
        return True
    except Exception as e:
        logger.warning(f"Could not optimize cache memory: {e}")
        return False


def _get_active_instruments() -> List[str]:
    """Get list of instruments that have recent trade data"""
    try:
        from database_manager import DatabaseManager
        
        with DatabaseManager() as db:
            # Get instruments with trades in the last 7 days
            cutoff_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            instruments_query = """
                SELECT DISTINCT instrument 
                FROM trades 
                WHERE entry_time >= ? 
                AND deleted = 0 
                AND instrument IS NOT NULL
                ORDER BY instrument
            """
            
            result = db.cursor.execute(instruments_query, (cutoff_date,))
            instruments = [row[0] for row in result.fetchall()]
            
            return instruments
            
    except Exception as e:
        logger.error(f"Error getting active instruments: {e}")
        return []


def _warm_instrument_cache(cache_service, instrument: str) -> Dict[str, Any]:
    """Warm cache for a specific instrument"""
    try:
        # This would involve pre-loading common data patterns
        # For now, return a placeholder implementation
        
        timeframes = ['1h', '4h', '1d']
        ranges = ['1week', '1month']
        
        warmed_keys = 0
        
        for timeframe in timeframes:
            for range_val in ranges:
                try:
                    # Create cache key
                    cache_key = f"chart_data:{instrument}:{timeframe}:{range_val}"
                    
                    # Check if already cached
                    if not cache_service.redis.exists(cache_key):
                        # Would call the actual data loading function here
                        # For now, just create a placeholder
                        cache_service.set(cache_key, {}, timeout=3600)  # 1 hour timeout
                        warmed_keys += 1
                        
                except Exception as e:
                    logger.error(f"Error warming cache key {cache_key}: {e}")
                    continue
        
        return {
            'success': True,
            'warmed_keys': warmed_keys,
            'instrument': instrument
        }
        
    except Exception as e:
        logger.error(f"Error warming cache for instrument {instrument}: {e}")
        return {'success': False, 'error': str(e)}


# Manual task triggers for API endpoints
@app.task(base=CallbackTask)
def trigger_manual_cache_cleanup():
    """Manually trigger cache cleanup (for API endpoints)"""
    return cleanup_expired_cache.delay()


@app.task(base=CallbackTask)
def trigger_cache_warm_up(instruments: List[str] = None):
    """Manually trigger cache warm-up (for API endpoints)"""
    return warm_cache_for_instruments.delay(instruments)