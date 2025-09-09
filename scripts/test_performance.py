#!/usr/bin/env python3
"""
Performance testing script for database optimizations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.TradingLog_db import FuturesDB
import time

def test_database_performance():
    """Test database performance with current optimizations."""
    
    print("🔍 Testing Database Performance")
    print("=" * 50)
    
    with FuturesDB() as db:
        # Get performance analysis
        perf_info = db.analyze_performance()
        
        print(f"📊 Database Statistics:")
        print(f"   Total Trades: {perf_info.get('total_trades', 0):,}")
        print(f"   Database Size: {perf_info.get('database_size_mb', 0):.2f} MB")
        print(f"   Indexes: {perf_info.get('indexes', 0)}")
        print()
        
        print(f"⚡ Query Performance:")
        print(f"   Pagination Query: {perf_info.get('pagination_query_ms', 0):.2f} ms")
        print(f"   Filtered Query: {perf_info.get('filtered_query_ms', 0):.2f} ms")
        print()
        
        # Test cursor-based pagination
        print("🔄 Testing Cursor-Based Pagination:")
        
        start_time = time.time()
        trades, total_count, total_pages, cursor_id, cursor_time = db.get_recent_trades(
            page_size=50,
            page=1,
            sort_by='entry_time',
            sort_order='DESC'
        )
        first_page_time = (time.time() - start_time) * 1000
        print(f"   First Page (50 trades): {first_page_time:.2f} ms")
        
        if cursor_id and cursor_time:
            start_time = time.time()
            trades_page2, _, _, _, _ = db.get_recent_trades(
                page_size=50,
                page=2,
                sort_by='entry_time',
                sort_order='DESC',
                cursor_id=cursor_id,
                cursor_time=cursor_time
            )
            second_page_time = (time.time() - start_time) * 1000
            print(f"   Second Page (cursor): {second_page_time:.2f} ms")
        
        print()
        
        # Test query explanation for optimization verification
        print("🔍 Query Plan Analysis:")
        explain_results = db.explain_query("""
            SELECT * FROM trades 
            WHERE dollars_gain_loss > 0 
            ORDER BY entry_time DESC 
            LIMIT 50
        """)
        
        for i, step in enumerate(explain_results):
            detail = step.get('detail', 'N/A')
            if 'INDEX' in detail.upper():
                print(f"   ✅ Step {i}: {detail}")
            else:
                print(f"   ⚠️  Step {i}: {detail}")
        
        print()
        
        # Performance recommendations
        print("💡 Performance Recommendations:")
        
        if perf_info.get('total_trades', 0) == 0:
            print("   ⚠️  No trades found - import some data to test performance")
        elif perf_info.get('pagination_query_ms', 0) > 100:
            print("   ⚠️  Pagination queries are slow - check indexes")
        else:
            print("   ✅ Query performance looks good")
            
        if perf_info.get('database_size_mb', 0) > 100:
            print("   💾 Large database - consider periodic VACUUM")
        
        if perf_info.get('indexes', 0) < 5:
            print("   ⚠️  Few indexes detected - performance may be suboptimal")
        else:
            print("   ✅ Good index coverage detected")

def test_index_usage():
    """Test if indexes are being used effectively."""
    print("\n🔍 Index Usage Analysis")
    print("=" * 50)
    
    with FuturesDB() as db:
        # Check index list
        db.cursor.execute("PRAGMA index_list(trades)")
        indexes = db.cursor.fetchall()
        
        print(f"📝 Available Indexes ({len(indexes)}):")
        for idx in indexes:
            index_dict = dict(idx)
            print(f"   - {index_dict['name']}")
        
        print()
        
        # Test specific queries that should use indexes
        test_queries = [
            ("Account Filter", "SELECT * FROM trades WHERE account = ? LIMIT 10", ["Account1"]),
            ("Date Range", "SELECT * FROM trades WHERE entry_time > ? LIMIT 10", ["2024-01-01"]),
            ("P&L Filter", "SELECT * FROM trades WHERE dollars_gain_loss > ? LIMIT 10", [0]),
            ("Combined Filter", "SELECT * FROM trades WHERE account = ? AND dollars_gain_loss > ? LIMIT 10", ["Account1", 0])
        ]
        
        for query_name, query, params in test_queries:
            print(f"🔍 {query_name}:")
            explain_results = db.explain_query(query, params)
            
            index_used = False
            for step in explain_results:
                detail = step.get('detail', '')
                if 'INDEX' in detail.upper():
                    index_used = True
                    print(f"   ✅ Using index: {detail}")
                    break
            
            if not index_used:
                print(f"   ⚠️  No index detected - may use table scan")
            print()

if __name__ == "__main__":
    test_database_performance()
    test_index_usage()
    
    print("🎯 Performance testing complete!")
    print("\nNext steps:")
    print("1. Import some trade data if none exists")
    print("2. Run this script again to see performance improvements")
    print("3. Monitor query times as data grows")
    print("4. Consider running VACUUM periodically for large databases")