"""
Trade repository for managing all trade-related database operations
"""

import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class TradeRepository(BaseRepository):
    """Repository for trade-related database operations"""
    
    def get_table_name(self) -> str:
        return 'trades'
    
    def get_trade_by_id(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Get a single trade by ID"""
        query = """
            SELECT * FROM trades 
            WHERE id = ? AND deleted = 0
        """
        
        result = self._execute_with_monitoring(
            query, (trade_id,), 
            operation='select', 
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        return dict(row) if row else None
    
    def get_recent_trades(self, limit: int = 50, offset: int = 0, 
                         account: Optional[str] = None,
                         instrument: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         side_of_market: Optional[str] = None,
                         sort_by: str = 'entry_time',
                         sort_order: str = 'DESC') -> Tuple[List[Dict[str, Any]], int]:
        """Get recent trades with optional filtering and pagination"""
        
        # Build WHERE conditions
        conditions = ["deleted = 0"]
        params = []
        
        if account:
            conditions.append("account = ?")
            params.append(account)
        
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        
        if start_date:
            conditions.append("entry_time >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("entry_time <= ?")
            params.append(end_date)
        
        if side_of_market:
            conditions.append("side_of_market = ?")
            params.append(side_of_market)
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM trades WHERE {where_clause}"
        count_result = self._execute_with_monitoring(
            count_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        total_count = count_result.fetchone()[0]
        
        # Get paginated results
        data_query = f"""
            SELECT * FROM trades 
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        
        result = self._execute_with_monitoring(
            data_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        trades = [dict(row) for row in result.fetchall()]
        
        return trades, total_count
    
    def add_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Add a new trade to the database"""
        try:
            query = """
                INSERT INTO trades (
                    instrument, side_of_market, quantity, entry_price, entry_time,
                    exit_time, exit_price, points_gain_loss, dollars_gain_loss,
                    commission, account, chart_url, notes, validated, reviewed,
                    entry_execution_id, link_group_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                trade_data.get('instrument'),
                trade_data.get('side_of_market'),
                trade_data.get('quantity'),
                trade_data.get('entry_price'),
                trade_data.get('entry_time'),
                trade_data.get('exit_time'),
                trade_data.get('exit_price'),
                trade_data.get('points_gain_loss'),
                trade_data.get('dollars_gain_loss'),
                trade_data.get('commission'),
                trade_data.get('account'),
                trade_data.get('chart_url'),
                trade_data.get('notes'),
                trade_data.get('validated', False),
                trade_data.get('reviewed', False),
                trade_data.get('entry_execution_id'),
                trade_data.get('link_group_id')
            )
            
            self._execute_with_monitoring(
                query, params,
                operation='insert',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully added trade for {trade_data.get('instrument')}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to add trade: {e}")
            self.rollback()
            return False
    
    def update_trade_details(self, trade_id: int, chart_url: Optional[str] = None, 
                           notes: Optional[str] = None, validated: Optional[bool] = None,
                           reviewed: Optional[bool] = None) -> bool:
        """Update trade details"""
        try:
            updates = []
            params = []
            
            if chart_url is not None:
                updates.append("chart_url = ?")
                params.append(chart_url)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if validated is not None:
                updates.append("validated = ?")
                params.append(validated)
            
            if reviewed is not None:
                updates.append("reviewed = ?")
                params.append(reviewed)
            
            if not updates:
                return True  # Nothing to update
            
            query = f"""
                UPDATE trades 
                SET {', '.join(updates)}
                WHERE id = ? AND deleted = 0
            """
            params.append(trade_id)
            
            self._execute_with_monitoring(
                query, tuple(params),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully updated trade {trade_id}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to update trade {trade_id}: {e}")
            self.rollback()
            return False
    
    def delete_trades(self, trade_ids: List[int]) -> bool:
        """Soft delete trades by setting deleted flag"""
        try:
            if not trade_ids:
                return True
            
            placeholders = ','.join(['?' for _ in trade_ids])
            query = f"""
                UPDATE trades 
                SET deleted = 1 
                WHERE id IN ({placeholders})
            """
            
            self._execute_with_monitoring(
                query, tuple(trade_ids),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully deleted {len(trade_ids)} trades")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to delete trades: {e}")
            self.rollback()
            return False
    
    def link_trades(self, trade_ids: List[int]) -> Tuple[bool, Optional[int]]:
        """Link multiple trades together with a group ID"""
        try:
            if len(trade_ids) < 2:
                return False, None
            
            # Find the highest existing link_group_id
            max_group_query = "SELECT MAX(link_group_id) FROM trades"
            result = self._execute_with_monitoring(
                max_group_query, 
                operation='select',
                table=self.get_table_name()
            )
            max_group_id = result.fetchone()[0] or 0
            new_group_id = max_group_id + 1
            
            # Update all trades with the new group ID
            placeholders = ','.join(['?' for _ in trade_ids])
            update_query = f"""
                UPDATE trades 
                SET link_group_id = ? 
                WHERE id IN ({placeholders}) AND deleted = 0
            """
            
            params = [new_group_id] + trade_ids
            self._execute_with_monitoring(
                update_query, tuple(params),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully linked {len(trade_ids)} trades with group ID {new_group_id}")
            return True, new_group_id
            
        except Exception as e:
            db_logger.error(f"Failed to link trades: {e}")
            self.rollback()
            return False, None
    
    def unlink_trades(self, trade_ids: List[int]) -> bool:
        """Remove trade links by clearing group IDs"""
        try:
            if not trade_ids:
                return True
            
            placeholders = ','.join(['?' for _ in trade_ids])
            query = f"""
                UPDATE trades 
                SET link_group_id = NULL 
                WHERE id IN ({placeholders}) AND deleted = 0
            """
            
            self._execute_with_monitoring(
                query, tuple(trade_ids),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully unlinked {len(trade_ids)} trades")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to unlink trades: {e}")
            self.rollback()
            return False
    
    def get_linked_trades(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all trades linked to a specific group"""
        query = """
            SELECT * FROM trades 
            WHERE link_group_id = ? AND deleted = 0
            ORDER BY entry_time
        """
        
        result = self._execute_with_monitoring(
            query, (group_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        return [dict(row) for row in result.fetchall()]
    
    def get_unique_accounts(self) -> List[str]:
        """Get list of unique account names"""
        query = """
            SELECT DISTINCT account 
            FROM trades 
            WHERE account IS NOT NULL AND deleted = 0
            ORDER BY account
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        return [row[0] for row in result.fetchall()]
    
    def get_unique_instruments(self) -> List[str]:
        """Get list of unique instruments"""
        query = """
            SELECT DISTINCT instrument 
            FROM trades 
            WHERE instrument IS NOT NULL AND deleted = 0
            ORDER BY instrument
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        return [row[0] for row in result.fetchall()]
    
    def get_date_range(self) -> Dict[str, str]:
        """Get the earliest and latest trade dates"""
        query = """
            SELECT MIN(entry_time) as earliest, MAX(entry_time) as latest
            FROM trades 
            WHERE deleted = 0
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        return {
            'earliest': row[0] if row[0] else '',
            'latest': row[1] if row[1] else ''
        }