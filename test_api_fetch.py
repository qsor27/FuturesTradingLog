#!/usr/bin/env python3
"""Test script to see what happens when the API tries to fetch data"""

import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

def test_available_timeframes_api():
    """Test the available timeframes API directly"""
    print("=== Testing Available Timeframes API ===")
    
    try:
        # Test with MNQ
        url = "http://localhost:5000/api/available-timeframes/MNQ"
        print(f"Calling: {url}")
        
        response = requests.get(url, timeout=30)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {json.dumps(data, indent=2)}")
        else:
            print(f"Error response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Cannot connect to localhost:5000 - Flask app not running")
    except Exception as e:
        print(f"API test error: {e}")

def test_chart_data_api():
    """Test the chart data API to see what happens when no data exists"""
    print("\n=== Testing Chart Data API ===")
    
    try:
        # Test with MNQ
        url = "http://localhost:5000/api/chart-data/MNQ?timeframe=1h&days=1"
        print(f"Calling: {url}")
        
        response = requests.get(url, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Chart data response: {json.dumps(data, indent=2)}")
        else:
            print(f"Error response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Cannot connect to localhost:5000 - Flask app not running")
    except Exception as e:
        print(f"API test error: {e}")

if __name__ == "__main__":
    test_available_timeframes_api()
    test_chart_data_api()