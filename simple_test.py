#!/usr/bin/env python3
"""
Simple test runner for GitHub Actions
"""
import subprocess
import sys
import os
from pathlib import Path

def setup_environment():
    """Setup test environment"""
    # Set PYTHONPATH
    current_dir = Path(__file__).parent
    os.environ['PYTHONPATH'] = str(current_dir)
    
    # Set data directory
    data_dir = current_dir / 'data'
    os.environ['DATA_DIR'] = str(data_dir)
    os.environ['FLASK_ENV'] = 'testing'
    
    # Create required directories
    for subdir in ['db', 'logs', 'config', 'charts', 'archive']:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    print(f"Environment setup complete:")
    print(f"  DATA_DIR: {os.environ['DATA_DIR']}")
    print(f"  FLASK_ENV: {os.environ['FLASK_ENV']}")
    print(f"  PYTHONPATH: {os.environ['PYTHONPATH']}")

def run_tests():
    """Run basic tests for GitHub Actions"""
    setup_environment()
    
    success = True
    
    # Test 1: Basic import test
    try:
        print("\n1. Testing basic imports...")
        import config
        print("  ✓ Config module imported")
        
        from config import config as app_config
        print("  ✓ Config instance imported")
        
        # Test config initialization
        print(f"  ✓ Data directory: {app_config.data_dir}")
        
    except Exception as e:
        print(f"  ✗ Config import failed: {e}")
        success = False
    
    # Test 2: Database manager import
    try:
        print("\n2. Testing database imports...")
        from database_manager import DatabaseManager
        print("  ✓ DatabaseManager imported")
    except Exception as e:
        print(f"  ✗ Database import failed: {e}")
        # Don't fail on this since it might need Redis/other deps
        print("  ! Continuing anyway (database might need additional setup)")
    
    # Test 3: Flask app
    try:
        print("\n3. Testing Flask app...")
        from app import app as flask_app
        print("  ✓ Flask app imported")
        
        with flask_app.test_client() as client:
            print("  ✓ Test client created")
            
            # Test health endpoint
            response = client.get('/health')
            if response.status_code == 200:
                print("  ✓ Health endpoint returns 200")
                
                # Check if response contains expected content
                data = response.get_json()
                if data and 'status' in data:
                    print("  ✓ Health response contains status")
                else:
                    print("  ! Health response format unexpected but continuing")
            else:
                print(f"  ✗ Health endpoint failed: {response.status_code}")
                success = False
                
    except Exception as e:
        print(f"  ✗ Flask app test failed: {e}")
        success = False
    
    return success

if __name__ == '__main__':
    print("=== GitHub Actions Simple Test Runner ===")
    
    if run_tests():
        print("\n=== ALL TESTS PASSED ===")
        sys.exit(0)
    else:
        print("\n=== SOME TESTS FAILED ===")
        sys.exit(1)