"""
Instrument Management Service - User-Configurable Instrument Lists

Allows users to customize which instruments are used for background services,
gap filling, and cache warming instead of hardcoded lists.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

db_logger = logging.getLogger('database')


@dataclass
class InstrumentGroup:
    """Represents a group of instruments for a specific purpose"""
    name: str
    description: str
    instruments: List[str]
    is_active: bool = True


class InstrumentManagementService:
    """
    Service for managing user-configurable instrument lists
    
    Replaces hardcoded instrument lists with database-backed, user-configurable groups.
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager for repository access"""
        self.db_manager = db_manager
        self._default_groups = self._get_default_groups()
    
    def _get_default_groups(self) -> Dict[str, InstrumentGroup]:
        """Define default instrument groups"""
        return {
            'gap_filling': InstrumentGroup(
                name='gap_filling',
                description='Instruments for regular gap filling (every 15 minutes)',
                instruments=['MNQ', 'ES', 'YM', 'RTY']
            ),
            'extended_gap_filling': InstrumentGroup(
                name='extended_gap_filling', 
                description='Instruments for extended gap filling (every 4 hours)',
                instruments=['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']
            ),
            'popular_instruments': InstrumentGroup(
                name='popular_instruments',
                description='Popular instruments for cache warming',
                instruments=['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']
            )
        }
    
    def get_instrument_group(self, group_name: str) -> List[str]:
        """
        Get instruments for a specific group
        
        Args:
            group_name: Name of the instrument group
            
        Returns:
            List of instrument symbols
        """
        try:
            # Try to get from database first
            query = """
                SELECT instruments, is_active
                FROM instrument_groups 
                WHERE group_name = ? AND is_active = 1
            """
            
            result = self.db_manager.cursor.execute(query, (group_name,))
            row = result.fetchone()
            
            if row:
                # Parse comma-separated instruments from database
                instruments_str, is_active = row
                if is_active:
                    return [inst.strip() for inst in instruments_str.split(',') if inst.strip()]
            
            # Fall back to defaults if not found in database
            if group_name in self._default_groups:
                default_group = self._default_groups[group_name]
                db_logger.info(f"Using default instruments for {group_name}: {default_group.instruments}")
                return default_group.instruments
            else:
                db_logger.warning(f"Unknown instrument group: {group_name}")
                return []
                
        except Exception as e:
            db_logger.error(f"Error getting instrument group {group_name}: {e}")
            # Return defaults on error
            if group_name in self._default_groups:
                return self._default_groups[group_name].instruments
            return []
    
    def set_instrument_group(self, group_name: str, instruments: List[str], description: str = None) -> bool:
        """
        Set instruments for a specific group
        
        Args:
            group_name: Name of the instrument group
            instruments: List of instrument symbols
            description: Optional description of the group
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert list to comma-separated string
            instruments_str = ', '.join(instruments)
            
            # Use description if provided, otherwise use default
            if description is None and group_name in self._default_groups:
                description = self._default_groups[group_name].description
            elif description is None:
                description = f"Custom instrument group: {group_name}"
            
            # Insert or update the group
            query = """
                INSERT OR REPLACE INTO instrument_groups 
                (group_name, description, instruments, is_active, last_updated)
                VALUES (?, ?, ?, 1, datetime('now'))
            """
            
            self.db_manager.cursor.execute(query, (group_name, description, instruments_str))
            self.db_manager.conn.commit()
            
            db_logger.info(f"Updated instrument group {group_name}: {instruments}")
            return True
            
        except Exception as e:
            db_logger.error(f"Error setting instrument group {group_name}: {e}")
            self.db_manager.conn.rollback()
            return False
    
    def get_all_groups(self) -> Dict[str, InstrumentGroup]:
        """
        Get all instrument groups (both database and defaults)
        
        Returns:
            Dictionary of group_name -> InstrumentGroup
        """
        groups = {}
        
        try:
            # Get groups from database
            query = """
                SELECT group_name, description, instruments, is_active
                FROM instrument_groups
                ORDER BY group_name
            """
            
            result = self.db_manager.cursor.execute(query)
            for row in result.fetchall():
                group_name, description, instruments_str, is_active = row
                instruments = [inst.strip() for inst in instruments_str.split(',') if inst.strip()]
                
                groups[group_name] = InstrumentGroup(
                    name=group_name,
                    description=description,
                    instruments=instruments,
                    is_active=bool(is_active)
                )
        
        except Exception as e:
            db_logger.warning(f"Error loading groups from database: {e}")
        
        # Add defaults for any missing groups
        for name, default_group in self._default_groups.items():
            if name not in groups:
                groups[name] = default_group
        
        return groups
    
    def delete_group(self, group_name: str) -> bool:
        """
        Delete a custom instrument group (cannot delete default groups)
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            True if successful, False otherwise
        """
        if group_name in self._default_groups:
            db_logger.warning(f"Cannot delete default group: {group_name}")
            return False
        
        try:
            query = "DELETE FROM instrument_groups WHERE group_name = ?"
            self.db_manager.cursor.execute(query, (group_name,))
            self.db_manager.conn.commit()
            
            db_logger.info(f"Deleted instrument group: {group_name}")
            return True
            
        except Exception as e:
            db_logger.error(f"Error deleting instrument group {group_name}: {e}")
            self.db_manager.conn.rollback()
            return False
    
    def initialize_default_groups(self) -> bool:
        """
        Initialize default groups in database if they don't exist
        
        Returns:
            True if successful, False otherwise
        """
        try:
            for group_name, group in self._default_groups.items():
                # Check if group already exists
                check_query = "SELECT COUNT(*) FROM instrument_groups WHERE group_name = ?"
                result = self.db_manager.cursor.execute(check_query, (group_name,))
                
                if result.fetchone()[0] == 0:
                    # Group doesn't exist, create it
                    self.set_instrument_group(group_name, group.instruments, group.description)
            
            return True
        except Exception as e:
            db_logger.error(f"Error initializing default groups: {e}")
            return False