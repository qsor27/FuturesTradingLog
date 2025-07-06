"""
Base repository class providing common database operations and monitoring
"""

import sqlite3
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from abc import ABC, abstractmethod

# Get database logger
db_logger = logging.getLogger('database')


class BaseRepository(ABC):
    """Base repository class with shared database functionality"""
    
    def __init__(self, connection: sqlite3.Connection, cursor: sqlite3.Cursor):
        """Initialize repository with database connection and cursor"""
        self.conn = connection
        self.cursor = cursor
    
    def _execute_with_monitoring(self, query: str, params: tuple = None, 
                               operation: str = "query", table: str = "unknown") -> sqlite3.Cursor:
        """Execute query with monitoring metrics collection"""
        start_time = time.time()
        
        try:
            if params:
                result = self.cursor.execute(query, params)
            else:
                result = self.cursor.execute(query)
            
            duration = time.time() - start_time
            
            # Record metrics (import locally to avoid circular imports)
            try:
                from app import record_database_query
                record_database_query(table, operation, duration)
            except ImportError:
                # App module not available (e.g., during testing)
                pass
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            # Still record the failed query for monitoring
            try:
                from app import record_database_query
                record_database_query(table, f"{operation}_error", duration)
            except ImportError:
                pass
            raise e
    
    def _detect_table_from_query(self, query: str) -> str:
        """Detect the primary table being queried for monitoring purposes"""
        query_lower = query.lower().strip()
        
        if 'from trades' in query_lower or 'update trades' in query_lower or 'insert into trades' in query_lower:
            return 'trades'
        elif 'from ohlc_data' in query_lower or 'update ohlc_data' in query_lower or 'insert into ohlc_data' in query_lower:
            return 'ohlc_data'
        elif 'from positions' in query_lower or 'update positions' in query_lower or 'insert into positions' in query_lower:
            return 'positions'
        elif 'from chart_settings' in query_lower or 'update chart_settings' in query_lower:
            return 'chart_settings'
        elif 'from user_profiles' in query_lower or 'update user_profiles' in query_lower or 'insert into user_profiles' in query_lower:
            return 'user_profiles'
        elif 'from profile_history' in query_lower or 'update profile_history' in query_lower or 'insert into profile_history' in query_lower:
            return 'profile_history'
        else:
            return 'unknown'
    
    def _detect_operation_from_query(self, query: str) -> str:
        """Detect the operation type for monitoring purposes"""
        query_lower = query.lower().strip()
        
        if query_lower.startswith('select'):
            return 'select'
        elif query_lower.startswith('insert'):
            return 'insert'
        elif query_lower.startswith('update'):
            return 'update'
        elif query_lower.startswith('delete'):
            return 'delete'
        elif query_lower.startswith('pragma'):
            return 'pragma'
        else:
            return 'other'
    
    def commit(self) -> None:
        """Commit the current transaction"""
        self.conn.commit()
    
    def rollback(self) -> None:
        """Rollback the current transaction"""
        self.conn.rollback()
    
    @abstractmethod
    def get_table_name(self) -> str:
        """Return the primary table name this repository manages"""
        pass