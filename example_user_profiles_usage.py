#!/usr/bin/env python3
"""
Example usage of the user_profiles functionality
This demonstrates how to use the new user profile methods
"""

import json
from datetime import datetime

def example_user_profiles_usage():
    """
    Example showing how to use the user_profiles functionality
    
    Note: This is a demonstration script. In actual use, you would:
    1. Import TradingLog_db: from TradingLog_db import FuturesDB
    2. Use with FuturesDB() as db: to get a database connection
    """
    
    print("User Profiles Usage Examples")
    print("="*50)
    
    # Example 1: Creating user profiles
    print("\n1. Creating User Profiles")
    print("-" * 30)
    
    # Create different profile configurations
    scalping_settings = {
        'chart_settings': {
            'default_timeframe': '1m',
            'default_data_range': '3hours',
            'volume_visibility': True
        },
        'instrument_multipliers': {
            'NQ': 20,
            'ES': 50
        },
        'theme_settings': {
            'dark_mode': True,
            'chart_background': '#000000'
        }
    }
    
    swing_settings = {
        'chart_settings': {
            'default_timeframe': '4h',
            'default_data_range': '1month',
            'volume_visibility': False
        },
        'instrument_multipliers': {
            'NQ': 20,
            'ES': 50,
            'YM': 5
        },
        'theme_settings': {
            'dark_mode': False,
            'chart_background': '#ffffff'
        }
    }
    
    day_trading_settings = {
        'chart_settings': {
            'default_timeframe': '15m',
            'default_data_range': '1week',
            'volume_visibility': True
        },
        'instrument_multipliers': {
            'NQ': 20,
            'ES': 50,
            'RTY': 50
        },
        'theme_settings': {
            'dark_mode': True,
            'chart_background': '#1a1a1a'
        }
    }
    
    print("Example profile creation:")
    print("# Create a scalping profile as default")
    print("profile_id = db.create_user_profile(")
    print("    profile_name='Scalping Setup',")
    print("    settings_snapshot=scalping_settings,")
    print("    description='Fast scalping configuration for NQ/ES',")
    print("    is_default=True")
    print(")")
    
    print("\n# Create additional profiles")
    print("swing_id = db.create_user_profile(")
    print("    profile_name='Swing Trading',")
    print("    settings_snapshot=swing_settings,")
    print("    description='Longer timeframe setup for swing positions'")
    print(")")
    
    # Example 2: Retrieving user profiles
    print("\n2. Retrieving User Profiles")
    print("-" * 30)
    
    print("# Get all profiles for a user")
    print("profiles = db.get_user_profiles(user_id=1)")
    print("for profile in profiles:")
    print("    print(f'Profile: {profile[\"profile_name\"]}')") 
    print("    print(f'Default: {profile[\"is_default\"]}')") 
    print("    print(f'Description: {profile[\"description\"]}')") 
    print()
    
    print("# Get a specific profile by name")
    print("scalping_profile = db.get_user_profile_by_name('Scalping Setup')")
    print("if scalping_profile:")
    print("    settings = scalping_profile['settings_snapshot']")
    print("    timeframe = settings['chart_settings']['default_timeframe']")
    print("    print(f'Scalping timeframe: {timeframe}')")
    print()
    
    print("# Get the default profile")
    print("default_profile = db.get_default_user_profile()")
    print("if default_profile:")
    print("    print(f'Default profile: {default_profile[\"profile_name\"]}')") 
    
    # Example 3: Updating profiles
    print("\n3. Updating User Profiles")
    print("-" * 30)
    
    print("# Update profile settings")
    print("updated_settings = scalping_settings.copy()")
    print("updated_settings['chart_settings']['default_timeframe'] = '3m'")
    print()
    print("success = db.update_user_profile(")
    print("    profile_id=profile_id,")
    print("    settings_snapshot=updated_settings,")
    print("    description='Updated scalping setup with 3m timeframe'")
    print(")")
    
    print("\n# Make a different profile the default")
    print("db.update_user_profile(swing_id, is_default=True)")
    
    # Example 4: Using profiles in application
    print("\n4. Application Integration")
    print("-" * 30)
    
    print("# Example: Load user's default settings on app startup")
    print("def load_user_settings():")
    print("    with FuturesDB() as db:")
    print("        default_profile = db.get_default_user_profile()")
    print("        if default_profile:")
    print("            settings = default_profile['settings_snapshot']")
    print("            apply_chart_settings(settings['chart_settings'])")
    print("            apply_instrument_multipliers(settings['instrument_multipliers'])")
    print("            apply_theme_settings(settings['theme_settings'])")
    print("        else:")
    print("            # Use system defaults")
    print("            apply_default_settings()")
    print()
    
    print("# Example: Switch to a different profile")
    print("def switch_profile(profile_name):")
    print("    with FuturesDB() as db:")
    print("        profile = db.get_user_profile_by_name(profile_name)")
    print("        if profile:")
    print("            settings = profile['settings_snapshot']")
    print("            apply_settings(settings)")
    print("            # Optionally make it the new default")
    print("            # db.update_user_profile(profile['id'], is_default=True)")
    print("        else:")
    print("            print(f'Profile {profile_name} not found')")
    
    # Example 5: Profile management
    print("\n5. Profile Management")
    print("-" * 30)
    
    print("# Create a new profile from current settings")
    print("def save_current_as_profile(profile_name, description):")
    print("    current_settings = {")
    print("        'chart_settings': get_current_chart_settings(),")
    print("        'instrument_multipliers': get_current_multipliers(),")
    print("        'theme_settings': get_current_theme_settings()")
    print("    }")
    print("    ")
    print("    with FuturesDB() as db:")
    print("        profile_id = db.create_user_profile(")
    print("            profile_name=profile_name,")
    print("            settings_snapshot=current_settings,")
    print("            description=description")
    print("        )")
    print("        return profile_id")
    print()
    
    print("# Export profile for sharing")
    print("def export_profile(profile_name, filepath):")
    print("    with FuturesDB() as db:")
    print("        profile = db.get_user_profile_by_name(profile_name)")
    print("        if profile:")
    print("            export_data = {")
    print("                'profile_name': profile['profile_name'],")
    print("                'description': profile['description'],")
    print("                'settings_snapshot': profile['settings_snapshot'],")
    print("                'exported_at': datetime.now().isoformat()")
    print("            }")
    print("            with open(filepath, 'w') as f:")
    print("                json.dump(export_data, f, indent=2)")
    
    # Example 6: Data structure examples
    print("\n6. Data Structure Examples")
    print("-" * 30)
    
    print("# Example settings_snapshot structure:")
    print("settings_snapshot = {")
    print("    'chart_settings': {")
    print("        'default_timeframe': '1h',")
    print("        'default_data_range': '1week',")
    print("        'volume_visibility': True")
    print("    },")
    print("    'instrument_multipliers': {")
    print("        'NQ': 20,")
    print("        'ES': 50,")
    print("        'YM': 5,")
    print("        'RTY': 50")
    print("    },")
    print("    'theme_settings': {")
    print("        'dark_mode': True,")
    print("        'chart_background': '#000000',")
    print("        'grid_color': '#333333'")
    print("    },")
    print("    'display_preferences': {")
    print("        'show_pnl': True,")
    print("        'show_volume': True,")
    print("        'decimal_places': 2")
    print("    }")
    print("}")
    
    print(f"\nJSON representation:")
    print(json.dumps(scalping_settings, indent=2))
    
    print("\n" + "="*50)
    print("Implementation complete! The user_profiles schema is ready for use.")
    print("="*50)

if __name__ == "__main__":
    example_user_profiles_usage()