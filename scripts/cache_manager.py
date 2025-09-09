"""
Enhanced Cache Management with Explicit Invalidation

Implements Gemini's recommendations for:
- Structured cache key naming conventions
- Explicit invalidation on data changes
- Cache management utilities
"""

import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import hashlib

from services.redis_cache_service import get_cache_service
from config import config

logger = logging.getLogger(__name__)


class CacheKeyManager:
    """Manages structured cache key naming conventions"""
    
    # Key prefixes for different data types
    CHART_OHLC = "chart:ohlc"
    CHART_VOLUME = "chart:volume"
    POSITION_DATA = "position:data"
    INSTRUMENT_META = "instrument:meta"
    USER_SETTINGS = "user:settings"
    VALIDATION_STATUS = "validation:status"
    
    @classmethod
    def chart_ohlc_key(cls, instrument: str, resolution: str, start_ts: int = None, end_ts: int = None) -> str:
        """
        Generate chart OHLC cache key.
        Format: chart:ohlc:instrument:resolution[:hash]
        """
        base_key = f"{cls.CHART_OHLC}:{instrument}:{resolution}"
        
        if start_ts and end_ts:
            # Add hash for specific time range
            time_hash = hashlib.md5(f"{start_ts}:{end_ts}".encode()).hexdigest()[:8]
            return f"{base_key}:{time_hash}"
        
        return base_key
    
    @classmethod
    def chart_volume_key(cls, instrument: str, resolution: str) -> str:
        """Generate chart volume cache key"""
        return f"{cls.CHART_VOLUME}:{instrument}:{resolution}"
    
    @classmethod
    def position_data_key(cls, account: str, instrument: str = None) -> str:
        """Generate position data cache key"""
        if instrument:
            return f"{cls.POSITION_DATA}:{account}:{instrument}"
        return f"{cls.POSITION_DATA}:{account}"
    
    @classmethod
    def instrument_meta_key(cls, instrument: str) -> str:
        """Generate instrument metadata cache key"""
        return f"{cls.INSTRUMENT_META}:{instrument}"
    
    @classmethod
    def user_settings_key(cls, user_id: str, setting_type: str) -> str:
        """Generate user settings cache key"""
        return f"{cls.USER_SETTINGS}:{user_id}:{setting_type}"
    
    @classmethod
    def validation_status_key(cls, account: str) -> str:
        """Generate validation status cache key"""
        return f"{cls.VALIDATION_STATUS}:{account}"
    
    @classmethod
    def get_pattern_for_instrument(cls, instrument: str) -> List[str]:
        """Get all cache key patterns for an instrument"""
        return [
            f"{cls.CHART_OHLC}:{instrument}:*",
            f"{cls.CHART_VOLUME}:{instrument}:*",
            f"{cls.POSITION_DATA}:*:{instrument}",
            f"{cls.INSTRUMENT_META}:{instrument}",
        ]
    
    @classmethod
    def get_pattern_for_account(cls, account: str) -> List[str]:
        """Get all cache key patterns for an account"""
        return [
            f"{cls.POSITION_DATA}:{account}:*",
            f"{cls.VALIDATION_STATUS}:{account}",
        ]


