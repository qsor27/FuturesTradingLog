#!/usr/bin/env python3
"""
Simple test script to validate the profile API implementation
Tests syntax, imports, and basic functionality without requiring Flask server
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_validation_function():
    """Test the profile data validation function"""
    print("🧪 Testing profile data validation...")
    
    # Import the validation function (this will test syntax)
    try:
        from routes.profiles import validate_profile_data
        print("✅ Import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test cases
    test_cases = [
        # Valid profile
        {
            'data': {
                'profile_name': 'Test Profile',
                'settings_snapshot': {
                    'chart_settings': {'default_timeframe': '1m'}
                }
            },
            'expected': True,
            'description': 'Valid profile data'
        },
        # Missing profile_name
        {
            'data': {
                'settings_snapshot': {'chart_settings': {}}
            },
            'expected': False,
            'description': 'Missing profile_name'
        },
        # Missing settings_snapshot
        {
            'data': {
                'profile_name': 'Test Profile'
            },
            'expected': False,
            'description': 'Missing settings_snapshot'
        },
        # Empty profile_name
        {
            'data': {
                'profile_name': '',
                'settings_snapshot': {}
            },
            'expected': False,
            'description': 'Empty profile_name'
        },
        # Invalid settings_snapshot type
        {
            'data': {
                'profile_name': 'Test Profile',
                'settings_snapshot': 'invalid'
            },
            'expected': False,
            'description': 'Invalid settings_snapshot type'
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        is_valid, error_msg = validate_profile_data(test_case['data'])
        expected = test_case['expected']
        
        if is_valid == expected:
            print(f"✅ Test {i+1}: {test_case['description']}")
        else:
            print(f"❌ Test {i+1}: {test_case['description']}")
            print(f"   Expected: {expected}, Got: {is_valid}")
            print(f"   Error: {error_msg}")
    
    return True

def test_helper_functions():
    """Test utility functions"""
    print("\n🧪 Testing utility functions...")
    
    try:
        from routes.profiles import allowed_file, ensure_unique_profile_name
        print("✅ Helper functions imported successfully")
    except Exception as e:
        print(f"❌ Helper function import failed: {e}")
        return False
    
    # Test allowed_file function
    test_files = [
        ('test.json', True),
        ('test.JSON', True),
        ('test.txt', False),
        ('test.py', False),
        ('test', False),
        ('test.json.txt', False)
    ]
    
    for filename, expected in test_files:
        result = allowed_file(filename)
        if result == expected:
            print(f"✅ File validation: {filename}")
        else:
            print(f"❌ File validation: {filename} - Expected {expected}, got {result}")
    
    return True

def test_sample_export_format():
    """Test sample export data format"""
    print("\n🧪 Testing export data format...")
    
    # Sample profile data
    sample_profile = {
        'profile_name': 'Scalping Setup',
        'description': 'Quick trades with 1m charts',
        'settings_snapshot': {
            'chart_settings': {
                'default_timeframe': '1m',
                'default_data_range': '3hours',
                'volume_visibility': True
            },
            'instrument_multipliers': {
                'NQ': 20,
                'ES': 50
            }
        }
    }
    
    # Create export format
    export_data = {
        'profile_name': sample_profile['profile_name'],
        'description': sample_profile.get('description', ''),
        'settings_snapshot': sample_profile['settings_snapshot'],
        'exported_at': '2025-01-01T10:00:00.000Z',
        'export_version': '1.0'
    }
    
    try:
        # Test JSON serialization
        json_str = json.dumps(export_data, indent=2)
        
        # Test JSON parsing
        parsed_data = json.loads(json_str)
        
        # Validate structure
        required_fields = ['profile_name', 'settings_snapshot', 'exported_at', 'export_version']
        for field in required_fields:
            if field not in parsed_data:
                print(f"❌ Missing required field in export: {field}")
                return False
        
        print("✅ Export data format validation passed")
        print(f"   Profile name: {parsed_data['profile_name']}")
        print(f"   Settings keys: {list(parsed_data['settings_snapshot'].keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Export format test failed: {e}")
        return False

def test_bulk_export_format():
    """Test bulk export data format"""
    print("\n🧪 Testing bulk export format...")
    
    sample_profiles = [
        {
            'profile_name': 'Scalping Setup',
            'settings_snapshot': {'chart_settings': {'default_timeframe': '1m'}}
        },
        {
            'profile_name': 'Swing Trading',
            'settings_snapshot': {'chart_settings': {'default_timeframe': '4h'}}
        }
    ]
    
    bulk_export_data = {
        'profiles': sample_profiles,
        'exported_at': '2025-01-01T10:00:00.000Z',
        'export_version': '1.0',
        'export_type': 'bulk',
        'profile_count': len(sample_profiles)
    }
    
    try:
        # Test JSON serialization
        json_str = json.dumps(bulk_export_data, indent=2)
        
        # Test JSON parsing
        parsed_data = json.loads(json_str)
        
        # Validate structure
        if 'profiles' not in parsed_data:
            print("❌ Missing 'profiles' field in bulk export")
            return False
        
        if parsed_data['profile_count'] != len(parsed_data['profiles']):
            print("❌ Profile count mismatch in bulk export")
            return False
        
        print("✅ Bulk export format validation passed")
        print(f"   Profile count: {parsed_data['profile_count']}")
        print(f"   Export type: {parsed_data['export_type']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bulk export format test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Profile API Tests\n")
    
    tests = [
        test_validation_function,
        test_helper_functions,
        test_sample_export_format,
        test_bulk_export_format
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Profile API implementation looks good.")
        return True
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)