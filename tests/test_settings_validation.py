#!/usr/bin/env python3
"""
Unit tests for Enhanced Settings Categories validation functions
Tests the validation logic without requiring Flask to be running
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_chart_settings_validation():
    """Test chart settings validation logic"""
    
    # Mock the validation function from settings.py
    def _validate_chart_settings(chart_settings):
        """Validate chart settings structure and values"""
        try:
            errors = []
            
            # Validate timeframe
            if 'default_timeframe' in chart_settings:
                valid_timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
                if chart_settings['default_timeframe'] not in valid_timeframes:
                    errors.append(f"Invalid timeframe. Must be one of {valid_timeframes}")
            
            # Validate data range
            if 'default_data_range' in chart_settings:
                valid_ranges = ['1day', '3days', '1week', '2weeks', '1month', '3months', '6months']
                if chart_settings['default_data_range'] not in valid_ranges:
                    errors.append(f"Invalid data range. Must be one of {valid_ranges}")
            
            # Validate volume visibility
            if 'volume_visibility' in chart_settings:
                if not isinstance(chart_settings['volume_visibility'], bool):
                    errors.append("volume_visibility must be a boolean")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
        
        except Exception as e:
            return {
                'valid': False,
                'errors': [str(e)]
            }
    
    print("Testing chart settings validation...")
    print("=" * 40)
    
    # Test 1: Valid chart settings
    valid_settings = {
        'default_timeframe': '1h',
        'default_data_range': '1week',
        'volume_visibility': True
    }
    
    result = _validate_chart_settings(valid_settings)
    print(f"Test 1 - Valid settings: {result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    # Test 2: Invalid timeframe
    invalid_timeframe = {
        'default_timeframe': '2h',  # Invalid
        'default_data_range': '1week',
        'volume_visibility': True
    }
    
    result = _validate_chart_settings(invalid_timeframe)
    print(f"Test 2 - Invalid timeframe: {not result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    # Test 3: Invalid data range
    invalid_range = {
        'default_timeframe': '1h',
        'default_data_range': '2weeks_invalid',  # Invalid
        'volume_visibility': True
    }
    
    result = _validate_chart_settings(invalid_range)
    print(f"Test 3 - Invalid data range: {not result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    # Test 4: Invalid volume visibility type
    invalid_volume = {
        'default_timeframe': '1h',
        'default_data_range': '1week',
        'volume_visibility': 'yes'  # Should be boolean
    }
    
    result = _validate_chart_settings(invalid_volume)
    print(f"Test 4 - Invalid volume visibility: {not result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    print("✓ Chart settings validation tests completed")


def test_trading_settings_validation():
    """Test trading settings validation logic"""
    
    # Mock the validation function from settings.py
    def _validate_trading_settings(trading_settings):
        """Validate trading settings structure and values"""
        try:
            errors = []
            
            # Validate instrument multipliers
            if 'instrument_multipliers' in trading_settings:
                multipliers = trading_settings['instrument_multipliers']
                
                if not isinstance(multipliers, dict):
                    errors.append("instrument_multipliers must be a dictionary")
                else:
                    for instrument, multiplier in multipliers.items():
                        try:
                            float(multiplier)
                        except (ValueError, TypeError):
                            errors.append(f"Invalid multiplier for {instrument}: {multiplier}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
        
        except Exception as e:
            return {
                'valid': False,
                'errors': [str(e)]
            }
    
    print("\nTesting trading settings validation...")
    print("=" * 40)
    
    # Test 1: Valid trading settings
    valid_settings = {
        'instrument_multipliers': {
            'ES': 50,
            'NQ': 20,
            'YM': 5
        }
    }
    
    result = _validate_trading_settings(valid_settings)
    print(f"Test 1 - Valid settings: {result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    # Test 2: Invalid multiplier type
    invalid_multiplier = {
        'instrument_multipliers': {
            'ES': 'invalid',  # Should be numeric
            'NQ': 20
        }
    }
    
    result = _validate_trading_settings(invalid_multiplier)
    print(f"Test 2 - Invalid multiplier: {not result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    # Test 3: Invalid multipliers structure
    invalid_structure = {
        'instrument_multipliers': 'not_a_dict'  # Should be dict
    }
    
    result = _validate_trading_settings(invalid_structure)
    print(f"Test 3 - Invalid structure: {not result['valid']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    
    print("✓ Trading settings validation tests completed")


def test_categorized_settings_structure():
    """Test the expected categorized settings structure"""
    
    print("\nTesting categorized settings structure...")
    print("=" * 40)
    
    # Expected structure
    expected_structure = {
        'chart': {
            'default_timeframe': '1h',
            'default_data_range': '1week',
            'volume_visibility': True,
            'last_updated': None
        },
        'trading': {
            'instrument_multipliers': {
                'ES': 50,
                'NQ': 20
            }
        },
        'notifications': {
            # Future category
        }
    }
    
    print("Expected structure:")
    print(f"  Categories: {list(expected_structure.keys())}")
    print(f"  Chart keys: {list(expected_structure['chart'].keys())}")
    print(f"  Trading keys: {list(expected_structure['trading'].keys())}")
    
    # Validate structure
    required_categories = ['chart', 'trading', 'notifications']
    for category in required_categories:
        if category in expected_structure:
            print(f"✓ {category} category present")
        else:
            print(f"✗ {category} category missing")
    
    # Validate chart settings
    chart_required = ['default_timeframe', 'default_data_range', 'volume_visibility']
    for key in chart_required:
        if key in expected_structure['chart']:
            print(f"✓ chart.{key} present")
        else:
            print(f"✗ chart.{key} missing")
    
    # Validate trading settings
    if 'instrument_multipliers' in expected_structure['trading']:
        print("✓ trading.instrument_multipliers present")
    else:
        print("✗ trading.instrument_multipliers missing")
    
    print("✓ Structure validation tests completed")


if __name__ == "__main__":
    print("Enhanced Settings Categories - Unit Tests")
    print("=" * 50)
    
    test_chart_settings_validation()
    test_trading_settings_validation()
    test_categorized_settings_structure()
    
    print("\n" + "=" * 50)
    print("All unit tests completed!")