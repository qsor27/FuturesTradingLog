"""
Statistics Calculation Service - Standardized calculations for dashboard accuracy
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Union
from scripts.TradingLog_db import FuturesDB

logger = logging.getLogger('statistics')

class StandardizedStatisticsCalculator:
    """
    Standardized statistics calculator that ensures consistent calculations
    across all dashboard components and resolves win rate inconsistencies.
    """
    
    @staticmethod
    def calculate_win_rate(trades_data: List[Dict[str, Any]], include_zero_pnl: bool = True) -> float:
        """
        Calculate win rate with consistent methodology
        
        Args:
            trades_data: List of trade dictionaries with 'dollars_gain_loss' field
            include_zero_pnl: Whether to include zero P&L trades in total count
            
        Returns:
            Win rate as percentage (0-100)
        """
        if not trades_data:
            return 0.0
            
        winning_trades = sum(1 for trade in trades_data if trade.get('dollars_gain_loss', 0) > 0)
        
        if include_zero_pnl:
            # Include all trades in denominator (recommended standard)
            total_trades = len(trades_data)
        else:
            # Exclude zero P&L trades from denominator (legacy behavior)
            total_trades = sum(1 for trade in trades_data if trade.get('dollars_gain_loss', 0) != 0)
        
        return (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    @staticmethod
    def calculate_basic_statistics(trades_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate basic trading statistics with standardized methodology
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Dictionary with standardized statistics
        """
        if not trades_data:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'zero_pnl_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'reward_risk_ratio': 0.0,
                'total_commission': 0.0
            }
        
        # Count trade types
        winning_trades = []
        losing_trades = []
        zero_pnl_trades = []
        
        for trade in trades_data:
            pnl = trade.get('dollars_gain_loss', 0)
            if pnl > 0:
                winning_trades.append(trade)
            elif pnl < 0:
                losing_trades.append(trade)
            else:
                zero_pnl_trades.append(trade)
        
        # Calculate metrics
        total_trades = len(trades_data)
        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        zero_count = len(zero_pnl_trades)
        
        # P&L calculations
        total_pnl = sum(trade.get('dollars_gain_loss', 0) for trade in trades_data)
        gross_profit = sum(trade.get('dollars_gain_loss', 0) for trade in winning_trades)
        gross_loss = abs(sum(trade.get('dollars_gain_loss', 0) for trade in losing_trades))
        total_commission = sum(trade.get('commission', 0) for trade in trades_data)
        
        # Average calculations
        avg_win = gross_profit / winning_count if winning_count > 0 else 0.0
        avg_loss = gross_loss / losing_count if losing_count > 0 else 0.0
        
        # Ratios
        win_rate = StandardizedStatisticsCalculator.calculate_win_rate(trades_data, include_zero_pnl=True)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        reward_risk_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_count,
            'losing_trades': losing_count,
            'zero_pnl_trades': zero_count,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'reward_risk_ratio': round(reward_risk_ratio, 2),
            'total_commission': round(total_commission, 2)
        }
    
    @staticmethod
    def get_standardized_overview_statistics(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get overview statistics using standardized calculation methods
        
        Args:
            account_filter: Optional list of accounts to filter by
            
        Returns:
            Standardized overview statistics
        """
        try:
            with FuturesDB() as db:
                # Build query with optional account filtering
                where_conditions = ["entry_time IS NOT NULL"]
                params = []
                
                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        dollars_gain_loss,
                        commission,
                        entry_time,
                        instrument,
                        account
                    FROM trades
                    WHERE {where_clause}
                """
                
                result = db._execute_with_monitoring(
                    query, 
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_data = [dict(row) for row in result.fetchall()]
                
                # Calculate standardized statistics
                stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
                
                # Add additional metadata
                stats.update({
                    'instruments_traded': len(set(trade.get('instrument') for trade in trades_data if trade.get('instrument'))),
                    'accounts_traded': len(set(trade.get('account') for trade in trades_data if trade.get('account'))),
                    'first_trade_date': min((trade.get('entry_time') for trade in trades_data if trade.get('entry_time')), default=None),
                    'last_trade_date': max((trade.get('entry_time') for trade in trades_data if trade.get('entry_time')), default=None),
                    'avg_trade_pnl': round(stats['total_pnl'] / stats['total_trades'], 2) if stats['total_trades'] > 0 else 0.0
                })
                
                return stats
                
        except Exception as e:
            logger.error(f"Error calculating standardized overview statistics: {e}")
            return {}
    
    @staticmethod
    def get_standardized_timeframe_statistics(
        timeframe: str = 'daily', 
        account_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get timeframe-based statistics using standardized calculation methods
        
        Args:
            timeframe: 'daily', 'weekly', or 'monthly'
            account_filter: Optional list of accounts to filter by
            
        Returns:
            List of standardized statistics grouped by timeframe
        """
        try:
            with FuturesDB() as db:
                # Define time grouping
                if timeframe == 'daily':
                    time_group = "strftime('%Y-%m-%d', entry_time)"
                    period_display = "strftime('%Y-%m-%d', entry_time)"
                elif timeframe == 'weekly':
                    time_group = "strftime('%Y-%W', entry_time)"
                    period_display = "strftime('%Y Week %W', entry_time)"
                elif timeframe == 'monthly':
                    time_group = "strftime('%Y-%m', entry_time)"
                    period_display = "strftime('%Y-%m', entry_time)"
                else:
                    raise ValueError(f"Invalid timeframe: {timeframe}")
                
                # Build query with optional account filtering
                where_conditions = ["entry_time IS NOT NULL"]
                params = []
                
                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        {time_group} as period,
                        {period_display} as period_display,
                        dollars_gain_loss,
                        commission,
                        instrument
                    FROM trades
                    WHERE {where_clause}
                    ORDER BY period DESC
                """
                
                result = db._execute_with_monitoring(
                    query,
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_by_period = {}
                for row in result.fetchall():
                    row_dict = dict(row)
                    period = row_dict['period']
                    if period not in trades_by_period:
                        trades_by_period[period] = {
                            'period': period,
                            'period_display': row_dict['period_display'],
                            'trades': []
                        }
                    trades_by_period[period]['trades'].append(row_dict)
                
                # Calculate statistics for each period
                period_stats = []
                for period_data in trades_by_period.values():
                    trades = period_data['trades']
                    stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades)
                    
                    # Add period information and template compatibility fields
                    stats.update({
                        'period': period_data['period'],
                        'period_display': period_data['period_display'],
                        'instruments_traded': list(set(trade.get('instrument') for trade in trades if trade.get('instrument'))),
                        # Template compatibility fields
                        'valid_trades': stats['total_trades'] - stats['zero_pnl_trades'],  # Non-zero trades
                        'valid_trade_percentage': (stats['total_trades'] - stats['zero_pnl_trades']) / stats['total_trades'] * 100 if stats['total_trades'] > 0 else 0.0,
                        'total_points_all_trades': 0.0,  # Would need instrument point values to calculate this
                        'net_profit': stats['total_pnl']
                    })
                    
                    period_stats.append(stats)
                
                return period_stats
                
        except Exception as e:
            logger.error(f"Error calculating standardized timeframe statistics: {e}")
            return []

def get_standardized_overview_statistics(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience function to get standardized overview statistics
    
    This function replaces the inconsistent calculations in get_overview_statistics()
    """
    return StandardizedStatisticsCalculator.get_standardized_overview_statistics(account_filter)

def get_standardized_timeframe_statistics(
    timeframe: str = 'daily', 
    account_filter: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to get standardized timeframe statistics
    
    This function replaces the inconsistent calculations in get_statistics()
    """
    return StandardizedStatisticsCalculator.get_standardized_timeframe_statistics(timeframe, account_filter)

class DashboardStatisticsIntegration:
    """
    Integration service to replace inconsistent database methods with standardized calculations
    """
    
    @staticmethod
    def get_overview_statistics_standardized(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Drop-in replacement for FuturesDB.get_overview_statistics() with standardized calculations
        """
        return StandardizedStatisticsCalculator.get_standardized_overview_statistics(account_filter)
    
    @staticmethod
    def get_statistics_standardized(
        timeframe: str = 'daily', 
        accounts: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Drop-in replacement for FuturesDB.get_statistics() with standardized calculations
        """
        return StandardizedStatisticsCalculator.get_standardized_timeframe_statistics(timeframe, accounts)
    
    @staticmethod
    def get_summary_statistics_standardized(
        account: Optional[str] = None,
        instrument: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drop-in replacement for FuturesDB.get_summary_statistics() with standardized calculations
        """
        try:
            with FuturesDB() as db:
                # Build WHERE clause based on filters
                where_conditions = ["entry_time IS NOT NULL"]
                params = []
                
                if account:
                    where_conditions.append("account = ?")
                    params.append(account)
                
                if instrument:
                    where_conditions.append("instrument = ?")
                    params.append(instrument)
                
                if start_date:
                    where_conditions.append("entry_time >= ?")
                    params.append(start_date)
                
                if end_date:
                    where_conditions.append("entry_time <= ?")
                    params.append(end_date)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        dollars_gain_loss,
                        commission,
                        entry_time,
                        instrument,
                        account
                    FROM trades
                    WHERE {where_clause}
                """
                
                result = db._execute_with_monitoring(
                    query, 
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_data = [dict(row) for row in result.fetchall()]
                
                # Use standardized calculations
                return StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
                
        except Exception as e:
            logger.error(f"Error in get_summary_statistics_standardized: {e}")
            return {}