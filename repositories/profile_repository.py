"""
Profile repository for managing user profiles and settings snapshots
"""

import sqlite3
from typing import Dict, List, Any, Optional
import json
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class ProfileRepository(BaseRepository):
    """Repository for user profile operations"""
    
    def get_table_name(self) -> str:
        return 'user_profiles'
    
    def create_user_profile(self, user_id: int, profile_name: str, 
                          settings_snapshot: Dict[str, Any], description: str = None,
                          is_default: bool = False) -> Optional[int]:
        """Create a new user profile"""
        try:
            # If setting as default, unset other defaults first
            if is_default:
                self._unset_default_profiles(user_id)
            
            query = """
                INSERT INTO user_profiles 
                (user_id, profile_name, description, settings_snapshot, is_default, version)
                VALUES (?, ?, ?, ?, ?, 1)
            """
            
            params = (
                user_id,
                profile_name,
                description,
                json.dumps(settings_snapshot),
                is_default
            )
            
            result = self._execute_with_monitoring(
                query, params,
                operation='insert',
                table=self.get_table_name()
            )
            
            profile_id = result.lastrowid
            self.commit()
            
            db_logger.info(f"Successfully created profile '{profile_name}' with ID {profile_id}")
            return profile_id
            
        except Exception as e:
            db_logger.error(f"Failed to create profile '{profile_name}': {e}")
            self.rollback()
            return None
    
    def get_user_profiles(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all profiles for a user"""
        query = """
            SELECT id, profile_name, description, is_default, version, created_at, updated_at
            FROM user_profiles 
            WHERE user_id = ?
            ORDER BY is_default DESC, profile_name ASC
        """
        
        result = self._execute_with_monitoring(
            query, (user_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        profiles = []
        for row in result.fetchall():
            profiles.append({
                'id': row[0],
                'profile_name': row[1],
                'description': row[2],
                'is_default': bool(row[3]),
                'version': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            })
        
        return profiles
    
    def get_user_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific profile by ID"""
        query = """
            SELECT id, user_id, profile_name, description, settings_snapshot, 
                   is_default, version, created_at, updated_at
            FROM user_profiles 
            WHERE id = ?
        """
        
        result = self._execute_with_monitoring(
            query, (profile_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'profile_name': row[2],
                'description': row[3],
                'settings_snapshot': json.loads(row[4]),
                'is_default': bool(row[5]),
                'version': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
    
    def get_user_profile_by_name(self, user_id: int, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by name"""
        query = """
            SELECT id, user_id, profile_name, description, settings_snapshot, 
                   is_default, version, created_at, updated_at
            FROM user_profiles 
            WHERE user_id = ? AND profile_name = ?
        """
        
        result = self._execute_with_monitoring(
            query, (user_id, profile_name),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'profile_name': row[2],
                'description': row[3],
                'settings_snapshot': json.loads(row[4]),
                'is_default': bool(row[5]),
                'version': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
    
    def update_user_profile(self, profile_id: int, profile_name: str = None,
                          description: str = None, settings_snapshot: Dict[str, Any] = None,
                          is_default: bool = None) -> bool:
        """Update an existing profile"""
        try:
            # Get current profile first
            current_profile = self.get_user_profile(profile_id)
            if not current_profile:
                return False
            
            # If setting as default, unset other defaults first
            if is_default:
                self._unset_default_profiles(current_profile['user_id'])
            
            # Build update query dynamically
            updates = []
            params = []
            
            if profile_name is not None:
                updates.append("profile_name = ?")
                params.append(profile_name)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if settings_snapshot is not None:
                updates.append("settings_snapshot = ?")
                updates.append("version = version + 1")
                params.append(json.dumps(settings_snapshot))
            
            if is_default is not None:
                updates.append("is_default = ?")
                params.append(is_default)
            
            if not updates:
                return True  # Nothing to update
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"""
                UPDATE user_profiles 
                SET {', '.join(updates)}
                WHERE id = ?
            """
            params.append(profile_id)
            
            self._execute_with_monitoring(
                query, tuple(params),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully updated profile {profile_id}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to update profile {profile_id}: {e}")
            self.rollback()
            return False
    
    def delete_user_profile(self, profile_id: int) -> bool:
        """Delete a profile"""
        try:
            # Check if this is the only profile for the user
            profile = self.get_user_profile(profile_id)
            if not profile:
                return False
            
            user_profiles = self.get_user_profiles(profile['user_id'])
            if len(user_profiles) <= 1:
                db_logger.warning(f"Cannot delete profile {profile_id}: User must have at least one profile")
                return False
            
            query = "DELETE FROM user_profiles WHERE id = ?"
            
            self._execute_with_monitoring(
                query, (profile_id,),
                operation='delete',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully deleted profile {profile_id}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to delete profile {profile_id}: {e}")
            self.rollback()
            return False
    
    def get_default_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get the default profile for a user"""
        query = """
            SELECT id, user_id, profile_name, description, settings_snapshot, 
                   is_default, version, created_at, updated_at
            FROM user_profiles 
            WHERE user_id = ? AND is_default = 1
        """
        
        result = self._execute_with_monitoring(
            query, (user_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'profile_name': row[2],
                'description': row[3],
                'settings_snapshot': json.loads(row[4]),
                'is_default': bool(row[5]),
                'version': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
    
    def _unset_default_profiles(self, user_id: int) -> None:
        """Unset all default profiles for a user (internal helper)"""
        query = """
            UPDATE user_profiles 
            SET is_default = 0 
            WHERE user_id = ? AND is_default = 1
        """
        
        self._execute_with_monitoring(
            query, (user_id,),
            operation='update',
            table=self.get_table_name()
        )