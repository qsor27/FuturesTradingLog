"""
Performance Service - Handle performance calculation logic for API endpoints
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from scripts.TradingLog_db import FuturesDB

logger = logging.getLogger('performance')

def get_week_start_end(current_date: date) -> tuple[date, date]:
    """Get the start (Monday) and end (Sunday) of the week for a given date"""
    # Monday is 0, Sunday is 6
    days_since_monday = current_date.weekday()
    week_start = current_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end

def calculate_daily_performance(target_date: date = None) -> Dict[str, Any]:
    """
    Calculate trading performance for a specific calendar day
    
    Args:
        target_date: Date to calculate performance for (defaults to today)
        
    Returns:
        Dictionary with daily performance metrics
    """
    if target_date is None:
        target_date = date.today()
    
    logger.debug(f"Calculating daily performance for {target_date}")
    
    try:
        with FuturesDB() as db:
            # Get all positions for the target date
            # Use position-based calculation as per technical spec
            query = """
            SELECT realized_pnl, status
            FROM positions 
            WHERE DATE(entry_time) = ? 
            AND status = 'closed'
            """
            
            results = db._execute_with_monitoring(
                query, 
                (target_date.strftime('%Y-%m-%d'),),
                operation="select",
                table="positions"
            ).fetchall()
            
            # Calculate metrics
            total_pnl = 0.0
            total_trades = len(results)
            winning_trades = 0
            losing_trades = 0
            
            for row in results:
                pnl = float(row['realized_pnl'] or 0.0)
                total_pnl += pnl
                
                if pnl > 0:
                    winning_trades += 1
                elif pnl < 0:
                    losing_trades += 1
            
            return {
                'daily_pnl': round(total_pnl, 2),
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'date': target_date.strftime('%Y-%m-%d')
            }
            
    except Exception as e:
        logger.error(f"Error calculating daily performance: {e}")
        raise

def calculate_weekly_performance(target_date: date = None) -> Dict[str, Any]:
    """
    Calculate trading performance for a calendar week (Monday to Sunday)
    
    Args:
        target_date: Date within the week to calculate performance for (defaults to today)
        
    Returns:
        Dictionary with weekly performance metrics
    """
    if target_date is None:
        target_date = date.today()
    
    week_start, week_end = get_week_start_end(target_date)
    logger.debug(f"Calculating weekly performance for week {week_start} to {week_end}")
    
    try:
        with FuturesDB() as db:
            # Get all positions for the target week
            # Use position-based calculation as per technical spec
            query = """
            SELECT realized_pnl, status
            FROM positions 
            WHERE DATE(entry_time) >= ? 
            AND DATE(entry_time) <= ?
            AND status = 'closed'
            """
            
            results = db._execute_with_monitoring(
                query, 
                (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')),
                operation="select",
                table="positions"
            ).fetchall()
            
            # Calculate metrics
            total_pnl = 0.0
            total_trades = len(results)
            winning_trades = 0
            losing_trades = 0
            
            for row in results:
                pnl = float(row['realized_pnl'] or 0.0)
                total_pnl += pnl
                
                if pnl > 0:
                    winning_trades += 1
                elif pnl < 0:
                    losing_trades += 1
            
            return {
                'weekly_pnl': round(total_pnl, 2),
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d')
            }
            
    except Exception as e:
        logger.error(f"Error calculating weekly performance: {e}")
        raise

def get_daily_performance() -> Dict[str, Any]:
    """Get current day performance with caching consideration"""
    return calculate_daily_performance()

def get_weekly_performance() -> Dict[str, Any]:
    """Get current week performance with caching consideration"""
    return calculate_weekly_performance()