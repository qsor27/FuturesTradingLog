"""
Position repository for managing position-related database operations
"""

import sqlite3
from typing import Dict, List, Any, Optional, Tuple
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class PositionRepository(BaseRepository):
    """Repository for position-related database operations"""
    
    def get_table_name(self) -> str:
        return 'positions'
    
    def get_positions(self, account: str = None, instrument: str = None,
                     start_date: str = None, end_date: str = None,
                     limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Get positions with optional filtering and pagination"""
        
        # Build WHERE conditions
        conditions = ["deleted = 0"]  # Assuming positions table has deleted column
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
            conditions.append("exit_time <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM positions WHERE {where_clause}"
        count_result = self._execute_with_monitoring(
            count_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        total_count = count_result.fetchone()[0]
        
        # Get paginated results
        data_query = f"""
            SELECT * FROM positions 
            WHERE {where_clause}
            ORDER BY entry_time DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        
        result = self._execute_with_monitoring(
            data_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        positions = [dict(row) for row in result.fetchall()]
        
        return positions, total_count
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """Get a single position by ID"""
        query = """
            SELECT * FROM positions 
            WHERE id = ? AND deleted = 0
        """
        
        result = self._execute_with_monitoring(
            query, (position_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        return dict(row) if row else None
    
    def get_position_executions(self, position_id: int) -> List[Dict[str, Any]]:
        """Get all executions that make up a position"""
        query = """
            SELECT t.* FROM trades t
            INNER JOIN position_executions pe ON t.id = pe.trade_id
            WHERE pe.position_id = ? AND t.deleted = 0
            ORDER BY t.entry_time ASC
        """
        
        result = self._execute_with_monitoring(
            query, (position_id,),
            operation='select',
            table='trades'  # This query primarily uses trades table
        )
        
        return [dict(row) for row in result.fetchall()]
    
    def create_position(self, position_data: Dict[str, Any]) -> Optional[int]:
        """Create a new position record"""
        try:
            query = """
                INSERT INTO positions (
                    account, instrument, side, entry_time, exit_time,
                    entry_price, exit_price, quantity, points_gain_loss,
                    dollars_gain_loss, commission, duration_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                position_data.get('account'),
                position_data.get('instrument'),
                position_data.get('side'),
                position_data.get('entry_time'),
                position_data.get('exit_time'),
                position_data.get('entry_price'),
                position_data.get('exit_price'),
                position_data.get('quantity'),
                position_data.get('points_gain_loss'),
                position_data.get('dollars_gain_loss'),
                position_data.get('commission'),
                position_data.get('duration_minutes')
            )
            
            result = self._execute_with_monitoring(
                query, params,
                operation='insert',
                table=self.get_table_name()
            )
            
            position_id = result.lastrowid
            self.commit()
            
            db_logger.info(f"Successfully created position {position_id}")
            return position_id
            
        except Exception as e:
            db_logger.error(f"Failed to create position: {e}")
            self.rollback()
            return None
    
    def link_trade_to_position(self, position_id: int, trade_id: int) -> bool:
        """Link a trade execution to a position"""
        try:
            query = """
                INSERT INTO position_executions (position_id, trade_id)
                VALUES (?, ?)
            """
            
            self._execute_with_monitoring(
                query, (position_id, trade_id),
                operation='insert',
                table='position_executions'
            )
            
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to link trade {trade_id} to position {position_id}: {e}")
            return False
    
    def update_position(self, position_id: int, **updates) -> bool:
        """Update position fields"""
        try:
            if not updates:
                return True
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            for field, value in updates.items():
                update_fields.append(f"{field} = ?")
                params.append(value)
            
            query = f"""
                UPDATE positions 
                SET {', '.join(update_fields)}
                WHERE id = ? AND deleted = 0
            """
            params.append(position_id)
            
            self._execute_with_monitoring(
                query, tuple(params),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully updated position {position_id}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to update position {position_id}: {e}")
            self.rollback()
            return False
    
    def delete_position(self, position_id: int) -> bool:
        """Soft delete a position"""
        try:
            query = """
                UPDATE positions 
                SET deleted = 1 
                WHERE id = ?
            """
            
            self._execute_with_monitoring(
                query, (position_id,),
                operation='update',
                table=self.get_table_name()
            )
            
            self.commit()
            db_logger.info(f"Successfully deleted position {position_id}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to delete position {position_id}: {e}")
            self.rollback()
            return False
    
    def get_position_summary(self, account: str = None, instrument: str = None) -> Dict[str, Any]:
        """Get summary statistics for positions"""
        conditions = ["deleted = 0"]
        params = []
        
        if account:
            conditions.append("account = ?")
            params.append(account)
        
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                COUNT(*) as total_positions,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_positions,
                SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_positions,
                AVG(dollars_gain_loss) as avg_pnl,
                SUM(dollars_gain_loss) as total_pnl,
                MAX(dollars_gain_loss) as best_position,
                MIN(dollars_gain_loss) as worst_position,
                AVG(duration_minutes) as avg_duration_minutes,
                AVG(quantity) as avg_quantity
            FROM positions 
            WHERE {where_clause}
        """
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        if not row:
            return {}
        
        total_positions = row[0] or 0
        winning_positions = row[1] or 0
        
        win_rate = (winning_positions / total_positions * 100) if total_positions > 0 else 0
        
        return {
            'total_positions': total_positions,
            'winning_positions': winning_positions,
            'losing_positions': row[2] or 0,
            'win_rate': round(win_rate, 2),
            'avg_pnl': round(row[3] or 0, 2),
            'total_pnl': round(row[4] or 0, 2),
            'best_position': round(row[5] or 0, 2),
            'worst_position': round(row[6] or 0, 2),
            'avg_duration_minutes': round(row[7] or 0, 2),
            'avg_quantity': round(row[8] or 0, 2)
        }