import sqlite3
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager
from .interfaces import (
    ITradeRepository, IPositionRepository, IOHLCRepository, 
    ISettingsRepository, IProfileRepository, IStatisticsRepository,
    TradeRecord, PositionRecord, OHLCRecord
)

db_logger = logging.getLogger('database')

class SQLiteRepository:
    """Base repository class for SQLite operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper context management"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def _execute_with_monitoring(self, conn: sqlite3.Connection, query: str, params: tuple = None, 
                                operation: str = "query", table: str = "unknown"):
        """Execute query with monitoring metrics collection"""
        import time
        
        start_time = time.time()
        cursor = conn.cursor()
        
        try:
            if params:
                result = cursor.execute(query, params)
            else:
                result = cursor.execute(query)
            
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
    
    def _row_to_trade(self, row: sqlite3.Row) -> TradeRecord:
        """Convert database row to TradeRecord"""
        return TradeRecord(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['entry_time']) if row['entry_time'] else None,
            instrument=row['instrument'],
            quantity=row['quantity'],
            price=row['entry_price'],
            side=row['side_of_market'],
            commission=row['commission'],
            realized_pnl=row['dollars_gain_loss'],
            link_group_id=str(row['link_group_id']) if row['link_group_id'] else None
        )
    
    def _row_to_position(self, row: sqlite3.Row) -> PositionRecord:
        """Convert database row to PositionRecord"""
        return PositionRecord(
            id=row['id'],
            start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
            instrument=row['instrument'],
            side=row['side'],
            quantity=row['quantity'],
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            realized_pnl=row['realized_pnl'],
            commission=row['commission'],
            link_group_id=str(row['link_group_id']) if row['link_group_id'] else None,
            mae=row['mae'] if 'mae' in row.keys() else None,
            mfe=row['mfe'] if 'mfe' in row.keys() else None
        )
    
    def _row_to_ohlc(self, row: sqlite3.Row) -> OHLCRecord:
        """Convert database row to OHLCRecord"""
        return OHLCRecord(
            id=row['id'],
            timestamp=datetime.fromtimestamp(row['timestamp']) if row['timestamp'] else None,
            instrument=row['instrument'],
            open=row['open_price'],
            high=row['high_price'],
            low=row['low_price'],
            close=row['close_price'],
            volume=row['volume']
        )

class SQLiteTradeRepository(SQLiteRepository, ITradeRepository):
    """SQLite implementation of trade repository"""
    
    def create_trade(self, trade: TradeRecord) -> int:
        """Create a new trade record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """INSERT INTO trades (instrument, side_of_market, quantity, entry_price, entry_time, 
                   commission, dollars_gain_loss, link_group_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (trade.instrument, trade.side, trade.quantity, trade.price, 
                 trade.timestamp.isoformat() if trade.timestamp else None,
                 trade.commission, trade.realized_pnl, trade.link_group_id),
                "insert", "trades"
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_trade(self, trade_id: int) -> Optional[TradeRecord]:
        """Get a trade by ID"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM trades WHERE id = ? AND deleted = 0",
                (trade_id,),
                "select", "trades"
            )
            row = cursor.fetchone()
            return self._row_to_trade(row) if row else None
    
    def get_trades_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                end_date: Optional[datetime] = None) -> List[TradeRecord]:
        """Get trades for a specific instrument"""
        with self.get_connection() as conn:
            query = "SELECT * FROM trades WHERE instrument = ? AND deleted = 0"
            params = [instrument]
            
            if start_date:
                query += " AND entry_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND entry_time <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY entry_time"
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params), "select", "trades"
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def get_trades_by_link_group(self, link_group_id: str) -> List[TradeRecord]:
        """Get trades by link group ID"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM trades WHERE link_group_id = ? AND deleted = 0 ORDER BY entry_time",
                (link_group_id,),
                "select", "trades"
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def update_trade(self, trade: TradeRecord) -> bool:
        """Update an existing trade record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """UPDATE trades SET instrument = ?, side_of_market = ?, quantity = ?, 
                   entry_price = ?, entry_time = ?, commission = ?, dollars_gain_loss = ?, 
                   link_group_id = ? WHERE id = ?""",
                (trade.instrument, trade.side, trade.quantity, trade.price,
                 trade.timestamp.isoformat() if trade.timestamp else None,
                 trade.commission, trade.realized_pnl, trade.link_group_id, trade.id),
                "update", "trades"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_trade(self, trade_id: int) -> bool:
        """Delete a trade record (soft delete)"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "UPDATE trades SET deleted = 1 WHERE id = ?",
                (trade_id,),
                "update", "trades"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_trades(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[TradeRecord]:
        """Get all trades with optional pagination"""
        with self.get_connection() as conn:
            query = "SELECT * FROM trades WHERE deleted = 0 ORDER BY entry_time DESC"
            params = []
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
                
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params) if params else None, "select", "trades"
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]

class SQLitePositionRepository(SQLiteRepository, IPositionRepository):
    """SQLite implementation of position repository"""
    
    def create_position(self, position: PositionRecord) -> int:
        """Create a new position record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """INSERT INTO positions (start_time, end_time, instrument, side, quantity, 
                   entry_price, exit_price, realized_pnl, commission, link_group_id, mae, mfe) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (position.start_time.isoformat() if position.start_time else None,
                 position.end_time.isoformat() if position.end_time else None,
                 position.instrument, position.side, position.quantity,
                 position.entry_price, position.exit_price, position.realized_pnl,
                 position.commission, position.link_group_id, position.mae, position.mfe),
                "insert", "positions"
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_position(self, position_id: int) -> Optional[PositionRecord]:
        """Get a position by ID"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM positions WHERE id = ?",
                (position_id,),
                "select", "positions"
            )
            row = cursor.fetchone()
            return self._row_to_position(row) if row else None
    
    def get_positions_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                   end_date: Optional[datetime] = None) -> List[PositionRecord]:
        """Get positions for a specific instrument"""
        with self.get_connection() as conn:
            query = "SELECT * FROM positions WHERE instrument = ?"
            params = [instrument]
            
            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND end_time <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY start_time"
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params), "select", "positions"
            )
            return [self._row_to_position(row) for row in cursor.fetchall()]
    
    def get_positions_by_link_group(self, link_group_id: str) -> List[PositionRecord]:
        """Get positions by link group ID"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM positions WHERE link_group_id = ? ORDER BY start_time",
                (link_group_id,),
                "select", "positions"
            )
            return [self._row_to_position(row) for row in cursor.fetchall()]
    
    def update_position(self, position: PositionRecord) -> bool:
        """Update an existing position record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """UPDATE positions SET start_time = ?, end_time = ?, instrument = ?, 
                   side = ?, quantity = ?, entry_price = ?, exit_price = ?, 
                   realized_pnl = ?, commission = ?, link_group_id = ?, mae = ?, mfe = ? 
                   WHERE id = ?""",
                (position.start_time.isoformat() if position.start_time else None,
                 position.end_time.isoformat() if position.end_time else None,
                 position.instrument, position.side, position.quantity,
                 position.entry_price, position.exit_price, position.realized_pnl,
                 position.commission, position.link_group_id, position.mae, 
                 position.mfe, position.id),
                "update", "positions"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_position(self, position_id: int) -> bool:
        """Delete a position record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "DELETE FROM positions WHERE id = ?",
                (position_id,),
                "delete", "positions"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_positions(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[PositionRecord]:
        """Get all positions with optional pagination"""
        with self.get_connection() as conn:
            query = "SELECT * FROM positions ORDER BY start_time DESC"
            params = []
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
                
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params) if params else None, "select", "positions"
            )
            return [self._row_to_position(row) for row in cursor.fetchall()]
    
    def check_position_overlaps(self, instrument: str) -> List[Dict[str, Any]]:
        """Check for position overlaps for validation"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """SELECT p1.id as id1, p1.start_time as start1, p1.end_time as end1,
                          p2.id as id2, p2.start_time as start2, p2.end_time as end2
                   FROM positions p1, positions p2 
                   WHERE p1.instrument = ? AND p2.instrument = ? 
                   AND p1.id < p2.id
                   AND p1.start_time < p2.end_time AND p2.start_time < p1.end_time""",
                (instrument, instrument),
                "select", "positions"
            )
            
            overlaps = []
            for row in cursor.fetchall():
                overlaps.append({
                    'position1_id': row['id1'],
                    'position1_start': row['start1'],
                    'position1_end': row['end1'],
                    'position2_id': row['id2'],
                    'position2_start': row['start2'],
                    'position2_end': row['end2']
                })
            
            return overlaps

class SQLiteOHLCRepository(SQLiteRepository, IOHLCRepository):
    """SQLite implementation of OHLC repository"""
    
    def create_ohlc(self, ohlc: OHLCRecord) -> int:
        """Create a new OHLC record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """INSERT INTO ohlc_data (instrument, timestamp, open_price, high_price, 
                   low_price, close_price, volume) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ohlc.instrument, int(ohlc.timestamp.timestamp()) if ohlc.timestamp else None,
                 ohlc.open, ohlc.high, ohlc.low, ohlc.close, ohlc.volume),
                "insert", "ohlc_data"
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_ohlc_data(self, instrument: str, start_date: datetime, end_date: datetime, 
                      resolution: str = '1m') -> List[OHLCRecord]:
        """Get OHLC data for charting"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """SELECT * FROM ohlc_data 
                   WHERE instrument = ? AND timestamp >= ? AND timestamp <= ?
                   ORDER BY timestamp""",
                (instrument, int(start_date.timestamp()), int(end_date.timestamp())),
                "select", "ohlc_data"
            )
            return [self._row_to_ohlc(row) for row in cursor.fetchall()]
    
    def update_ohlc(self, ohlc: OHLCRecord) -> bool:
        """Update an existing OHLC record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """UPDATE ohlc_data SET instrument = ?, timestamp = ?, open_price = ?, 
                   high_price = ?, low_price = ?, close_price = ?, volume = ? WHERE id = ?""",
                (ohlc.instrument, int(ohlc.timestamp.timestamp()) if ohlc.timestamp else None,
                 ohlc.open, ohlc.high, ohlc.low, ohlc.close, ohlc.volume, ohlc.id),
                "update", "ohlc_data"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_ohlc(self, ohlc_id: int) -> bool:
        """Delete an OHLC record"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "DELETE FROM ohlc_data WHERE id = ?",
                (ohlc_id,),
                "delete", "ohlc_data"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_latest_ohlc(self, instrument: str) -> Optional[OHLCRecord]:
        """Get the latest OHLC record for an instrument"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM ohlc_data WHERE instrument = ? ORDER BY timestamp DESC LIMIT 1",
                (instrument,),
                "select", "ohlc_data"
            )
            row = cursor.fetchone()
            return self._row_to_ohlc(row) if row else None

