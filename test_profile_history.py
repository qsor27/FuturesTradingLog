#!/usr/bin/env python3

"""
Test script for Settings Version History feature implementation.
This script tests the profile_history table and related CRUD operations.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from TradingLog_db import FuturesDB

def test_profile_history_schema():
    """Test the database schema creation and initialization."""
    print("=== Testing Profile History Schema ===")
    
    # Use a test database
    test_db_path = "/tmp/test_profile_history.db"
    
    # Remove existing test database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    try:
        with FuturesDB(test_db_path) as db:
            # Check if profile_history table exists
            db.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='profile_history'
            """)
            
            table_exists = db.cursor.fetchone() is not None
            print(f"✓ profile_history table exists: {table_exists}")
            
            # Check table structure
            if table_exists:
                db.cursor.execute("PRAGMA table_info(profile_history)")
                columns = {row[1]: row[2] for row in db.cursor.fetchall()}
                print(f"✓ Table columns: {list(columns.keys())}")
                
                expected_columns = {
                    'id': 'INTEGER',
                    'user_profile_id': 'INTEGER',
                    'version': 'INTEGER',
                    'settings_snapshot': 'TEXT',
                    'change_reason': 'TEXT',
                    'archived_at': 'TIMESTAMP'
                }
                
                for col, dtype in expected_columns.items():
                    if col in columns:
                        print(f"✓ Column {col} exists with type {columns[col]}")
                    else:
                        print(f"✗ Column {col} missing")
            
            # Check if user_profiles table has version column
            db.cursor.execute("PRAGMA table_info(user_profiles)")
            columns = {row[1]: row[2] for row in db.cursor.fetchall()}
            if 'version' in columns:
                print("✓ user_profiles table has version column")
            else:
                print("✗ user_profiles table missing version column")
            
            # Check indexes
            db.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_profile_history_profile_id_version_desc'
            """)
            
            index_exists = db.cursor.fetchone() is not None
            print(f"✓ Profile history index exists: {index_exists}")
            
    except Exception as e:
        print(f"✗ Schema test failed: {e}")
        return False
    
    print("✓ Schema tests completed successfully\n")
    return True

def test_profile_history_crud():
    """Test CRUD operations for profile history."""
    print("=== Testing Profile History CRUD Operations ===")
    
    test_db_path = "/tmp/test_profile_history.db"
    
    try:
        with FuturesDB(test_db_path) as db:
            # Create a test profile first
            test_settings = {
                'chart_settings': {
                    'default_timeframe': '1h',
                    'default_data_range': '1week',
                    'volume_visibility': True
                },
                'instrument_multipliers': {
                    'NQ': 20,
                    'ES': 50
                }
            }
            
            profile_id = db.create_user_profile(
                profile_name="Test Profile",
                settings_snapshot=test_settings,
                description="Test profile for history testing"
            )
            
            if not profile_id:
                print("✗ Failed to create test profile")
                return False
            
            print(f"✓ Created test profile with ID: {profile_id}")
            
            # Test create_profile_version
            history_record = db.create_profile_version(
                profile_id=profile_id,
                version=1,
                settings_snapshot=json.dumps(test_settings),
                change_reason="Initial version"
            )
            
            if history_record:
                print(f"✓ Created profile history record: {history_record['id']}")
            else:
                print("✗ Failed to create profile history record")
                return False
            
            # Test get_profile_history
            history_list = db.get_profile_history(profile_id)
            if history_list:
                print(f"✓ Retrieved {len(history_list)} history records")
                print(f"  First record: version {history_list[0]['version']}, reason: {history_list[0]['change_reason']}")
            else:
                print("✗ Failed to retrieve profile history")
                return False
            
            # Test get_specific_version
            specific_version = db.get_specific_version(history_record['id'])
            if specific_version:
                print(f"✓ Retrieved specific version: {specific_version['version']}")
            else:
                print("✗ Failed to retrieve specific version")
                return False
            
            # Test archive_current_version
            # First, update the profile to create a new version
            updated_settings = test_settings.copy()
            updated_settings['chart_settings']['default_timeframe'] = '5m'
            
            success = db.update_user_profile(
                profile_id=profile_id,
                settings_snapshot=updated_settings,
                version=2
            )
            
            if success:
                print("✓ Updated profile to version 2")
            else:
                print("✗ Failed to update profile")
                return False
            
            # Archive the current version
            success = db.archive_current_version(profile_id, "Updated timeframe to 5m")
            if success:
                print("✓ Archived current version")
            else:
                print("✗ Failed to archive current version")
                return False
            
            # Check that we now have 2 history records
            history_list = db.get_profile_history(profile_id)
            if len(history_list) == 2:
                print(f"✓ Now have {len(history_list)} history records")
            else:
                print(f"✗ Expected 2 history records, got {len(history_list)}")
                return False
            
            # Test revert_to_version
            # Get the first history record to revert to
            first_history = history_list[1]  # Oldest first due to DESC order
            success = db.revert_to_version(
                profile_id=profile_id,
                history_id=first_history['id'],
                change_reason="Reverting to initial timeframe"
            )
            
            if success:
                print("✓ Successfully reverted to previous version")
            else:
                print("✗ Failed to revert to previous version")
                return False
            
            # Verify the revert worked
            current_profile = db.get_user_profile(profile_id)
            if current_profile:
                current_timeframe = current_profile['settings_snapshot']['chart_settings']['default_timeframe']
                if current_timeframe == '1h':
                    print(f"✓ Revert successful: timeframe is back to {current_timeframe}")
                else:
                    print(f"✗ Revert failed: timeframe is {current_timeframe}, expected 1h")
                    return False
            else:
                print("✗ Failed to retrieve current profile after revert")
                return False
            
            # Test delete_old_versions
            # Create a few more versions first
            for i in range(3, 8):
                db.archive_current_version(profile_id, f"Version {i}")
            
            # Check total history count
            history_list = db.get_profile_history(profile_id)
            initial_count = len(history_list)
            print(f"✓ Created {initial_count} total history records")
            
            # Delete old versions, keeping only the latest 3
            deleted_count = db.delete_old_versions(profile_id, keep_latest=3)
            print(f"✓ Deleted {deleted_count} old versions")
            
            # Verify deletion
            history_list = db.get_profile_history(profile_id)
            if len(history_list) == 3:
                print(f"✓ Now have {len(history_list)} history records as expected")
            else:
                print(f"✗ Expected 3 history records, got {len(history_list)}")
                return False
            
    except Exception as e:
        print(f"✗ CRUD test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("✓ CRUD tests completed successfully\n")
    return True

def test_foreign_key_constraints():
    """Test foreign key constraints work correctly."""
    print("=== Testing Foreign Key Constraints ===")
    
    test_db_path = "/tmp/test_profile_history.db"
    
    try:
        with FuturesDB(test_db_path) as db:
            # Enable foreign key constraints
            db.cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create a test profile
            test_settings = {'test': 'data'}
            profile_id = db.create_user_profile(
                profile_name="FK Test Profile",
                settings_snapshot=test_settings,
                description="Profile for FK testing"
            )
            
            if not profile_id:
                print("✗ Failed to create FK test profile")
                return False
            
            # Create a history record
            history_record = db.create_profile_version(
                profile_id=profile_id,
                version=1,
                settings_snapshot=json.dumps(test_settings),
                change_reason="FK test"
            )
            
            if not history_record:
                print("✗ Failed to create history record for FK test")
                return False
            
            # Verify history record exists
            history_list = db.get_profile_history(profile_id)
            if len(history_list) == 0:
                print("✗ History record not found before profile deletion")
                return False
            
            print(f"✓ Created profile {profile_id} with history record")
            
            # Delete the profile (should cascade delete history)
            success = db.delete_user_profile(profile_id)
            if success:
                print("✓ Successfully deleted profile")
            else:
                print("✗ Failed to delete profile")
                return False
            
            # Verify history record was automatically deleted
            history_list = db.get_profile_history(profile_id)
            if len(history_list) == 0:
                print("✓ History records automatically deleted via CASCADE")
            else:
                print(f"✗ Expected 0 history records, got {len(history_list)}")
                return False
            
    except Exception as e:
        print(f"✗ Foreign key test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("✓ Foreign key tests completed successfully\n")
    return True

def test_performance():
    """Test performance of profile history operations."""
    print("=== Testing Performance ===")
    
    test_db_path = "/tmp/test_profile_history.db"
    
    try:
        with FuturesDB(test_db_path) as db:
            # Create a test profile
            test_settings = {
                'chart_settings': {'timeframe': '1h'},
                'data': 'x' * 1000  # Some bulk data
            }
            
            profile_id = db.create_user_profile(
                profile_name="Performance Test Profile",
                settings_snapshot=test_settings,
                description="Profile for performance testing"
            )
            
            if not profile_id:
                print("✗ Failed to create performance test profile")
                return False
            
            # Create multiple history records
            import time
            start_time = time.time()
            
            for i in range(100):
                db.create_profile_version(
                    profile_id=profile_id,
                    version=i + 1,
                    settings_snapshot=json.dumps(test_settings),
                    change_reason=f"Performance test version {i + 1}"
                )
            
            create_time = time.time() - start_time
            print(f"✓ Created 100 history records in {create_time:.3f}s")
            
            # Test retrieval performance
            start_time = time.time()
            history_list = db.get_profile_history(profile_id, limit=50)
            retrieve_time = time.time() - start_time
            
            if len(history_list) == 50:
                print(f"✓ Retrieved 50 history records in {retrieve_time:.3f}s")
            else:
                print(f"✗ Expected 50 records, got {len(history_list)}")
                return False
            
            # Test cleanup performance
            start_time = time.time()
            deleted_count = db.delete_old_versions(profile_id, keep_latest=10)
            cleanup_time = time.time() - start_time
            
            print(f"✓ Deleted {deleted_count} old versions in {cleanup_time:.3f}s")
            
    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("✓ Performance tests completed successfully\n")
    return True

def main():
    """Run all tests."""
    print("Starting Settings Version History Implementation Tests...\n")
    
    tests = [
        test_profile_history_schema,
        test_profile_history_crud,
        test_foreign_key_constraints,
        test_performance
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
        print("🎉 All tests passed! Settings Version History implementation is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())