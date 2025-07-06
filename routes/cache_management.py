"""
Cache Management API Routes

Provides endpoints for cache status, manual invalidation, and maintenance.
"""

from flask import Blueprint, jsonify, request
import logging
from typing import Dict, Any

try:
    from cache_manager import get_cache_manager
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create blueprint
cache_bp = Blueprint('cache', __name__, url_prefix='/api/cache')


@cache_bp.route('/status', methods=['GET'])
def get_cache_status():
    """Get current cache status and statistics"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        cache_manager = get_cache_manager()
        status = cache_manager.get_cache_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/invalidate/instrument/<instrument>', methods=['POST'])
def invalidate_instrument(instrument: str):
    """Manually invalidate cache for a specific instrument"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        cache_manager = get_cache_manager()
        result = cache_manager.invalidator.invalidate_instrument_data(instrument)
        
        logger.info(f"Manual cache invalidation for instrument {instrument}: {result}")
        return jsonify({
            'status': 'success',
            'instrument': instrument,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error invalidating cache for instrument {instrument}: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/invalidate/account/<account>', methods=['POST'])
def invalidate_account(account: str):
    """Manually invalidate cache for a specific account"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        cache_manager = get_cache_manager()
        result = cache_manager.invalidator.invalidate_account_data(account)
        
        logger.info(f"Manual cache invalidation for account {account}: {result}")
        return jsonify({
            'status': 'success',
            'account': account,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error invalidating cache for account {account}: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/invalidate/chart/<instrument>', methods=['POST'])
def invalidate_chart_data(instrument: str):
    """Manually invalidate chart cache for a specific instrument"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        # Get optional resolution parameter
        resolution = request.json.get('resolution') if request.json else None
        
        cache_manager = get_cache_manager()
        result = cache_manager.invalidator.invalidate_chart_data(instrument, resolution)
        
        logger.info(f"Manual chart cache invalidation for {instrument} (resolution: {resolution}): {result}")
        return jsonify({
            'status': 'success',
            'instrument': instrument,
            'resolution': resolution,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error invalidating chart cache for {instrument}: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/invalidate/validation', methods=['POST'])
def invalidate_validation():
    """Manually invalidate position validation cache"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        # Get optional account parameter
        account = request.json.get('account') if request.json else None
        
        cache_manager = get_cache_manager()
        result = cache_manager.invalidator.invalidate_position_validation(account)
        
        logger.info(f"Manual validation cache invalidation (account: {account}): {result}")
        return jsonify({
            'status': 'success',
            'account': account,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error invalidating validation cache: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/invalidate/bulk', methods=['POST'])
def bulk_invalidate():
    """Bulk invalidate cache for multiple instruments/accounts"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        data = request.get_json() or {}
        instruments = data.get('instruments', [])
        accounts = data.get('accounts', [])
        
        if not instruments and not accounts:
            return jsonify({
                'status': 'error',
                'error': 'Must provide instruments or accounts to invalidate'
            }), 400
        
        cache_manager = get_cache_manager()
        result = cache_manager.invalidator.bulk_invalidate(instruments, accounts)
        
        logger.info(f"Bulk cache invalidation: {result}")
        return jsonify({
            'status': 'success',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error in bulk cache invalidation: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Manually trigger cache cleanup"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'error': 'Cache manager not available'
        }), 503
    
    try:
        data = request.get_json() or {}
        older_than_days = data.get('older_than_days', 14)
        
        cache_manager = get_cache_manager()
        result = cache_manager.manual_cleanup(older_than_days)
        
        logger.info(f"Manual cache cleanup completed: {result}")
        return jsonify({
            'status': 'success',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error in manual cache cleanup: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@cache_bp.route('/health', methods=['GET'])
def cache_health():
    """Cache system health check"""
    if not CACHE_MANAGER_AVAILABLE:
        return jsonify({
            'status': 'unavailable',
            'cache_manager': False,
            'error': 'Cache manager not available'
        }), 503
    
    try:
        cache_manager = get_cache_manager()
        
        # Test basic cache service
        health_status = cache_manager.cache_service.health_check()
        
        return jsonify({
            'status': 'healthy' if health_status.get('status') == 'healthy' else 'unhealthy',
            'cache_manager': True,
            'cache_service': health_status,
            'timestamp': health_status.get('timestamp')
        })
        
    except Exception as e:
        logger.error(f"Error in cache health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'cache_manager': True,
            'error': str(e)
        }), 500


# Error handlers
@cache_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'error': 'Cache endpoint not found'
    }), 404


@cache_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'status': 'error',
        'error': 'Method not allowed'
    }), 405