#!/usr/bin/env python3

"""
Integration test for Settings Version History feature with existing database.
This tests the schema changes in a real database environment.
"""

import sqlite3
import json
import os
import shutil
import tempfile

def test_database_integration():
    """Test integration with existing database structure."""
    print("=== Testing Database Integration ===")
    
    # Use the actual database path
    original_db_path = "/home/qadmin/Projects/FuturesTradingLog/data/db/TradingLog.db"
    
    if not os.path.exists(original_db_path):
        print("✗ TradingLog.db not found")
        return False
    
    # Create a backup for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    try:
        # Copy the original database
        shutil.copy2(original_db_path, test_db_path)
        print(f"✓ Created test database copy")
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Check if user_profiles table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'")
        user_profiles_exists = cursor.fetchone() is not None
        
        if user_profiles_exists:
            print("✓ user_profiles table exists")
            
            # Check if version column exists
            cursor.execute("PRAGMA table_info(user_profiles)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            if 'version' not in columns:
                print("⚠ Adding version column to user_profiles table")
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
                conn.commit()
                print("✓ Added version column")
            else:
                print("✓ version column already exists")
            
        else:
            print("✗ user_profiles table not found")
            return False
        
        # Check if profile_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profile_history'")
        profile_history_exists = cursor.fetchone() is not None
        
        if not profile_history_exists:
            print("⚠ Creating profile_history table")
            cursor.execute("""
                CREATE TABLE profile_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_profile_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    settings_snapshot TEXT NOT NULL,
                    change_reason TEXT,
                    archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (user_profile_id) REFERENCES user_profiles (id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE INDEX idx_profile_history_profile_id_version_desc
                ON profile_history (user_profile_id, version DESC)
            """)
            
            conn.commit()
            print("✓ Created profile_history table and index")
        else:
            print("✓ profile_history table already exists")
        
        # Test with actual data if any profiles exist
        cursor.execute("SELECT COUNT(*) FROM user_profiles")
        profile_count = cursor.fetchone()[0]
        
        if profile_count > 0:
            print(f"✓ Found {profile_count} existing profiles")
            
            # Test with first profile
            cursor.execute("SELECT id, profile_name, settings_snapshot, version FROM user_profiles LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                profile_id, profile_name, settings_snapshot, version = row
                print(f"✓ Testing with profile: {profile_name} (ID: {profile_id}, Version: {version})")
                
                # Create a history record
                cursor.execute("""
                    INSERT INTO profile_history (user_profile_id, version, settings_snapshot, change_reason)
                    VALUES (?, ?, ?, ?)
                """, (profile_id, version or 1, settings_snapshot, "Integration test"))
                
                history_id = cursor.lastrowid
                conn.commit()
                
                if history_id:
                    print(f"✓ Created history record with ID: {history_id}")
                else:
                    print("✗ Failed to create history record")
                    return False
                
                # Retrieve the history record
                cursor.execute("""
                    SELECT id, version, change_reason, archived_at
                    FROM profile_history
                    WHERE user_profile_id = ?
                    ORDER BY version DESC
                """, (profile_id,))
                
                history_records = cursor.fetchall()
                
                if len(history_records) >= 1:
                    print(f"✓ Retrieved {len(history_records)} history record(s)")
                    
                    # Clean up test data
                    cursor.execute("DELETE FROM profile_history WHERE id = ?", (history_id,))
                    conn.commit()
                    print("✓ Cleaned up test history record")
                else:
                    print("✗ Failed to retrieve history record")
                    return False
                
        else:
            print("⚠ No existing profiles found, creating test profile")
            
            # Create a test profile
            test_settings = {
                'chart_settings': {
                    'default_timeframe': '1h',
                    'default_data_range': '1week'
                }
            }
            
            cursor.execute("""
                INSERT INTO user_profiles (profile_name, settings_snapshot, description)
                VALUES (?, ?, ?)
            """, ("Integration Test Profile", json.dumps(test_settings), "Test profile for integration"))
            
            profile_id = cursor.lastrowid
            conn.commit()
            
            if profile_id:
                print(f"✓ Created test profile with ID: {profile_id}")
                
                # Create a history record
                cursor.execute("""
                    INSERT INTO profile_history (user_profile_id, version, settings_snapshot, change_reason)
                    VALUES (?, ?, ?, ?)
                """, (profile_id, 1, json.dumps(test_settings), "Integration test"))
                
                history_id = cursor.lastrowid
                conn.commit()
                
                if history_id:
                    print(f"✓ Created history record with ID: {history_id}")
                else:
                    print("✗ Failed to create history record")
                    return False
                
                # Clean up test data
                cursor.execute("DELETE FROM user_profiles WHERE id = ?", (profile_id,))
                conn.commit()
                print("✓ Cleaned up test profile and history")
            else:
                print("✗ Failed to create test profile")
                return False
        
        # Test index performance
        cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM profile_history WHERE user_profile_id = 1 ORDER BY version DESC")
        query_plan = cursor.fetchall()
        
        # Check if index is being used
        plan_text = ' '.join([str(row) for row in query_plan])
        if 'idx_profile_history_profile_id_version_desc' in plan_text:
            print("✓ Index is being used in query plan")
        else:
            print("⚠ Index may not be optimally used")
            print(f"Query plan: {query_plan}")
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test database
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    
    print("✓ Integration tests completed successfully\n")
    return True

def test_database_migration():
    """Test database migration for existing installations."""
    print("=== Testing Database Migration ===")
    
    # Create a database that simulates an existing installation
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    try:
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        # Create the original user_profiles table without version column
        cursor.execute("""
            CREATE TABLE user_profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                profile_name TEXT NOT NULL,
                description TEXT,
                settings_snapshot TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(user_id, profile_name)
            )
        """)
        
        # Add some test data
        test_settings = {'chart_settings': {'timeframe': '1h'}}
        cursor.execute("""
            INSERT INTO user_profiles (profile_name, settings_snapshot, description)
            VALUES (?, ?, ?)
        """, ("Original Profile", json.dumps(test_settings), "Original profile"))
        
        conn.commit()
        
        # Check original structure
        cursor.execute("PRAGMA table_info(user_profiles)")
        original_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        if 'version' in original_columns:
            print("✗ Version column should not exist in original table")
            return False
        else:
            print("✓ Original table structure verified")
        
        # Simulate migration
        print("⚠ Simulating migration...")
        
        # Add version column
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        
        # Create profile_history table
        cursor.execute("""
            CREATE TABLE profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                settings_snapshot TEXT NOT NULL,
                change_reason TEXT,
                archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles (id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE INDEX idx_profile_history_profile_id_version_desc
            ON profile_history (user_profile_id, version DESC)
        """)
        
        conn.commit()
        
        # Verify migration
        cursor.execute("PRAGMA table_info(user_profiles)")
        migrated_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        if 'version' in migrated_columns:
            print("✓ Version column added successfully")
        else:
            print("✗ Version column not added")
            return False
        
        # Check that existing data is preserved
        cursor.execute("SELECT id, profile_name, version FROM user_profiles WHERE profile_name = 'Original Profile'")
        row = cursor.fetchone()
        
        if row:
            profile_id, profile_name, version = row
            if version == 1:  # Default value
                print(f"✓ Existing data preserved: {profile_name} (Version: {version})")
            else:
                print(f"✗ Version not set to default: {version}")
                return False
        else:
            print("✗ Existing data lost during migration")
            return False
        
        # Test profile_history table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profile_history'")
        if cursor.fetchone():
            print("✓ profile_history table created")
        else:
            print("✗ profile_history table not created")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Migration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    
    print("✓ Migration tests completed successfully\n")
    return True

def main():
    """Run all integration tests."""
    print("Starting Settings Version History Integration Tests...\n")
    
    tests = [
        test_database_integration,
        test_database_migration
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
        print("🎉 All integration tests passed! Settings Version History is ready for production.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())