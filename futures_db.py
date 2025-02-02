import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
from flask import current_app, g

class FuturesDB:
    def __init__(self):
        self.get_db()
        self._ensure_tables_exist()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_db()

    # ... [previous methods remain the same] ...

    def get_statistics(self, period: Optional[str] = None, accounts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Calculate trading statistics with optional period and account filtering"""
        db = self.get_db()
        
        # Base query with optional time filter
        base_query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                ROUND(SUM(dollars_gain_loss), 2) as total_pnl,
                ROUND(SUM(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss ELSE 0 END), 2) as gross_profits,
                ROUND(SUM(CASE WHEN dollars_gain_loss < 0 THEN dollars_gain_loss ELSE 0 END), 2) as gross_losses,
                ROUND(AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END), 2) as avg_winner,
                ROUND(AVG(CASE WHEN dollars_gain_loss < 0 THEN dollars_gain_loss END), 2) as avg_loser
            FROM trades
            WHERE 1=1
        """
        
        params = []
        
        # Add time period filter
        if period:
            if period == 'daily':
                base_query += " AND date(entry_time) = date('now')"
            elif period == 'weekly':
                base_query += " AND entry_time >= date('now', '-7 days')"
            elif period == 'monthly':
                base_query += " AND entry_time >= date('now', '-30 days')"
            
        # Add account filter
        if accounts and len(accounts) > 0:
            placeholders = ','.join('?' * len(accounts))
            base_query += f" AND account IN ({placeholders})"
            params.extend(accounts)
            
        results = db.execute(base_query, params).fetchone()
        
        # Calculate derived statistics
        stats = dict(results)
        if stats['total_trades'] > 0:
            stats['win_rate'] = round((stats['winning_trades'] / stats['total_trades']) * 100, 2)
        else:
            stats['win_rate'] = 0.0
            
        if stats['avg_loser'] and stats['avg_winner']:
            stats['profit_factor'] = round(abs(stats['avg_winner'] / stats['avg_loser']), 2)
        else:
            stats['profit_factor'] = 0.0
            
        return stats

    # ... [all other methods remain the same] ...