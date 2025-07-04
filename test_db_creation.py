#!/usr/bin/env python3

"""
Test database creation with Settings Version History implementation.
This tests the actual TradingLog_db.py with our new schema.
"""

import os
import sys
import tempfile
import sqlite3

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_with_mock_dependencies():
    """Test with minimal dependencies mocked."""
    print("=== Testing Database Creation with Mocked Dependencies ===")
    
    # Create a test database path
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    try:
        # Mock the config module temporarily
        import config
        original_db_path = getattr(config.config, 'db_path', None)
        config.config.db_path = test_db_path
        
        # Mock pandas to avoid import error
        sys.modules['pandas'] = type('MockPandas', (), {
            'DataFrame': lambda *args, **kwargs: None,
            'read_sql_query': lambda *args, **kwargs: None
        })()
        
        # Now import and test TradingLog_db
        from TradingLog_db import FuturesDB
        
        # Test database creation
        with FuturesDB(test_db_path) as db:
            print("✓ Database connection established")
            
            # Check if all expected tables exist
            tables = ['trades', 'ohlc_data', 'user_profiles', 'profile_history']
            
            for table in tables:
                db.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if db.cursor.fetchone():
                    print(f"✓ {table} table exists")
                else:
                    print(f"✗ {table} table missing")
                    return False
            
            # Check user_profiles has version column
            db.cursor.execute("PRAGMA table_info(user_profiles)")
            columns = {row[1]: row[2] for row in db.cursor.fetchall()}
            
            if 'version' in columns:
                print("✓ user_profiles table has version column")
            else:
                print("✗ user_profiles table missing version column")
                return False
            
            # Check profile_history table structure
            db.cursor.execute("PRAGMA table_info(profile_history)")
            columns = {row[1]: row[2] for row in db.cursor.fetchall()}
            
            expected_columns = ['id', 'user_profile_id', 'version', 'settings_snapshot', 'change_reason', 'archived_at']
            
            for col in expected_columns:
                if col in columns:
                    print(f"✓ profile_history has {col} column")
                else:
                    print(f"✗ profile_history missing {col} column")
                    return False
            
            # Check foreign key constraint
            db.cursor.execute("PRAGMA foreign_key_list(profile_history)")
            fk_info = db.cursor.fetchall()
            
            if fk_info:
                print("✓ profile_history has foreign key constraint")
                fk = fk_info[0]
                if fk[2] == 'user_profiles' and fk[3] == 'user_profile_id' and fk[4] == 'id':
                    print("✓ Foreign key points to correct table and columns")
                else:
                    print(f"✗ Foreign key misconfigured: {fk}")
                    return False
            else:
                print("✗ profile_history missing foreign key constraint")
                return False
            
            # Check index exists
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_profile_history_profile_id_version_desc'")
            if db.cursor.fetchone():
                print("✓ profile_history index exists")
            else:
                print("✗ profile_history index missing")
                return False
            
            # Test CRUD methods exist
            methods = [
                'create_profile_version',
                'get_profile_history', 
                'get_specific_version',
                'delete_old_versions',
                'archive_current_version',
                'revert_to_version'
            ]
            
            for method in methods:
                if hasattr(db, method):
                    print(f"✓ {method} method exists")
                else:
                    print(f"✗ {method} method missing")
                    return False
        
        # Restore original config
        if original_db_path:
            config.config.db_path = original_db_path
        
    except Exception as e:
        print(f"✗ Database creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    
    print("✓ Database creation tests completed successfully\n")
    return True

def test_methods_with_simple_data():
    """Test the CRUD methods with simple test data."""
    print("=== Testing CRUD Methods with Simple Data ===")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    try:
        # Set up minimal environment
        import config
        original_db_path = getattr(config.config, 'db_path', None)
        config.config.db_path = test_db_path
        
        # Mock pandas
        sys.modules['pandas'] = type('MockPandas', (), {
            'DataFrame': lambda *args, **kwargs: None,
            'read_sql_query': lambda *args, **kwargs: None
        })()
        
        from TradingLog_db import FuturesDB
        
        with FuturesDB(test_db_path) as db:
            # Create a test profile
            test_settings = {
                'chart_settings': {
                    'default_timeframe': '1h',
                    'default_data_range': '1week'
                }
            }
            
            profile_id = db.create_user_profile(
                profile_name="CRUD Test Profile",
                settings_snapshot=test_settings,
                description="Profile for CRUD testing"
            )
            
            if profile_id:
                print(f"✓ Created test profile with ID: {profile_id}")
            else:
                print("✗ Failed to create test profile")
                return False
            
            # Test create_profile_version
            import json
            history_record = db.create_profile_version(
                profile_id=profile_id,
                version=1,
                settings_snapshot=json.dumps(test_settings),
                change_reason="CRUD test"
            )
            
            if history_record:
                print(f"✓ Created profile version: {history_record['id']}")
            else:
                print("✗ Failed to create profile version")
                return False
            
            # Test get_profile_history
            history_list = db.get_profile_history(profile_id)
            if history_list and len(history_list) == 1:
                print(f"✓ Retrieved {len(history_list)} history record")
            else:
                print(f"✗ Expected 1 history record, got {len(history_list) if history_list else 0}")
                return False
            
            # Test get_specific_version
            specific_version = db.get_specific_version(history_record['id'])
            if specific_version:
                print(f"✓ Retrieved specific version: {specific_version['version']}")
            else:
                print("✗ Failed to retrieve specific version")
                return False
            
            # Test archive_current_version
            success = db.archive_current_version(profile_id, "Test archive")
            if success:
                print("✓ Archived current version")
            else:
                print("✗ Failed to archive current version")
                return False
            
            # Test delete_old_versions
            deleted_count = db.delete_old_versions(profile_id, keep_latest=1)
            print(f"✓ Deleted {deleted_count} old versions")
            
            # Verify we still have the latest version
            history_list = db.get_profile_history(profile_id)
            if history_list and len(history_list) == 1:
                print(f"✓ Still have {len(history_list)} history record after cleanup")
            else:
                print(f"✗ Expected 1 history record after cleanup, got {len(history_list) if history_list else 0}")
                return False
        
        # Restore original config
        if original_db_path:
            config.config.db_path = original_db_path
        
    except Exception as e:
        print(f"✗ CRUD methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    
    print("✓ CRUD methods tests completed successfully\n")
    return True

def main():
    """Run all tests."""
    print("Starting TradingLog_db Settings Version History Tests...\n")
    
    tests = [
        test_with_mock_dependencies,
        test_methods_with_simple_data
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("🎉 All TradingLog_db tests passed! Settings Version History implementation is complete.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())