"""
Performance Routes - Handle real-time trader performance API endpoints
"""
import json
import logging
from flask import Blueprint, jsonify
from services.performance_service import get_daily_performance, get_weekly_performance

# Setup logging
logger = logging.getLogger('performance')

# Create blueprint with API prefix
performance_bp = Blueprint('performance', __name__, url_prefix='/api/performance')

# Redis client for caching (try to import, fallback gracefully)
try:
    import redis
    from config import REDIS_CONFIG
    redis_client = redis.Redis(
        host=REDIS_CONFIG.get('host', 'localhost'),
        port=REDIS_CONFIG.get('port', 6379),
        db=REDIS_CONFIG.get('db', 0),
        decode_responses=True
    )
    REDIS_AVAILABLE = True
    logger.info("Redis client initialized for performance caching")
except (ImportError, Exception) as e:
    redis_client = None
    REDIS_AVAILABLE = False
    logger.warning(f"Redis not available for performance caching: {e}")

def get_cached_data(cache_key: str):
    """Get data from Redis cache if available"""
    if not REDIS_AVAILABLE or not redis_client:
        return None
    
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Cache retrieval error for key {cache_key}: {e}")
    
    return None

def set_cached_data(cache_key: str, data: dict, ttl: int = 45):
    """Set data in Redis cache with TTL if available"""
    if not REDIS_AVAILABLE or not redis_client:
        return False
    
    try:
        redis_client.setex(cache_key, ttl, json.dumps(data))
        return True
    except Exception as e:
        logger.warning(f"Cache storage error for key {cache_key}: {e}")
        return False

@performance_bp.route('/daily', methods=['GET'])
def api_daily_performance():
    """
    GET /api/performance/daily
    
    Returns current calendar day trading performance metrics.
    Includes P&L, trade counts, and win/loss statistics.
    
    Returns:
        JSON response with daily performance data
    """
    cache_key = "daily_performance:current_day"
    
    try:
        # Try to get from cache first
        cached_result = get_cached_data(cache_key)
        if cached_result:
            logger.debug("Returning cached daily performance data")
            return jsonify(cached_result)
        
        # Calculate fresh data
        logger.debug("Calculating fresh daily performance data")
        performance_data = get_daily_performance()
        
        # Cache the result
        set_cached_data(cache_key, performance_data, ttl=45)
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(f"Error retrieving daily performance: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to retrieve daily performance data'
        }), 500

@performance_bp.route('/weekly', methods=['GET'])
def api_weekly_performance():
    """
    GET /api/performance/weekly
    
    Returns current calendar week (Monday to Sunday) trading performance metrics.
    Includes P&L, trade counts, and win/loss statistics.
    
    Returns:
        JSON response with weekly performance data
    """
    cache_key = "weekly_performance:current_week"
    
    try:
        # Try to get from cache first
        cached_result = get_cached_data(cache_key)
        if cached_result:
            logger.debug("Returning cached weekly performance data")
            return jsonify(cached_result)
        
        # Calculate fresh data
        logger.debug("Calculating fresh weekly performance data")
        performance_data = get_weekly_performance()
        
        # Cache the result
        set_cached_data(cache_key, performance_data, ttl=60)
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(f"Error retrieving weekly performance: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to retrieve weekly performance data'
        }), 500

@performance_bp.route('/health', methods=['GET'])
def api_performance_health():
    """
    GET /api/performance/health
    
    Health check endpoint for performance API system.
    
    Returns:
        JSON response with system health status
    """
    try:
        # Test database connectivity by getting a simple daily performance
        test_data = get_daily_performance()
        
        # Test Redis connectivity if available
        redis_status = "not_available"
        if REDIS_AVAILABLE and redis_client:
            try:
                redis_client.ping()
                redis_status = "available"
            except Exception:
                redis_status = "error"
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'redis_cache': redis_status,
            'endpoints': ['daily', 'weekly']
        })
        
    except Exception as e:
        logger.error(f"Performance API health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503