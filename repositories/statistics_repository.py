"""
Statistics repository for managing all analytics and performance calculations
"""

import sqlite3
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class StatisticsRepository(BaseRepository):
    """Repository for statistical analysis and performance calculations"""
    
    def get_table_name(self) -> str:
        return 'trades'  # Statistics are primarily derived from trades
    
    def get_overview_statistics(self) -> Dict[str, Any]:
        """Get high-level overview statistics"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(dollars_gain_loss) as total_pnl,
                    MAX(dollars_gain_loss) as best_trade,
                    MIN(dollars_gain_loss) as worst_trade,
                    AVG(ABS(points_gain_loss)) as avg_points,
                    COUNT(DISTINCT instrument) as instruments_traded,
                    COUNT(DISTINCT account) as accounts_used
                FROM trades 
                WHERE deleted = 0
            """
            
            result = self._execute_with_monitoring(
                query,
                operation='select',
                table=self.get_table_name()
            )
            
            row = result.fetchone()
            if not row:
                return {}
            
            # Calculate additional metrics
            total_trades = row[0] or 0
            winning_trades = row[1] or 0
            losing_trades = row[2] or 0
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'avg_pnl': round(row[3] or 0, 2),
                'total_pnl': round(row[4] or 0, 2),
                'best_trade': round(row[5] or 0, 2),
                'worst_trade': round(row[6] or 0, 2),
                'avg_points': round(row[7] or 0, 2),
                'instruments_traded': row[8] or 0,
                'accounts_used': row[9] or 0
            }
            
        except Exception as e:
            db_logger.error(f"Failed to get overview statistics: {e}")
            return {}
    
    def get_performance_analysis(self, account: str = None, instrument: str = None,
                               start_date: str = None, end_date: str = None,
                               period: str = 'daily') -> List[Dict[str, Any]]:
        """Get performance analysis grouped by time period"""
        
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
        
        where_clause = " AND ".join(conditions)
        
        # Determine grouping based on period
        if period == 'daily':
            date_format = "date(entry_time)"
        elif period == 'weekly':
            date_format = "strftime('%Y-W%W', entry_time)"
        elif period == 'monthly':
            date_format = "strftime('%Y-%m', entry_time)"
        else:
            date_format = "date(entry_time)"
        
        query = f"""
            SELECT 
                {date_format} as period,
                COUNT(*) as total_trades,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(dollars_gain_loss) as total_pnl,
                AVG(dollars_gain_loss) as avg_pnl,
                MAX(dollars_gain_loss) as best_trade,
                MIN(dollars_gain_loss) as worst_trade,
                SUM(ABS(dollars_gain_loss)) as total_volume,
                AVG(ABS(points_gain_loss)) as avg_points
            FROM trades 
            WHERE {where_clause}
            GROUP BY {date_format}
            ORDER BY period DESC
        """
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        performance_data = []
        cumulative_pnl = 0
        
        for row in result.fetchall():
            total_trades = row[1]
            winning_trades = row[2]
            period_pnl = row[4] or 0
            cumulative_pnl += period_pnl
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            performance_data.append({
                'period': row[0],
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': row[3],
                'win_rate': round(win_rate, 2),
                'total_pnl': round(period_pnl, 2),
                'cumulative_pnl': round(cumulative_pnl, 2),
                'avg_pnl': round(row[5] or 0, 2),
                'best_trade': round(row[6] or 0, 2),
                'worst_trade': round(row[7] or 0, 2),
                'total_volume': round(row[8] or 0, 2),
                'avg_points': round(row[9] or 0, 2)
            })
        
        return list(reversed(performance_data))  # Return in chronological order
    
    def get_instrument_performance(self, account: str = None,
                                 start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Get performance analysis by instrument"""
        
        conditions = ["deleted = 0"]
        params = []
        
        if account:
            conditions.append("account = ?")
            params.append(account)
        
        if start_date:
            conditions.append("entry_time >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("entry_time <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                instrument,
                COUNT(*) as total_trades,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(dollars_gain_loss) as total_pnl,
                AVG(dollars_gain_loss) as avg_pnl,
                MAX(dollars_gain_loss) as best_trade,
                MIN(dollars_gain_loss) as worst_trade,
                AVG(ABS(points_gain_loss)) as avg_points,
                SUM(ABS(dollars_gain_loss)) as total_volume
            FROM trades 
            WHERE {where_clause}
            GROUP BY instrument
            ORDER BY total_pnl DESC
        """
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        instrument_data = []
        for row in result.fetchall():
            total_trades = row[1]
            winning_trades = row[2]
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            instrument_data.append({
                'instrument': row[0],
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': row[3],
                'win_rate': round(win_rate, 2),
                'total_pnl': round(row[4] or 0, 2),
                'avg_pnl': round(row[5] or 0, 2),
                'best_trade': round(row[6] or 0, 2),
                'worst_trade': round(row[7] or 0, 2),
                'avg_points': round(row[8] or 0, 2),
                'total_volume': round(row[9] or 0, 2)
            })
        
        return instrument_data
    
    def get_execution_quality_analysis(self, account: str = None, instrument: str = None,
                                     start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get execution quality metrics"""
        
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
        
        where_clause = " AND ".join(conditions)
        
        # Get basic execution metrics
        metrics_query = f"""
            SELECT 
                AVG(ABS(points_gain_loss)) as avg_points_per_trade,
                STDDEV(points_gain_loss) as points_volatility,
                AVG(dollars_gain_loss) as avg_dollars_per_trade,
                STDDEV(dollars_gain_loss) as dollars_volatility,
                COUNT(CASE WHEN side_of_market = 'Long' THEN 1 END) as long_trades,
                COUNT(CASE WHEN side_of_market = 'Short' THEN 1 END) as short_trades,
                AVG(CASE WHEN side_of_market = 'Long' THEN dollars_gain_loss END) as long_avg_pnl,
                AVG(CASE WHEN side_of_market = 'Short' THEN dollars_gain_loss END) as short_avg_pnl
            FROM trades 
            WHERE {where_clause}
        """
        
        result = self._execute_with_monitoring(
            metrics_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        
        return {
            'avg_points_per_trade': round(row[0] or 0, 2),
            'points_volatility': round(row[1] or 0, 2),
            'avg_dollars_per_trade': round(row[2] or 0, 2),
            'dollars_volatility': round(row[3] or 0, 2),
            'long_trades': row[4] or 0,
            'short_trades': row[5] or 0,
            'long_avg_pnl': round(row[6] or 0, 2),
            'short_avg_pnl': round(row[7] or 0, 2),
            'long_bias': round(((row[4] or 0) / ((row[4] or 0) + (row[5] or 0)) * 100), 2) if (row[4] or 0) + (row[5] or 0) > 0 else 0
        }
    
    def get_trade_distribution_analysis(self, account: str = None, instrument: str = None) -> Dict[str, Any]:
        """Get trade distribution and sizing analysis"""
        
        conditions = ["deleted = 0"]
        params = []
        
        if account:
            conditions.append("account = ?")
            params.append(account)
        
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        
        where_clause = " AND ".join(conditions)
        
        # Get P&L distribution
        distribution_query = f"""
            SELECT 
                COUNT(CASE WHEN dollars_gain_loss BETWEEN -50 AND 50 THEN 1 END) as small_trades,
                COUNT(CASE WHEN dollars_gain_loss BETWEEN 51 AND 200 THEN 1 END) as medium_wins,
                COUNT(CASE WHEN dollars_gain_loss BETWEEN -200 AND -51 THEN 1 END) as medium_losses,
                COUNT(CASE WHEN dollars_gain_loss > 200 THEN 1 END) as large_wins,
                COUNT(CASE WHEN dollars_gain_loss < -200 THEN 1 END) as large_losses,
                AVG(quantity) as avg_quantity,
                MAX(quantity) as max_quantity,
                MIN(quantity) as min_quantity
            FROM trades 
            WHERE {where_clause}
        """
        
        result = self._execute_with_monitoring(
            distribution_query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        
        return {
            'small_trades': row[0] or 0,
            'medium_wins': row[1] or 0,
            'medium_losses': row[2] or 0,
            'large_wins': row[3] or 0,
            'large_losses': row[4] or 0,
            'avg_quantity': round(row[5] or 0, 2),
            'max_quantity': row[6] or 0,
            'min_quantity': row[7] or 0
        }
    
    def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Get statistics for a linked trade group"""
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(dollars_gain_loss) as total_pnl,
                AVG(dollars_gain_loss) as avg_pnl,
                SUM(quantity) as total_quantity,
                MIN(entry_time) as first_trade,
                MAX(exit_time) as last_trade
            FROM trades 
            WHERE link_group_id = ? AND deleted = 0
        """
        
        result = self._execute_with_monitoring(
            query, (group_id,),
            operation='select',
            table=self.get_table_name()
        )
        
        row = result.fetchone()
        
        return {
            'total_trades': row[0] or 0,
            'total_pnl': round(row[1] or 0, 2),
            'avg_pnl': round(row[2] or 0, 2),
            'total_quantity': row[3] or 0,
            'first_trade': row[4],
            'last_trade': row[5]
        }
    
    def get_monthly_performance(self, account: str = None, year: int = None) -> List[Dict[str, Any]]:
        """Get monthly performance breakdown"""
        
        conditions = ["deleted = 0"]
        params = []
        
        if account:
            conditions.append("account = ?")
            params.append(account)
        
        if year:
            conditions.append("strftime('%Y', entry_time) = ?")
            params.append(str(year))
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                strftime('%Y-%m', entry_time) as month,
                COUNT(*) as total_trades,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(dollars_gain_loss) as total_pnl,
                AVG(dollars_gain_loss) as avg_pnl,
                MAX(dollars_gain_loss) as best_trade,
                MIN(dollars_gain_loss) as worst_trade
            FROM trades 
            WHERE {where_clause}
            GROUP BY strftime('%Y-%m', entry_time)
            ORDER BY month
        """
        
        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )
        
        monthly_data = []
        for row in result.fetchall():
            total_trades = row[1]
            winning_trades = row[2]
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            monthly_data.append({
                'month': row[0],
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(row[3] or 0, 2),
                'avg_pnl': round(row[4] or 0, 2),
                'best_trade': round(row[5] or 0, 2),
                'worst_trade': round(row[6] or 0, 2)
            })
        
        return monthly_data
    
    def get_available_years(self) -> List[int]:
        """Get all years with trade data"""
        query = """
            SELECT DISTINCT strftime('%Y', entry_time) as year
            FROM trades 
            WHERE deleted = 0 AND entry_time IS NOT NULL
            ORDER BY year DESC
        """
        
        result = self._execute_with_monitoring(
            query,
            operation='select',
            table=self.get_table_name()
        )
        
        return [int(row[0]) for row in result.fetchall() if row[0]]