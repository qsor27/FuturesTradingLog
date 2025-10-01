"""
Centralized settings management system
Handles application settings, user preferences, and configuration persistence
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SettingType(Enum):
    """Types of settings"""
    SYSTEM = "system"
    USER = "user"
    CHART = "chart"
    TRADING = "trading"
    PERFORMANCE = "performance"
    IMPORT = "import"


@dataclass
class Setting:
    """Individual setting definition"""
    key: str
    value: Any
    setting_type: SettingType
    description: str = ""
    default_value: Any = None
    validation_rules: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class UserProfile:
    """User profile with settings"""
    name: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    is_default: bool = False


class SettingsValidator:
    """Validates settings values"""
    
    @staticmethod
    def validate_setting(setting: Setting) -> bool:
        """Validate a setting value against its rules"""
        if not setting.validation_rules:
            return True
        
        value = setting.value
        rules = setting.validation_rules
        
        # Type validation
        if 'type' in rules:
            expected_type = rules['type']
            if not isinstance(value, expected_type):
                try:
                    # Try to convert
                    if expected_type == int:
                        value = int(value)
                    elif expected_type == float:
                        value = float(value)
                    elif expected_type == str:
                        value = str(value)
                    elif expected_type == bool:
                        value = bool(value)
                    else:
                        return False
                    setting.value = value
                except (ValueError, TypeError):
                    return False
        
        # Range validation
        if 'min' in rules and value < rules['min']:
            return False
        if 'max' in rules and value > rules['max']:
            return False
        
        # Choices validation
        if 'choices' in rules and value not in rules['choices']:
            return False
        
        # Pattern validation
        if 'pattern' in rules:
            import re
            if not re.match(rules['pattern'], str(value)):
                return False
        
        return True
    
    @staticmethod
    def validate_settings_dict(settings: Dict[str, Any], setting_definitions: Dict[str, Setting]) -> List[str]:
        """Validate a dictionary of settings and return list of errors"""
        errors = []
        
        for key, value in settings.items():
            if key in setting_definitions:
                setting = Setting(
                    key=key,
                    value=value,
                    setting_type=setting_definitions[key].setting_type,
                    validation_rules=setting_definitions[key].validation_rules
                )
                
                if not SettingsValidator.validate_setting(setting):
                    errors.append(f"Invalid value for {key}: {value}")
        
        return errors


class SettingsManager:
    """Centralized settings management"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / 'FuturesTradingLog' / 'data' / 'config'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings_file = self.config_dir / 'settings.json'
        self.profiles_file = self.config_dir / 'user_profiles.json'
        
        self._settings: Dict[str, Setting] = {}
        self._profiles: Dict[str, UserProfile] = {}
        self._current_profile: Optional[str] = None
        self._lock = threading.RLock()
        
        self._define_default_settings()
        self._load_settings()
        self._load_profiles()
    
    def _define_default_settings(self):
        """Define default application settings"""
        self._default_settings = {
            # System settings
            'theme': Setting(
                key='theme',
                value='dark',
                setting_type=SettingType.SYSTEM,
                description='Application theme',
                default_value='dark',
                validation_rules={'choices': ['light', 'dark', 'auto']}
            ),
            
            'language': Setting(
                key='language',
                value='en',
                setting_type=SettingType.SYSTEM,
                description='Application language',
                default_value='en',
                validation_rules={'choices': ['en', 'es', 'fr', 'de', 'zh']}
            ),
            
            'timezone': Setting(
                key='timezone',
                value='UTC',
                setting_type=SettingType.SYSTEM,
                description='Application timezone',
                default_value='UTC',
                validation_rules={'type': str}
            ),
            
            # Chart settings
            'default_timeframe': Setting(
                key='default_timeframe',
                value='1h',
                setting_type=SettingType.CHART,
                description='Default chart timeframe',
                default_value='1h',
                validation_rules={'choices': ['1m', '3m', '5m', '15m', '1h', '4h', '1d']}
            ),
            
            'chart_height': Setting(
                key='chart_height',
                value=400,
                setting_type=SettingType.CHART,
                description='Chart height in pixels',
                default_value=400,
                validation_rules={'type': int, 'min': 200, 'max': 1000}
            ),
            
            'show_volume': Setting(
                key='show_volume',
                value=True,
                setting_type=SettingType.CHART,
                description='Show volume on charts',
                default_value=True,
                validation_rules={'type': bool}
            ),
            
            'show_positions': Setting(
                key='show_positions',
                value=True,
                setting_type=SettingType.CHART,
                description='Show positions on charts',
                default_value=True,
                validation_rules={'type': bool}
            ),
            
            'chart_background_color': Setting(
                key='chart_background_color',
                value='#1e1e1e',
                setting_type=SettingType.CHART,
                description='Chart background color',
                default_value='#1e1e1e',
                validation_rules={'pattern': r'^#[0-9a-fA-F]{6}$'}
            ),
            
            # Trading settings
            'default_account': Setting(
                key='default_account',
                value='',
                setting_type=SettingType.TRADING,
                description='Default trading account',
                default_value='',
                validation_rules={'type': str}
            ),
            
            'risk_per_trade': Setting(
                key='risk_per_trade',
                value=1.0,
                setting_type=SettingType.TRADING,
                description='Risk per trade as percentage',
                default_value=1.0,
                validation_rules={'type': float, 'min': 0.1, 'max': 10.0}
            ),
            
            'max_daily_loss': Setting(
                key='max_daily_loss',
                value=5.0,
                setting_type=SettingType.TRADING,
                description='Maximum daily loss percentage',
                default_value=5.0,
                validation_rules={'type': float, 'min': 1.0, 'max': 20.0}
            ),
            
            # Performance settings
            'cache_enabled': Setting(
                key='cache_enabled',
                value=True,
                setting_type=SettingType.PERFORMANCE,
                description='Enable caching for better performance',
                default_value=True,
                validation_rules={'type': bool}
            ),
            
            'cache_ttl_minutes': Setting(
                key='cache_ttl_minutes',
                value=60,
                setting_type=SettingType.PERFORMANCE,
                description='Cache TTL in minutes',
                default_value=60,
                validation_rules={'type': int, 'min': 1, 'max': 1440}
            ),
            
            'enable_performance_monitoring': Setting(
                key='enable_performance_monitoring',
                value=False,
                setting_type=SettingType.PERFORMANCE,
                description='Enable performance monitoring',
                default_value=False,
                validation_rules={'type': bool}
            ),
            
            # Import settings
            'auto_import_enabled': Setting(
                key='auto_import_enabled',
                value=True,
                setting_type=SettingType.IMPORT,
                description='Enable automatic import',
                default_value=True,
                validation_rules={'type': bool}
            ),
            
            'auto_import_interval': Setting(
                key='auto_import_interval',
                value=300,
                setting_type=SettingType.IMPORT,
                description='Auto import interval in seconds',
                default_value=300,
                validation_rules={'type': int, 'min': 10, 'max': 3600}
            ),
            
            'import_file_path': Setting(
                key='import_file_path',
                value='',
                setting_type=SettingType.IMPORT,
                description='Path to import files',
                default_value='',
                validation_rules={'type': str}
            ),
            
            # User preferences
            'positions_per_page': Setting(
                key='positions_per_page',
                value=50,
                setting_type=SettingType.USER,
                description='Number of positions per page',
                default_value=50,
                validation_rules={'type': int, 'min': 10, 'max': 200}
            ),
            
            'show_advanced_filters': Setting(
                key='show_advanced_filters',
                value=False,
                setting_type=SettingType.USER,
                description='Show advanced filter options',
                default_value=False,
                validation_rules={'type': bool}
            ),
            
            'notification_sound': Setting(
                key='notification_sound',
                value=True,
                setting_type=SettingType.USER,
                description='Enable notification sounds',
                default_value=True,
                validation_rules={'type': bool}
            ),
        }
    
    def _load_settings(self):
        """Load settings from file"""
        with self._lock:
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        settings_data = json.load(f)
                    
                    for key, data in settings_data.items():
                        if 'created_at' in data:
                            data['created_at'] = datetime.fromisoformat(data['created_at'])
                        if 'updated_at' in data:
                            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                        
                        setting = Setting(**data)
                        self._settings[key] = setting
                        
                except (json.JSONDecodeError, IOError, TypeError) as e:
                    logger.warning(f"Failed to load settings: {e}")
                    self._settings = {}
            
            # Merge with defaults
            for key, default_setting in self._default_settings.items():
                if key not in self._settings:
                    self._settings[key] = default_setting
    
    def _load_profiles(self):
        """Load user profiles from file"""
        with self._lock:
            if self.profiles_file.exists():
                try:
                    with open(self.profiles_file, 'r') as f:
                        profiles_data = json.load(f)
                    
                    for name, data in profiles_data.items():
                        data['created_at'] = datetime.fromisoformat(data['created_at'])
                        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                        
                        profile = UserProfile(**data)
                        self._profiles[name] = profile
                        
                        if profile.is_default:
                            self._current_profile = name
                            
                except (json.JSONDecodeError, IOError, TypeError) as e:
                    logger.warning(f"Failed to load profiles: {e}")
                    self._profiles = {}
            
            # Create default profile if none exists
            if not self._profiles:
                self._create_default_profile()
    
    def _create_default_profile(self):
        """Create default user profile"""
        default_profile = UserProfile(
            name='Default',
            settings={key: setting.value for key, setting in self._settings.items()},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_default=True
        )
        
        self._profiles['Default'] = default_profile
        self._current_profile = 'Default'
        self._save_profiles()
    
    def _save_settings(self):
        """Save settings to file"""
        with self._lock:
            try:
                settings_data = {}
                for key, setting in self._settings.items():
                    data = asdict(setting)
                    data['created_at'] = setting.created_at.isoformat()
                    data['updated_at'] = setting.updated_at.isoformat()
                    data['setting_type'] = setting.setting_type.value
                    settings_data[key] = data
                
                with open(self.settings_file, 'w') as f:
                    json.dump(settings_data, f, indent=2)
                    
            except IOError as e:
                logger.error(f"Failed to save settings: {e}")
    
    def _save_profiles(self):
        """Save user profiles to file"""
        with self._lock:
            try:
                profiles_data = {}
                for name, profile in self._profiles.items():
                    data = asdict(profile)
                    data['created_at'] = profile.created_at.isoformat()
                    data['updated_at'] = profile.updated_at.isoformat()
                    profiles_data[name] = data
                
                with open(self.profiles_file, 'w') as f:
                    json.dump(profiles_data, f, indent=2)
                    
            except IOError as e:
                logger.error(f"Failed to save profiles: {e}")
    
    def get_setting(self, key: str) -> Any:
        """Get a setting value"""
        with self._lock:
            if key in self._settings:
                return self._settings[key].value
            return None
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        with self._lock:
            if key in self._settings:
                setting = self._settings[key]
                old_value = setting.value
                setting.value = value
                
                # Validate the new value
                if not SettingsValidator.validate_setting(setting):
                    setting.value = old_value  # Restore old value
                    return False
                
                setting.updated_at = datetime.now()
                self._save_settings()
                
                # Update current profile if exists
                if self._current_profile and self._current_profile in self._profiles:
                    self._profiles[self._current_profile].settings[key] = value
                    self._profiles[self._current_profile].updated_at = datetime.now()
                    self._save_profiles()
                
                return True
            return False
    
    def get_settings_by_type(self, setting_type: SettingType) -> Dict[str, Any]:
        """Get all settings of a specific type"""
        with self._lock:
            result = {}
            for key, setting in self._settings.items():
                if setting.setting_type == setting_type:
                    result[key] = setting.value
            return result
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        with self._lock:
            return {key: setting.value for key, setting in self._settings.items()}
    
    def reset_setting(self, key: str) -> bool:
        """Reset a setting to its default value"""
        with self._lock:
            if key in self._default_settings:
                default_setting = self._default_settings[key]
                return self.set_setting(key, default_setting.default_value)
            return False
    
    def reset_all_settings(self):
        """Reset all settings to default values"""
        with self._lock:
            for key, default_setting in self._default_settings.items():
                self.set_setting(key, default_setting.default_value)
    
    def create_profile(self, name: str, settings: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new user profile"""
        with self._lock:
            if name in self._profiles:
                return False
            
            profile_settings = settings or self.get_all_settings()
            
            # Validate settings
            errors = SettingsValidator.validate_settings_dict(profile_settings, self._settings)
            if errors:
                logger.error(f"Invalid settings for profile {name}: {errors}")
                return False
            
            profile = UserProfile(
                name=name,
                settings=profile_settings,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_default=False
            )
            
            self._profiles[name] = profile
            self._save_profiles()
            return True
    
    def switch_profile(self, name: str) -> bool:
        """Switch to a different user profile"""
        with self._lock:
            if name not in self._profiles:
                return False
            
            profile = self._profiles[name]
            
            # Apply profile settings
            for key, value in profile.settings.items():
                if key in self._settings:
                    self._settings[key].value = value
                    self._settings[key].updated_at = datetime.now()
            
            # Update current profile
            if self._current_profile and self._current_profile in self._profiles:
                self._profiles[self._current_profile].is_default = False
            
            self._profiles[name].is_default = True
            self._current_profile = name
            
            self._save_settings()
            self._save_profiles()
            return True
    
    def get_current_profile(self) -> Optional[str]:
        """Get current profile name"""
        with self._lock:
            return self._current_profile
    
    def get_profiles(self) -> List[str]:
        """Get list of profile names"""
        with self._lock:
            return list(self._profiles.keys())
    
    def delete_profile(self, name: str) -> bool:
        """Delete a user profile"""
        with self._lock:
            if name not in self._profiles or name == 'Default':
                return False
            
            # If deleting current profile, switch to default
            if self._current_profile == name:
                self.switch_profile('Default')
            
            del self._profiles[name]
            self._save_profiles()
            return True
    
    def export_settings(self, file_path: Optional[Path] = None) -> bool:
        """Export settings to file"""
        with self._lock:
            try:
                export_data = {
                    'settings': self.get_all_settings(),
                    'profiles': {name: asdict(profile) for name, profile in self._profiles.items()},
                    'current_profile': self._current_profile,
                    'exported_at': datetime.now().isoformat()
                }
                
                # Convert datetime objects to strings
                for profile_data in export_data['profiles'].values():
                    profile_data['created_at'] = profile_data['created_at'].isoformat() if isinstance(profile_data['created_at'], datetime) else profile_data['created_at']
                    profile_data['updated_at'] = profile_data['updated_at'].isoformat() if isinstance(profile_data['updated_at'], datetime) else profile_data['updated_at']
                
                export_path = file_path or self.config_dir / f'settings_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                
                with open(export_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                return True
                
            except IOError as e:
                logger.error(f"Failed to export settings: {e}")
                return False
    
    def import_settings(self, file_path: Path) -> bool:
        """Import settings from file"""
        with self._lock:
            try:
                with open(file_path, 'r') as f:
                    import_data = json.load(f)
                
                # Validate import data
                if 'settings' not in import_data:
                    logger.error("Invalid import file: missing settings")
                    return False
                
                # Validate settings
                errors = SettingsValidator.validate_settings_dict(import_data['settings'], self._settings)
                if errors:
                    logger.error(f"Invalid settings in import file: {errors}")
                    return False
                
                # Apply settings
                for key, value in import_data['settings'].items():
                    if key in self._settings:
                        self.set_setting(key, value)
                
                # Import profiles if present
                if 'profiles' in import_data:
                    for name, profile_data in import_data['profiles'].items():
                        if name not in self._profiles:
                            profile_data['created_at'] = datetime.fromisoformat(profile_data['created_at'])
                            profile_data['updated_at'] = datetime.fromisoformat(profile_data['updated_at'])
                            self._profiles[name] = UserProfile(**profile_data)
                
                self._save_settings()
                self._save_profiles()
                return True
                
            except (IOError, json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to import settings: {e}")
                return False
    
    def get_setting_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a setting"""
        with self._lock:
            if key in self._settings:
                setting = self._settings[key]
                return {
                    'key': setting.key,
                    'value': setting.value,
                    'type': setting.setting_type.value,
                    'description': setting.description,
                    'default_value': setting.default_value,
                    'validation_rules': setting.validation_rules,
                    'created_at': setting.created_at.isoformat(),
                    'updated_at': setting.updated_at.isoformat()
                }
            return None
    
    def get_settings_summary(self) -> Dict[str, Any]:
        """Get summary of all settings"""
        with self._lock:
            summary = {
                'total_settings': len(self._settings),
                'settings_by_type': {},
                'current_profile': self._current_profile,
                'total_profiles': len(self._profiles),
                'last_updated': max(setting.updated_at for setting in self._settings.values()).isoformat() if self._settings else None
            }
            
            for setting_type in SettingType:
                count = sum(1 for setting in self._settings.values() if setting.setting_type == setting_type)
                summary['settings_by_type'][setting_type.value] = count
            
            return summary


# Global settings manager instance
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """Get global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager

def get_setting(key: str) -> Any:
    """Convenience function to get a setting value"""
    return get_settings_manager().get_setting(key)

def set_setting(key: str, value: Any) -> bool:
    """Convenience function to set a setting value"""
    return get_settings_manager().set_setting(key, value)