class SQLiteSettingsRepository(SQLiteRepository, ISettingsRepository):
    """SQLite implementation of settings repository"""
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT value FROM chart_settings WHERE key = ?",
                (key,),
                "select", "chart_settings"
            )
            row = cursor.fetchone()
            if row:
                import json
                return json.loads(row['value'])
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        with self.get_connection() as conn:
            import json
            cursor = self._execute_with_monitoring(
                conn,
                "INSERT OR REPLACE INTO chart_settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
                "insert", "chart_settings"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT key, value FROM chart_settings",
                None,
                "select", "chart_settings"
            )
            settings = {}
            for row in cursor.fetchall():
                import json
                settings[row['key']] = json.loads(row['value'])
            return settings
    
    def delete_setting(self, key: str) -> bool:
        """Delete a setting"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "DELETE FROM chart_settings WHERE key = ?",
                (key,),
                "delete", "chart_settings"
            )
            conn.commit()
            return cursor.rowcount > 0

class SQLiteProfileRepository(SQLiteRepository, IProfileRepository):
    """SQLite implementation of profile repository"""
    
    def create_profile(self, profile_data: Dict[str, Any]) -> int:
        """Create a new profile"""
        with self.get_connection() as conn:
            import json
            cursor = self._execute_with_monitoring(
                conn,
                "INSERT INTO user_profiles (name, settings, created_at) VALUES (?, ?, ?)",
                (profile_data['name'], json.dumps(profile_data.get('settings', {})),
                 datetime.now().isoformat()),
                "insert", "user_profiles"
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a profile by ID"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM user_profiles WHERE id = ?",
                (profile_id,),
                "select", "user_profiles"
            )
            row = cursor.fetchone()
            if row:
                import json
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'settings': json.loads(row['settings']),
                    'created_at': row['created_at']
                }
            return None
    
    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by name"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM user_profiles WHERE name = ?",
                (name,),
                "select", "user_profiles"
            )
            row = cursor.fetchone()
            if row:
                import json
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'settings': json.loads(row['settings']),
                    'created_at': row['created_at']
                }
            return None
    
    def update_profile(self, profile_id: int, profile_data: Dict[str, Any]) -> bool:
        """Update a profile"""
        with self.get_connection() as conn:
            import json
            cursor = self._execute_with_monitoring(
                conn,
                "UPDATE user_profiles SET name = ?, settings = ? WHERE id = ?",
                (profile_data['name'], json.dumps(profile_data.get('settings', {})), profile_id),
                "update", "user_profiles"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_profile(self, profile_id: int) -> bool:
        """Delete a profile"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "DELETE FROM user_profiles WHERE id = ?",
                (profile_id,),
                "delete", "user_profiles"
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                "SELECT * FROM user_profiles ORDER BY created_at DESC",
                None,
                "select", "user_profiles"
            )
            profiles = []
            for row in cursor.fetchall():
                import json
                profiles.append({
                    'id': row['id'],
                    'name': row['name'],
                    'settings': json.loads(row['settings']),
                    'created_at': row['created_at']
                })
            return profiles

