"""
Settings repository for managing chart settings and application preferences
"""

import sqlite3
from typing import Dict, List, Any, Optional
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class SettingsRepository(BaseRepository):
    """Repository for application settings operations"""
    
    def get_table_name(self) -> str:
        return 'chart_settings'
    
    def get_chart_settings(self) -> Dict[str, Any]:
        """Get current chart settings"""
        query = """
            SELECT default_timeframe, default_data_range, volume_visibility, last_updated
            FROM chart_settings 
            WHERE id = 1
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        if row:
            return {
                'default_timeframe': row[0],
                'default_data_range': row[1], 
                'volume_visibility': bool(row[2]),
                'last_updated': row[3]
            }
        else:
            # Return defaults if no settings found
            return {
                'default_timeframe': '1h',
                'default_data_range': '1week',
                'volume_visibility': True,
                'last_updated': None
            }
    
    def update_chart_settings(self, timeframe: str = None, data_range: str = None,
                            volume_visibility: bool = None) -> bool:
        """Update chart settings"""
        try:
            # Get current settings first
            current_settings = self.get_chart_settings()
            
            # Use provided values or keep current ones
            new_timeframe = timeframe or current_settings['default_timeframe']
            new_data_range = data_range or current_settings['default_data_range']
            new_volume_visibility = volume_visibility if volume_visibility is not None else current_settings['volume_visibility']
            
            query = """
                INSERT OR REPLACE INTO chart_settings 
                (id, default_timeframe, default_data_range, volume_visibility, last_updated)
                VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (new_timeframe, new_data_range, int(new_volume_visibility))
            
            self._execute_with_monitoring(
                query, params,
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info("Successfully updated chart settings")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to update chart settings: {e}")
            self.rollback()
            return False
    
    def reset_chart_settings(self) -> bool:
        """Reset chart settings to defaults"""
        try:
            query = """
                INSERT OR REPLACE INTO chart_settings 
                (id, default_timeframe, default_data_range, volume_visibility, last_updated)
                VALUES (1, '1h', '1week', 1, CURRENT_TIMESTAMP)
            """
            
            self._execute_with_monitoring(
                query,
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info("Successfully reset chart settings to defaults")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to reset chart settings: {e}")
            self.rollback()
            return False