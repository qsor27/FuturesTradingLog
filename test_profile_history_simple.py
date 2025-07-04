#!/usr/bin/env python3

"""
Simple test script for Settings Version History feature implementation.
This script tests the profile_history table schema directly with SQLite.
"""

import sqlite3
import json
import os
import tempfile

def test_schema_creation():
    """Test the database schema creation."""
    print("=== Testing Profile History Schema Creation ===")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Apply SQLite optimizations
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = normal")
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create user_profiles table first
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                profile_name TEXT NOT NULL,
                description TEXT,
                settings_snapshot TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER NOT NULL DEFAULT 1,
                
                UNIQUE(user_id, profile_name)
            )
        """)
        
        # Create profile_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                settings_snapshot TEXT NOT NULL,
                change_reason TEXT,
                archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles (id) ON DELETE CASCADE
            )
        """)
        
        # Create index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_profile_history_profile_id_version_desc
            ON profile_history (user_profile_id, version DESC)
        """)
        
        conn.commit()
        
        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'user_profiles' in tables and 'profile_history' in tables:
            print("✓ Both tables created successfully")
        else:
            print(f"✗ Tables missing. Found: {tables}")
            return False
        
        # Check profile_history table structure
        cursor.execute("PRAGMA table_info(profile_history)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'user_profile_id': 'INTEGER',
            'version': 'INTEGER',
            'settings_snapshot': 'TEXT',
            'change_reason': 'TEXT',
            'archived_at': 'TIMESTAMP'
        }
        
        for col, expected_type in expected_columns.items():
            if col in columns:
                print(f"✓ Column {col} exists")
            else:
                print(f"✗ Column {col} missing")
                return False
        
        # Check user_profiles has version column
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        if 'version' in columns:
            print("✓ user_profiles table has version column")
        else:
            print("✗ user_profiles table missing version column")
            return False
        
        # Check index exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        if 'idx_profile_history_profile_id_version_desc' in indexes:
            print("✓ Profile history index created")
        else:
            print("✗ Profile history index missing")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Schema test failed: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    print("✓ Schema tests completed successfully\n")
    return True

def test_basic_operations():
    """Test basic CRUD operations."""
    print("=== Testing Basic CRUD Operations ===")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Apply SQLite optimizations
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = normal")
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
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
                version INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, profile_name)
            )
        """)
        
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
        
        # Test data
        test_settings = {
            'chart_settings': {
                'default_timeframe': '1h',
                'default_data_range': '1week'
            },
            'instrument_multipliers': {
                'NQ': 20,
                'ES': 50
            }
        }
        
        # Create a test profile
        cursor.execute("""
            INSERT INTO user_profiles (profile_name, settings_snapshot, description)
            VALUES (?, ?, ?)
        """, ("Test Profile", json.dumps(test_settings), "Test profile"))
        
        profile_id = cursor.lastrowid
        conn.commit()
        
        if profile_id:
            print(f"✓ Created test profile with ID: {profile_id}")
        else:
            print("✗ Failed to create test profile")
            return False
        
        # Create a history record
        cursor.execute("""
            INSERT INTO profile_history (user_profile_id, version, settings_snapshot, change_reason)
            VALUES (?, ?, ?, ?)
        """, (profile_id, 1, json.dumps(test_settings), "Initial version"))
        
        history_id = cursor.lastrowid
        conn.commit()
        
        if history_id:
            print(f"✓ Created history record with ID: {history_id}")
        else:
            print("✗ Failed to create history record")
            return False
        
        # Retrieve history
        cursor.execute("""
            SELECT id, user_profile_id, version, settings_snapshot, change_reason, archived_at
            FROM profile_history
            WHERE user_profile_id = ?
            ORDER BY version DESC
        """, (profile_id,))
        
        history_records = cursor.fetchall()
        
        if len(history_records) == 1:
            print(f"✓ Retrieved {len(history_records)} history record")
            record = history_records[0]
            settings = json.loads(record[3])
            if settings == test_settings:
                print("✓ Settings data matches original")
            else:
                print("✗ Settings data corrupted")
                return False
        else:
            print(f"✗ Expected 1 history record, got {len(history_records)}")
            return False
        
        # Test foreign key constraint
        cursor.execute("DELETE FROM user_profiles WHERE id = ?", (profile_id,))
        conn.commit()
        
        # Check that history record was automatically deleted
        cursor.execute("SELECT COUNT(*) FROM profile_history WHERE user_profile_id = ?", (profile_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("✓ Foreign key CASCADE delete working correctly")
        else:
            print(f"✗ Foreign key CASCADE failed, {count} records remain")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"✗ CRUD test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    print("✓ CRUD tests completed successfully\n")
    return True

def test_index_performance():
    """Test index performance."""
    print("=== Testing Index Performance ===")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Apply SQLite optimizations
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = normal")
        
        # Create tables
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
                version INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, profile_name)
            )
        """)
        
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
        
        # Create test data
        test_settings = {'data': 'test'}
        
        # Create a test profile
        cursor.execute("""
            INSERT INTO user_profiles (profile_name, settings_snapshot, description)
            VALUES (?, ?, ?)
        """, ("Performance Test Profile", json.dumps(test_settings), "Performance test"))
        
        profile_id = cursor.lastrowid
        conn.commit()
        
        # Create many history records
        import time
        start_time = time.time()
        
        for i in range(1000):
            cursor.execute("""
                INSERT INTO profile_history (user_profile_id, version, settings_snapshot, change_reason)
                VALUES (?, ?, ?, ?)
            """, (profile_id, i + 1, json.dumps(test_settings), f"Version {i + 1}"))
        
        conn.commit()
        create_time = time.time() - start_time
        
        print(f"✓ Created 1000 history records in {create_time:.3f}s")
        
        # Test query performance with index
        start_time = time.time()
        cursor.execute("""
            SELECT id, version, change_reason
            FROM profile_history
            WHERE user_profile_id = ?
            ORDER BY version DESC
            LIMIT 50
        """, (profile_id,))
        
        results = cursor.fetchall()
        query_time = time.time() - start_time
        
        if len(results) == 50:
            print(f"✓ Retrieved 50 records in {query_time:.3f}s")
        else:
            print(f"✗ Expected 50 records, got {len(results)}")
            return False
        
        # Check that results are properly sorted
        versions = [row[1] for row in results]
        if versions == sorted(versions, reverse=True):
            print("✓ Results properly sorted by version DESC")
        else:
            print("✗ Results not properly sorted")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    print("✓ Performance tests completed successfully\n")
    return True

def main():
    """Run all tests."""
    print("Starting Settings Version History Schema Tests...\n")
    
    tests = [
        test_schema_creation,
        test_basic_operations,
        test_index_performance
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
        print("🎉 All tests passed! Profile history schema is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())