class SQLiteStatisticsRepository(SQLiteRepository, IStatisticsRepository):
    """SQLite implementation of statistics repository"""
    
    def get_performance_metrics(self, instrument: Optional[str] = None, 
                               start_date: Optional[datetime] = None, 
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get performance metrics"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    MAX(dollars_gain_loss) as max_win,
                    MIN(dollars_gain_loss) as max_loss
                FROM trades 
                WHERE deleted = 0
            """
            params = []
            
            if instrument:
                query += " AND instrument = ?"
                params.append(instrument)
            
            if start_date:
                query += " AND entry_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND entry_time <= ?"
                params.append(end_date.isoformat())
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params) if params else None, "select", "trades"
            )
            row = cursor.fetchone()
            
            if row:
                win_rate = (row['winning_trades'] / row['total_trades']) * 100 if row['total_trades'] > 0 else 0
                return {
                    'total_trades': row['total_trades'],
                    'winning_trades': row['winning_trades'],
                    'losing_trades': row['losing_trades'],
                    'win_rate': win_rate,
                    'total_pnl': row['total_pnl'] or 0,
                    'average_pnl': row['avg_pnl'] or 0,
                    'max_win': row['max_win'] or 0,
                    'max_loss': row['max_loss'] or 0
                }
            
            return {}
    
    def get_trade_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get trade statistics"""
        return self.get_performance_metrics(instrument)
    
    def get_position_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get position statistics"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_positions,
                    SUM(realized_pnl) as total_pnl,
                    AVG(realized_pnl) as avg_pnl
                FROM positions
            """
            params = []
            
            if instrument:
                query += " WHERE instrument = ?"
                params.append(instrument)
            
            cursor = self._execute_with_monitoring(
                conn, query, tuple(params) if params else None, "select", "positions"
            )
            row = cursor.fetchone()
            
            if row:
                win_rate = (row['winning_positions'] / row['total_positions']) * 100 if row['total_positions'] > 0 else 0
                return {
                    'total_positions': row['total_positions'],
                    'winning_positions': row['winning_positions'],
                    'win_rate': win_rate,
                    'total_pnl': row['total_pnl'] or 0,
                    'average_pnl': row['avg_pnl'] or 0
                }
            
            return {}
    
    def get_daily_pnl(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily P&L data"""
        with self.get_connection() as conn:
            cursor = self._execute_with_monitoring(
                conn,
                """SELECT DATE(entry_time) as date, SUM(dollars_gain_loss) as daily_pnl
                   FROM trades 
                   WHERE deleted = 0 AND entry_time >= ? AND entry_time <= ?
                   GROUP BY DATE(entry_time)
                   ORDER BY date""",
                (start_date.isoformat(), end_date.isoformat()),
                "select", "trades"
            )
            
            return [{'date': row['date'], 'pnl': row['daily_pnl']} for row in cursor.fetchall()]