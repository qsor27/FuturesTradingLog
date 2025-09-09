"""
Test Cache Invalidation System

Simple test to verify the cache invalidation works correctly.
"""

import logging
from cache_manager import get_cache_manager, CacheKeyManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_cache_key_generation():
    """Test cache key generation"""
    print("Testing cache key generation...")
    
    # Test chart OHLC keys
    key1 = CacheKeyManager.chart_ohlc_key("ES 03-24", "1m")
    key2 = CacheKeyManager.chart_ohlc_key("ES 03-24", "1m", 1640995200, 1641081600)
    
    print(f"OHLC key (no time): {key1}")
    print(f"OHLC key (with time): {key2}")
    
    # Test position keys
    pos_key1 = CacheKeyManager.position_data_key("Sim101")
    pos_key2 = CacheKeyManager.position_data_key("Sim101", "ES 03-24")
    
    print(f"Position key (account only): {pos_key1}")
    print(f"Position key (account + instrument): {pos_key2}")
    
    # Test patterns
    patterns = CacheKeyManager.get_pattern_for_instrument("ES 03-24")
    print(f"Patterns for ES 03-24: {patterns}")
    
    print("✓ Cache key generation test passed\n")


def test_cache_invalidation():
    """Test cache invalidation functionality"""
    print("Testing cache invalidation...")
    
    try:
        cache_manager = get_cache_manager()
        
        # Test trade import invalidation
        result = cache_manager.on_trade_import(
            instruments=["ES 03-24", "NQ 03-24"],
            accounts=["Sim101", "Sim102"]
        )
        
        print(f"Trade import invalidation result: {result}")
        
        # Test position rebuild invalidation
        result = cache_manager.on_position_rebuild(
            account="Sim101",
            instruments=["ES 03-24"]
        )
        
        print(f"Position rebuild invalidation result: {result}")
        
        print("✓ Cache invalidation test passed\n")
        
    except Exception as e:
        print(f"✗ Cache invalidation test failed: {e}\n")


def test_cache_status():
    """Test cache status functionality"""
    print("Testing cache status...")
    
    try:
        cache_manager = get_cache_manager()
        status = cache_manager.get_cache_status()
        
        print(f"Cache status: {status}")
        print("✓ Cache status test passed\n")
        
    except Exception as e:
        print(f"✗ Cache status test failed: {e}\n")


def main():
    """Run all tests"""
    print("Starting cache invalidation tests...\n")
    
    test_cache_key_generation()
    test_cache_invalidation()
    test_cache_status()
    
    print("All tests completed!")


if __name__ == "__main__":
    main()