class CacheInvalidator:
    """Handles explicit cache invalidation on data changes"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
        self.redis_client = self.cache_service.redis_client if self.cache_service else None
        
    def invalidate_instrument_data(self, instrument: str) -> Dict[str, Any]:
        """
        Invalidate all cache entries for an instrument.
        Called when new trade data is imported for that instrument.
        """
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            results = {
                'instrument': instrument,
                'patterns_checked': 0,
                'keys_deleted': 0,
                'errors': []
            }
            
            # Get all patterns for this instrument
            patterns = CacheKeyManager.get_pattern_for_instrument(instrument)
            
            for pattern in patterns:
                try:
                    keys = self.redis_client.keys(pattern)
                    results['patterns_checked'] += 1
                    
                    if keys:
                        self.redis_client.delete(*keys)
                        results['keys_deleted'] += len(keys)
                        logger.info(f"Deleted {len(keys)} cache keys for pattern: {pattern}")
                    
                except Exception as e:
                    error_msg = f"Error processing pattern {pattern}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            logger.info(f"Cache invalidation for {instrument}: {results['keys_deleted']} keys deleted")
            return results
            
        except Exception as e:
            error_msg = f"Cache invalidation failed for {instrument}: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
    
    def invalidate_account_data(self, account: str) -> Dict[str, Any]:
        """
        Invalidate all cache entries for an account.
        Called when positions are rebuilt for that account.
        """
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            results = {
                'account': account,
                'patterns_checked': 0,
                'keys_deleted': 0,
                'errors': []
            }
            
            # Get all patterns for this account
            patterns = CacheKeyManager.get_pattern_for_account(account)
            
            for pattern in patterns:
                try:
                    keys = self.redis_client.keys(pattern)
                    results['patterns_checked'] += 1
                    
                    if keys:
                        self.redis_client.delete(*keys)
                        results['keys_deleted'] += len(keys)
                        logger.info(f"Deleted {len(keys)} cache keys for pattern: {pattern}")
                    
                except Exception as e:
                    error_msg = f"Error processing pattern {pattern}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            logger.info(f"Cache invalidation for account {account}: {results['keys_deleted']} keys deleted")
            return results
            
        except Exception as e:
            error_msg = f"Cache invalidation failed for account {account}: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
    
    def invalidate_chart_data(self, instrument: str, resolution: str = None) -> Dict[str, Any]:
        """
        Invalidate chart data cache for specific instrument and optionally resolution.
        Called when OHLC data is updated.
        """
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            results = {
                'instrument': instrument,
                'resolution': resolution,
                'keys_deleted': 0,
                'errors': []
            }
            
            # Build patterns
            if resolution:
                patterns = [
                    f"{CacheKeyManager.CHART_OHLC}:{instrument}:{resolution}:*",
                    f"{CacheKeyManager.CHART_VOLUME}:{instrument}:{resolution}"
                ]
            else:
                patterns = [
                    f"{CacheKeyManager.CHART_OHLC}:{instrument}:*",
                    f"{CacheKeyManager.CHART_VOLUME}:{instrument}:*"
                ]
            
            for pattern in patterns:
                try:
                    keys = self.redis_client.keys(pattern)
                    
                    if keys:
                        self.redis_client.delete(*keys)
                        results['keys_deleted'] += len(keys)
                        logger.info(f"Deleted {len(keys)} chart cache keys for pattern: {pattern}")
                    
                except Exception as e:
                    error_msg = f"Error processing pattern {pattern}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            logger.info(f"Chart cache invalidation for {instrument}: {results['keys_deleted']} keys deleted")
            return results
            
        except Exception as e:
            error_msg = f"Chart cache invalidation failed for {instrument}: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
    
    def invalidate_position_validation(self, account: str = None) -> Dict[str, Any]:
        """
        Invalidate position validation cache.
        Called when positions are rebuilt or validation data changes.
        """
        if not self.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            results = {
                'account': account,
                'keys_deleted': 0,
                'errors': []
            }
            
            # Build pattern
            if account:
                pattern = f"{CacheKeyManager.VALIDATION_STATUS}:{account}"
            else:
                pattern = f"{CacheKeyManager.VALIDATION_STATUS}:*"
            
            try:
                keys = self.redis_client.keys(pattern)
                
                if keys:
                    self.redis_client.delete(*keys)
                    results['keys_deleted'] += len(keys)
                    logger.info(f"Deleted {len(keys)} validation cache keys")
                
            except Exception as e:
                error_msg = f"Error processing validation pattern: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
            
            logger.info(f"Validation cache invalidation: {results['keys_deleted']} keys deleted")
            return results
            
        except Exception as e:
            error_msg = f"Validation cache invalidation failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
    
    def bulk_invalidate(self, instruments: List[str] = None, accounts: List[str] = None) -> Dict[str, Any]:
        """
        Bulk invalidate cache for multiple instruments/accounts.
        Useful for major data imports or system maintenance.
        """
        results = {
            'instruments_processed': 0,
            'accounts_processed': 0,
            'total_keys_deleted': 0,
            'errors': []
        }
        
        # Process instruments
        if instruments:
            for instrument in instruments:
                try:
                    result = self.invalidate_instrument_data(instrument)
                    if result.get('keys_deleted'):
                        results['total_keys_deleted'] += result['keys_deleted']
                    results['instruments_processed'] += 1
                except Exception as e:
                    results['errors'].append(f"Instrument {instrument}: {str(e)}")
        
        # Process accounts
        if accounts:
            for account in accounts:
                try:
                    result = self.invalidate_account_data(account)
                    if result.get('keys_deleted'):
                        results['total_keys_deleted'] += result['keys_deleted']
                    results['accounts_processed'] += 1
                except Exception as e:
                    results['errors'].append(f"Account {account}: {str(e)}")
        
        logger.info(f"Bulk invalidation: {results['total_keys_deleted']} total keys deleted")
        return results


class CacheManager:
    """Main cache management interface"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
        self.invalidator = CacheInvalidator()
        self.key_manager = CacheKeyManager()
    
    def on_trade_import(self, instruments: List[str], accounts: List[str]) -> Dict[str, Any]:
        """
        Handle cache invalidation after trade import.
        This is the main integration point for the position processing pipeline.
        """
        logger.info(f"Handling cache invalidation for trade import: {len(instruments)} instruments, {len(accounts)} accounts")
        
        results = {
            'triggered_by': 'trade_import',
            'timestamp': datetime.now().isoformat(),
            'instruments': instruments,
            'accounts': accounts,
            'invalidation_results': {}
        }
        
        # Invalidate instrument data (affects charts)
        if instruments:
            for instrument in instruments:
                try:
                    result = self.invalidator.invalidate_instrument_data(instrument)
                    results['invalidation_results'][f'instrument_{instrument}'] = result
                except Exception as e:
                    logger.error(f"Failed to invalidate instrument {instrument}: {e}")
                    results['invalidation_results'][f'instrument_{instrument}'] = {'error': str(e)}
        
        # Invalidate account data (affects positions)
        if accounts:
            for account in accounts:
                try:
                    result = self.invalidator.invalidate_account_data(account)
                    results['invalidation_results'][f'account_{account}'] = result
                except Exception as e:
                    logger.error(f"Failed to invalidate account {account}: {e}")
                    results['invalidation_results'][f'account_{account}'] = {'error': str(e)}
        
        # Invalidate validation cache
        try:
            result = self.invalidator.invalidate_position_validation()
            results['invalidation_results']['validation'] = result
        except Exception as e:
            logger.error(f"Failed to invalidate validation cache: {e}")
            results['invalidation_results']['validation'] = {'error': str(e)}
        
        return results
    
    def on_position_rebuild(self, account: str, instruments: List[str] = None) -> Dict[str, Any]:
        """
        Handle cache invalidation after position rebuild.
        """
        logger.info(f"Handling cache invalidation for position rebuild: account {account}")
        
        results = {
            'triggered_by': 'position_rebuild',
            'timestamp': datetime.now().isoformat(),
            'account': account,
            'instruments': instruments,
            'invalidation_results': {}
        }
        
        # Invalidate account data
        try:
            result = self.invalidator.invalidate_account_data(account)
            results['invalidation_results']['account'] = result
        except Exception as e:
            logger.error(f"Failed to invalidate account data: {e}")
            results['invalidation_results']['account'] = {'error': str(e)}
        
        # Invalidate specific instruments if provided
        if instruments:
            for instrument in instruments:
                try:
                    result = self.invalidator.invalidate_chart_data(instrument)
                    results['invalidation_results'][f'instrument_{instrument}'] = result
                except Exception as e:
                    logger.error(f"Failed to invalidate instrument {instrument}: {e}")
                    results['invalidation_results'][f'instrument_{instrument}'] = {'error': str(e)}
        
        # Invalidate validation cache for account
        try:
            result = self.invalidator.invalidate_position_validation(account)
            results['invalidation_results']['validation'] = result
        except Exception as e:
            logger.error(f"Failed to invalidate validation cache: {e}")
            results['invalidation_results']['validation'] = {'error': str(e)}
        
        return results
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get comprehensive cache status and statistics"""
        if not self.cache_service or not self.cache_service.redis_client:
            return {'status': 'redis_unavailable'}
        
        try:
            # Basic Redis stats
            stats = self.cache_service.get_cache_stats()
            
            # Enhanced stats with key breakdown
            redis_client = self.cache_service.redis_client
            
            # Count keys by type
            key_counts = {}
            for prefix in [CacheKeyManager.CHART_OHLC, CacheKeyManager.CHART_VOLUME, 
                          CacheKeyManager.POSITION_DATA, CacheKeyManager.INSTRUMENT_META,
                          CacheKeyManager.USER_SETTINGS, CacheKeyManager.VALIDATION_STATUS]:
                pattern = f"{prefix}:*"
                keys = redis_client.keys(pattern)
                key_counts[prefix] = len(keys)
            
            stats['key_counts_by_type'] = key_counts
            stats['cache_manager_version'] = '1.0'
            stats['structured_keys'] = True
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def manual_cleanup(self, older_than_days: int = 14) -> Dict[str, Any]:
        """Manual cache cleanup for maintenance"""
        if not self.cache_service:
            return {'status': 'cache_service_unavailable'}
        
        try:
            logger.info(f"Starting manual cache cleanup for entries older than {older_than_days} days")
            
            # Use existing cleanup method
            result = self.cache_service.clean_expired_cache()
            
            # Add timestamp
            result['cleanup_triggered'] = 'manual'
            result['cleanup_time'] = datetime.now().isoformat()
            result['older_than_days'] = older_than_days
            
            return result
            
        except Exception as e:
            logger.error(f"Manual cache cleanup failed: {e}")
            return {'status': 'error', 'error': str(e)}


# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager instance"""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = CacheManager()
    
    return _cache_manager