#!/usr/bin/env python3
"""
Test script for Enhanced Settings Categories API
Tests the new categorized settings endpoints
"""

import requests
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_categorized_settings_api():
    """Test the new categorized settings API endpoints"""
    base_url = "http://localhost:5000"
    
    print("Testing Enhanced Settings Categories API...")
    print("=" * 50)
    
    # Test 1: GET categorized settings
    print("\n1. Testing GET /api/v2/settings/categorized")
    try:
        response = requests.get(f"{base_url}/api/v2/settings/categorized")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ GET request successful")
            print(f"Response structure: {list(data.keys())}")
            
            if 'settings' in data:
                settings = data['settings']
                print(f"Settings categories: {list(settings.keys())}")
                
                # Check chart settings
                if 'chart' in settings:
                    chart = settings['chart']
                    print(f"Chart settings: {chart}")
                
                # Check trading settings
                if 'trading' in settings:
                    trading = settings['trading']
                    print(f"Trading settings: {trading}")
                    
                print("✓ Structure validation passed")
            else:
                print("✗ Missing 'settings' key in response")
        else:
            print(f"✗ GET request failed: {response.text}")
    except Exception as e:
        print(f"✗ GET request error: {e}")
    
    # Test 2: POST validation endpoint
    print("\n2. Testing POST /api/v2/settings/validate")
    test_settings = {
        "settings": {
            "chart": {
                "default_timeframe": "1h",
                "default_data_range": "1week",
                "volume_visibility": True
            },
            "trading": {
                "instrument_multipliers": {
                    "ES": 50,
                    "NQ": 20
                }
            }
        }
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v2/settings/validate",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Validation request successful")
            print(f"Valid: {data.get('valid', 'Unknown')}")
            
            if 'validation_results' in data:
                for category, result in data['validation_results'].items():
                    print(f"  {category}: valid={result.get('valid', False)}")
                    if result.get('errors'):
                        print(f"    Errors: {result['errors']}")
        else:
            print(f"✗ Validation request failed: {response.text}")
    except Exception as e:
        print(f"✗ Validation request error: {e}")
    
    # Test 3: PUT categorized settings (be careful with this one)
    print("\n3. Testing PUT /api/v2/settings/categorized")
    
    # First get current settings
    try:
        current_response = requests.get(f"{base_url}/api/v2/settings/categorized")
        if current_response.status_code != 200:
            print("✗ Cannot get current settings for PUT test")
            return
        
        current_data = current_response.json()
        current_settings = current_data.get('settings', {})
        
        # Make a small change to chart settings
        update_settings = {
            "settings": {
                "chart": {
                    "default_timeframe": current_settings.get('chart', {}).get('default_timeframe', '1h'),
                    "default_data_range": current_settings.get('chart', {}).get('default_data_range', '1week'),
                    "volume_visibility": not current_settings.get('chart', {}).get('volume_visibility', True)  # Toggle this
                }
            }
        }
        
        response = requests.put(
            f"{base_url}/api/v2/settings/categorized",
            json=update_settings,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ PUT request successful")
            print(f"Updated sections: {data.get('updated_sections', [])}")
            print(f"Message: {data.get('message', 'No message')}")
            
            # Restore original settings
            restore_settings = {
                "settings": {
                    "chart": {
                        "volume_visibility": current_settings.get('chart', {}).get('volume_visibility', True)
                    }
                }
            }
            
            restore_response = requests.put(
                f"{base_url}/api/v2/settings/categorized",
                json=restore_settings,
                headers={"Content-Type": "application/json"}
            )
            
            if restore_response.status_code == 200:
                print("✓ Settings restored successfully")
            else:
                print(f"⚠ Warning: Failed to restore settings: {restore_response.text}")
        else:
            print(f"✗ PUT request failed: {response.text}")
    except Exception as e:
        print(f"✗ PUT request error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_categorized_settings_api()