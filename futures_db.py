import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
import os

class FuturesDB:
    def __init__(self, db_path: str = r'C:\TradingTest\backup\futures_trades.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish database connection when entering context"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Create trades table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                instrument TEXT,
                side_of_market TEXT,
                quantity INTEGER,
                entry_price REAL,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                exit_price REAL,
                points_gain_loss REAL,
                dollars_gain_loss REAL,
                commission REAL,
                account TEXT,
                chart_url TEXT,
                notes TEXT,
                validated BOOLEAN DEFAULT 0,
                reviewed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                link_group_id INTEGER
            )
        """)
        
        self.conn.commit()
        return self

    def update_trade_details(self, trade_id: int, chart_url: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update the notes and/or chart URL for a trade."""
        try:
            updates = []
            params = []
            
            if chart_url is not None:
                updates.append("chart_url = ?")
                params.append(chart_url)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if not updates:
                return True
            
            query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
            params.append(trade_id)
            
            self.cursor.execute(query, params)
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error updating trade details: {e}")
            self.conn.rollback()
            return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection when exiting context"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def get_unique_accounts(self) -> List[str]:
        """Get a list of all unique account names in the database."""
        try:
            self.cursor.execute("SELECT DISTINCT account FROM trades WHERE account IS NOT NULL ORDER BY account")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting unique accounts: {e}")
            return []

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Get a single trade by its ID."""
        try:
            self.cursor.execute("""
                SELECT * FROM trades
                WHERE id = ?
            """, (trade_id,))
            row = self.cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            print(f"Error getting trade by ID: {e}")
            return None

    def get_recent_trades(
        self, 
        page_size: int = 50, 
        page: int = 1, 
        sort_by: str = 'entry_time',
        sort_order: str = 'DESC',
        account: Optional[str] = None,
        trade_result: Optional[str] = None,
        side: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Get recent trades with pagination and filtering."""
        try:
            # Start building the query
            query = """
                SELECT *,
                    CASE 
                        WHEN dollars_gain_loss > 0 THEN 'win'
                        WHEN dollars_gain_loss < 0 THEN 'loss'
                        ELSE 'breakeven'
                    END as result
                FROM trades 
                WHERE 1=1
            """
            params = []

            # Add filters
            if account and isinstance(account, list) and account:
                placeholders = ','.join(['?' for _ in account])
                query += f" AND account IN ({placeholders})"
                params.extend(account)
            
            if trade_result:
                if trade_result == 'win':
                    query += " AND dollars_gain_loss > 0"
                elif trade_result == 'loss':
                    query += " AND dollars_gain_loss < 0"
                elif trade_result == 'breakeven':
                    query += " AND dollars_gain_loss = 0"

            if side:
                query += " AND side_of_market = ?"
                params.append(side)

            # Add sorting
            allowed_sort_fields = {'entry_time', 'exit_time', 'instrument', 'dollars_gain_loss', 'account'}
            sort_by = sort_by if sort_by in allowed_sort_fields else 'entry_time'
            sort_order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort_by} {sort_order}"

            # Get total count first
            count_query = f"SELECT COUNT(*) FROM ({query})"
            self.cursor.execute(count_query, params)
            total_count = self.cursor.fetchone()[0]

            # Calculate total pages
            total_pages = (total_count + page_size - 1) // page_size

            # Add pagination
            offset = (page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            # Execute final query
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            # Convert rows to dictionaries
            trades = []
            for row in rows:
                trade_dict = dict(row)
                trades.append(trade_dict)

            return trades, total_count, total_pages

        except Exception as e:
            print(f"Error getting recent trades: {e}")
            return [], 0, 0

    def get_statistics(self, timeframe: str = 'daily', accounts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get trading statistics grouped by the specified timeframe."""
        try:
            # Define the time grouping based on timeframe
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

            # Base query with account filtering
            query = f"""
                WITH period_stats AS (
                    SELECT 
                        {time_group} as period,
                        {period_display} as period_display,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) as valid_trades,
                        CAST(SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as valid_trade_percentage,
                        CAST(SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
                            NULLIF(COUNT(CASE WHEN dollars_gain_loss != 0 THEN 1 END), 0) * 100 as win_rate,
                        SUM(points_gain_loss) as total_points_all_trades,
                        SUM(dollars_gain_loss) as net_profit,
                        AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END) as avg_win,
                        AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END) as avg_loss,
                        CASE 
                            WHEN AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END) > 0
                            THEN ABS(AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END)) / 
                                AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END)
                            ELSE NULL
                        END as reward_risk_ratio,
                        SUM(commission) as total_commission,
                        GROUP_CONCAT(DISTINCT instrument) as instruments_traded
                    FROM trades
                    WHERE entry_time IS NOT NULL
                    {f"AND account IN ({','.join('?' * len(accounts))})" if accounts else ""}
                    GROUP BY period
                    ORDER BY period DESC
                )
                SELECT *
                FROM period_stats
            """

            # Execute query with account parameters if provided
            params = accounts if accounts else []
            self.cursor.execute(query, params)
            
            # Convert rows to dictionaries
            stats = []
            for row in self.cursor.fetchall():
                stat_dict = dict(row)
                
                # Handle any potential NULL values
                for key in stat_dict:
                    if stat_dict[key] is None:
                        if key in ['win_rate', 'valid_trade_percentage', 'reward_risk_ratio']:
                            stat_dict[key] = 0.0
                        elif key in ['total_points_all_trades', 'net_profit', 'avg_win', 'avg_loss']:
                            stat_dict[key] = 0.0
                
                stats.append(stat_dict)
            
            return stats

        except Exception as e:
            print(f"Error getting statistics: {e}")
            return []

    def link_trades(self, trade_ids: List[int]) -> Tuple[bool, Optional[int]]:
        """Link multiple trades together in a group."""
        try:
            # Get the next available group ID
            self.cursor.execute("SELECT MAX(link_group_id) FROM trades")
            result = self.cursor.fetchone()
            next_group_id = (result[0] or 0) + 1
            
            # Update all selected trades with the new group ID
            placeholders = ','.join('?' for _ in trade_ids)
            self.cursor.execute(f"""
                UPDATE trades 
                SET link_group_id = ? 
                WHERE id IN ({placeholders})
            """, [next_group_id] + trade_ids)
            
            self.conn.commit()
            return True, next_group_id
        except Exception as e:
            print(f"Error linking trades: {e}")
            self.conn.rollback()
            return False, None

    def unlink_trades(self, trade_ids: List[int]) -> bool:
        """Remove trades from their link group."""
        try:
            placeholders = ','.join('?' for _ in trade_ids)
            self.cursor.execute(f"""
                UPDATE trades 
                SET link_group_id = NULL 
                WHERE id IN ({placeholders})
            """, trade_ids)
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error unlinking trades: {e}")
            self.conn.rollback()
            return False

    def get_linked_trades(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all trades in a link group."""
        try:
            self.cursor.execute("""
                SELECT * FROM trades 
                WHERE link_group_id = ?
                ORDER BY entry_time
            """, (group_id,))
            
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting linked trades: {e}")
            return []

    def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Get statistics for a linked trade group."""
        try:
            self.cursor.execute("""
                SELECT 
                    SUM(dollars_gain_loss) as total_pnl,
                    SUM(commission) as total_commission,
                    COUNT(*) as trade_count
                FROM trades 
                WHERE link_group_id = ?
            """, (group_id,))
            
            result = self.cursor.fetchone()
            return {
                'total_pnl': result['total_pnl'] or 0,
                'total_commission': result['total_commission'] or 0,
                'trade_count': result['trade_count'] or 0
            }
        except Exception as e:
            print(f"Error getting group statistics: {e}")
            return {
                'total_pnl': 0,
                'total_commission': 0,
                'trade_count': 0
            }
