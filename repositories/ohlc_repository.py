"""
OHLC repository for managing OHLC data operations
"""

import sqlite3
from typing import Dict, List, Any, Optional, Tuple
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class OHLCRepository(BaseRepository):
    """Repository for OHLC data operations"""
    
    def get_table_name(self) -> str:
        return 'ohlc_data'
    
    def insert_ohlc_data(self, instrument: str, timeframe: str, timestamp: int,
                        open_price: float, high_price: float, low_price: float,
                        close_price: float, volume: int = None) -> bool:
        """Insert a single OHLC record"""
        try:
            query = """
                INSERT OR REPLACE INTO ohlc_data 
                (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
            
            self._execute_with_monitoring(
                query, params,
                operation='insert',
                table=self.get_table_name()
            )
            
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to insert OHLC data for {instrument}: {e}")
            return False
    
    def insert_ohlc_batch(self, records: List[Dict[str, Any]]) -> bool:
        """Insert multiple OHLC records in a batch"""
        try:
            if not records:
                return True
            
            query = """
                INSERT OR REPLACE INTO ohlc_data 
                (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Convert records to tuples
            batch_data = []
            for record in records:
                batch_data.append((
                    record['instrument'],
                    record['timeframe'],
                    record['timestamp'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record.get('volume')
                ))
            
            self.cursor.executemany(query, batch_data)
            self.commit()
            
            db_logger.info(f"Successfully inserted {len(records)} OHLC records")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to insert OHLC batch: {e}")
            self.rollback()
            return False
    
    def get_ohlc_data(self, instrument: str, timeframe: str, 
                     start_timestamp: int = None, end_timestamp: int = None,
                     limit: int = None) -> List[Dict[str, Any]]:
        """Get OHLC data with optional filtering"""
        
        conditions = ["instrument = ?", "timeframe = ?"]
        params = [instrument, timeframe]
        
        if start_timestamp:
            conditions.append("timestamp >= ?")
            params.append(start_timestamp)
        
        if end_timestamp:
            conditions.append("timestamp <= ?")
            params.append(end_timestamp)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT * FROM ohlc_data 
            WHERE {where_clause}
            ORDER BY timestamp ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        return [dict(row) for row in result.fetchall()]
    
    def get_latest_timestamp(self, instrument: str, timeframe: str) -> Optional[int]:
        """Get the latest timestamp for an instrument/timeframe combination"""
        query = """
            SELECT MAX(timestamp) 
            FROM ohlc_data 
            WHERE instrument = ? AND timeframe = ?
        """
        
        result = self._execute_with_monitoring(
            query, (instrument, timeframe),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        return row[0] if row and row[0] else None
    
    def get_data_gaps(self, instrument: str, timeframe: str, 
                     expected_interval: int) -> List[Tuple[int, int]]:
        """Identify gaps in OHLC data based on expected interval"""
        query = """
            SELECT timestamp,
                   LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
            FROM ohlc_data 
            WHERE instrument = ? AND timeframe = ?
            ORDER BY timestamp
        """
        
        result = self._execute_with_monitoring(
            query, (instrument, timeframe),
            operation='select',
            table=self.get_table_name()
        )
        
        gaps = []
        for row in result.fetchall():
            current_ts, prev_ts = row[0], row[1]
            if prev_ts and (current_ts - prev_ts) > expected_interval:
                gaps.append((prev_ts, current_ts))
        
        return gaps
    
    def delete_ohlc_data(self, instrument: str, timeframe: str = None, 
                        start_timestamp: int = None, end_timestamp: int = None) -> bool:
        """Delete OHLC data with optional filtering"""
        try:
            conditions = ["instrument = ?"]
            params = [instrument]
            
            if timeframe:
                conditions.append("timeframe = ?")
                params.append(timeframe)
            
            if start_timestamp:
                conditions.append("timestamp >= ?")
                params.append(start_timestamp)
            
            if end_timestamp:
                conditions.append("timestamp <= ?")
                params.append(end_timestamp)
            
            where_clause = " AND ".join(conditions)
            
            query = f"DELETE FROM ohlc_data WHERE {where_clause}"
            
            result = self._execute_with_monitoring(
                query, tuple(params),
                operation='delete',
                table=self.get_table_name()
            )
            
            deleted_count = result.rowcount
            self.commit()
            
            db_logger.info(f"Deleted {deleted_count} OHLC records for {instrument}")
            return True
            
        except Exception as e:
            db_logger.error(f"Failed to delete OHLC data: {e}")
            self.rollback()
            return False
    
    def get_available_timeframes(self, instrument: str) -> List[str]:
        """Get all available timeframes for an instrument"""
        query = """
            SELECT DISTINCT timeframe 
            FROM ohlc_data 
            WHERE instrument = ?
            ORDER BY timeframe
        """
        
        result = self._execute_with_monitoring(
            query, (instrument,),
            operation='select',
            table=self.get_table_name()
        )
        
        return [row[0] for row in result.fetchall()]
    
    def get_available_instruments(self) -> List[str]:
        """Get all instruments with OHLC data"""
        query = """
            SELECT DISTINCT instrument 
            FROM ohlc_data 
            ORDER BY instrument
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        return [row[0] for row in result.fetchall()]
    
    def get_data_summary(self, instrument: str = None) -> List[Dict[str, Any]]:
        """Get summary of available OHLC data"""
        conditions = []
        params = []
        
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT instrument, timeframe,
                   COUNT(*) as record_count,
                   MIN(timestamp) as earliest_timestamp,
                   MAX(timestamp) as latest_timestamp
            FROM ohlc_data 
            {where_clause}
            GROUP BY instrument, timeframe
            ORDER BY instrument, timeframe
        """
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        return [dict(row) for row in result.fetchall()]