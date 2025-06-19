import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
import os
import logging

# Get database logger
db_logger = logging.getLogger('database')

class FuturesDB:
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish database connection when entering context"""
        try:
            db_logger.info(f"Connecting to database: {self.db_path}")
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Verify database structure
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            table_exists = self.cursor.fetchone() is not None
            
            if not table_exists:
                db_logger.info("Trades table does not exist, will be created")
            else:
                db_logger.debug("Database connection established successfully")
        except Exception as e:
            db_logger.error(f"Failed to connect to database: {e}")
            raise
        
        if not table_exists:
            print("Creating trades table...")
        else:
            print("Verifying trades table structure...")
            self.cursor.execute("PRAGMA table_info(trades)")
            columns = {row[1] for row in self.cursor.fetchall()}
            print(f"Existing columns: {columns}")
            
            # Add missing entry_execution_id column if it doesn't exist
            if 'entry_execution_id' not in columns:
                print("Adding missing entry_execution_id column...")
                self.cursor.execute("ALTER TABLE trades ADD COLUMN entry_execution_id TEXT")
                self.conn.commit()
                print("Added entry_execution_id column successfully")
        
        # Apply SQLite performance optimizations
        self.cursor.execute("PRAGMA journal_mode = WAL")
        self.cursor.execute("PRAGMA synchronous = normal")
        self.cursor.execute("PRAGMA temp_store = memory")
        self.cursor.execute("PRAGMA mmap_size = 1073741824")  # 1GB
        self.cursor.execute("PRAGMA cache_size = -64000")     # 64MB cache
        
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
                link_group_id INTEGER,
                entry_execution_id TEXT
            )
        """)
        
        # Create critical indexes for performance
        indexes = [
            ("idx_entry_time", "CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)"),
            ("idx_account", "CREATE INDEX IF NOT EXISTS idx_account ON trades(account)"),
            ("idx_dollars_gain_loss", "CREATE INDEX IF NOT EXISTS idx_dollars_gain_loss ON trades(dollars_gain_loss)"),
            ("idx_entry_execution_id", "CREATE INDEX IF NOT EXISTS idx_entry_execution_id ON trades(entry_execution_id, account)"),
            ("idx_link_group_id", "CREATE INDEX IF NOT EXISTS idx_link_group_id ON trades(link_group_id)"),
            ("idx_account_entry_time", "CREATE INDEX IF NOT EXISTS idx_account_entry_time ON trades(account, entry_time)"),
            ("idx_side_entry_time", "CREATE INDEX IF NOT EXISTS idx_side_entry_time ON trades(side_of_market, entry_time)"),
            ("idx_instrument", "CREATE INDEX IF NOT EXISTS idx_instrument ON trades(instrument)"),
            ("idx_exit_time", "CREATE INDEX IF NOT EXISTS idx_exit_time ON trades(exit_time)")
        ]
        
        for index_name, create_sql in indexes:
            try:
                self.cursor.execute(create_sql)
                print(f"Created/verified index: {index_name}")
            except Exception as e:
                print(f"Warning: Could not create index {index_name}: {e}")
        
        # Create OHLC data table for performance-first chart data
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlc_data (
                id INTEGER PRIMARY KEY,
                instrument TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(instrument, timeframe, timestamp)
            )
        """)
        
        # Create aggressive OHLC indexes for millisecond performance
        ohlc_indexes = [
            ("idx_ohlc_instrument_timeframe_timestamp", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_instrument_timeframe_timestamp ON ohlc_data(instrument, timeframe, timestamp)"),
            ("idx_ohlc_timestamp", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp ON ohlc_data(timestamp)"),
            ("idx_ohlc_instrument", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_instrument ON ohlc_data(instrument)"),
            ("idx_ohlc_timeframe", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe ON ohlc_data(timeframe)"),
            ("idx_ohlc_high_price", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_high_price ON ohlc_data(high_price)"),
            ("idx_ohlc_low_price", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_low_price ON ohlc_data(low_price)"),
            ("idx_ohlc_close_price", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_close_price ON ohlc_data(close_price)"),
            ("idx_ohlc_volume", 
             "CREATE INDEX IF NOT EXISTS idx_ohlc_volume ON ohlc_data(volume)")
        ]
        
        for index_name, create_sql in ohlc_indexes:
            try:
                self.cursor.execute(create_sql)
                print(f"Created/verified OHLC index: {index_name}")
            except Exception as e:
                print(f"Warning: Could not create OHLC index {index_name}: {e}")
        
        self.conn.commit()
        
        # Run ANALYZE to update query planner statistics
        self.cursor.execute("ANALYZE")
        self.conn.commit()
        
        return self

    def update_trade_details(self, trade_id: int, chart_url: Optional[str] = None, notes: Optional[str] = None, 
                           confirmed_valid: Optional[bool] = None, reviewed: Optional[bool] = None) -> bool:
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
                
            if confirmed_valid is not None:
                updates.append("validated = ?")
                params.append(confirmed_valid)
                
            if reviewed is not None:
                updates.append("reviewed = ?")
                params.append(reviewed)
            
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
        side: Optional[str] = None,
        cursor_id: Optional[int] = None,
        cursor_time: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int, int, Optional[int], Optional[str]]:
        """Get recent trades with cursor-based pagination and filtering."""
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

            # Add cursor-based pagination for better performance
            allowed_sort_fields = {'entry_time', 'exit_time', 'instrument', 'dollars_gain_loss', 'account'}
            sort_by = sort_by if sort_by in allowed_sort_fields else 'entry_time'
            sort_order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
            
            # Use cursor pagination if cursor values provided and not page 1
            if cursor_id and cursor_time and page > 1:
                if sort_order == 'DESC':
                    if sort_by == 'entry_time':
                        query += " AND (entry_time < ? OR (entry_time = ? AND id < ?))"
                        params.extend([cursor_time, cursor_time, cursor_id])
                    else:
                        query += f" AND ({sort_by} < ? OR ({sort_by} = ? AND id < ?))"
                        params.extend([cursor_time, cursor_time, cursor_id])  # cursor_time used as generic cursor value
                else:
                    if sort_by == 'entry_time':
                        query += " AND (entry_time > ? OR (entry_time = ? AND id > ?))"
                        params.extend([cursor_time, cursor_time, cursor_id])
                    else:
                        query += f" AND ({sort_by} > ? OR ({sort_by} = ? AND id > ?))"
                        params.extend([cursor_time, cursor_time, cursor_id])
            
            query += f" ORDER BY {sort_by} {sort_order}, id {sort_order}"

            # Get total count for pagination info (only when needed)
            if page == 1:
                count_query = f"""
                    SELECT COUNT(*) FROM trades 
                    WHERE 1=1
                    {f"AND account IN ({','.join('?' * len(account))})" if account and isinstance(account, list) and account else ""}
                    {" AND dollars_gain_loss > 0" if trade_result == 'win' else ""}
                    {" AND dollars_gain_loss < 0" if trade_result == 'loss' else ""}
                    {" AND dollars_gain_loss = 0" if trade_result == 'breakeven' else ""}
                    {" AND side_of_market = ?" if side else ""}
                """
                count_params = []
                if account and isinstance(account, list) and account:
                    count_params.extend(account)
                if side:
                    count_params.append(side)
                    
                self.cursor.execute(count_query, count_params)
                total_count = self.cursor.fetchone()[0]
                total_pages = (total_count + page_size - 1) // page_size
            else:
                # For subsequent pages, we don't need exact counts for performance
                total_count = -1  # Indicates unknown count
                total_pages = -1

            # Add limit for fetch
            query += " LIMIT ?"
            params.append(page_size + 1)  # Fetch one extra to determine if there are more pages

            # Execute final query
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            # Check if there are more pages
            has_more = len(rows) > page_size
            if has_more:
                rows = rows[:-1]  # Remove the extra row
            
            # Convert rows to dictionaries and get cursor values
            trades = []
            next_cursor_id = None
            next_cursor_time = None
            
            for row in rows:
                trade_dict = dict(row)
                trades.append(trade_dict)
            
            # Set cursor values for next page
            if trades and has_more:
                last_trade = trades[-1]
                next_cursor_id = last_trade['id']
                if sort_by == 'entry_time':
                    next_cursor_time = last_trade['entry_time']
                else:
                    next_cursor_time = str(last_trade[sort_by])  # Convert to string for generic handling

            return trades, total_count, total_pages, next_cursor_id, next_cursor_time

        except Exception as e:
            print(f"Error getting recent trades: {e}")
            return [], 0, 0, None, None

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
    
    def get_overview_statistics(self) -> Dict[str, Any]:
        """Get high-level overview statistics for dashboard."""
        try:
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_trade_pnl,
                    SUM(commission) as total_commission,
                    COUNT(DISTINCT instrument) as instruments_traded,
                    COUNT(DISTINCT account) as accounts_traded,
                    MIN(entry_time) as first_trade_date,
                    MAX(entry_time) as last_trade_date
                FROM trades
                WHERE entry_time IS NOT NULL
            """)
            
            row = self.cursor.fetchone()
            if not row:
                return {}
                
            stats = dict(row)
            
            # Calculate win rate
            total_trades = stats.get('total_trades', 0)
            winning_trades = stats.get('winning_trades', 0)
            stats['win_rate'] = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return stats
            
        except Exception as e:
            print(f"Error getting overview statistics: {e}")
            return {}
    
    def get_unique_accounts(self) -> List[str]:
        """Get list of unique account names."""
        try:
            self.cursor.execute("SELECT DISTINCT account FROM trades WHERE account IS NOT NULL ORDER BY account")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting unique accounts: {e}")
            return []
    
    def get_unique_instruments(self) -> List[str]:
        """Get list of unique instruments."""
        try:
            self.cursor.execute("SELECT DISTINCT instrument FROM trades WHERE instrument IS NOT NULL ORDER BY instrument")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting unique instruments: {e}")
            return []
    
    def get_date_range(self) -> Dict[str, str]:
        """Get date range of trades."""
        try:
            self.cursor.execute("""
                SELECT 
                    MIN(DATE(entry_time)) as min_date,
                    MAX(DATE(entry_time)) as max_date
                FROM trades 
                WHERE entry_time IS NOT NULL
            """)
            
            row = self.cursor.fetchone()
            if row and row[0] and row[1]:
                return {
                    'min_date': row[0],
                    'max_date': row[1]
                }
            return {}
            
        except Exception as e:
            print(f"Error getting date range: {e}")
            return {}
    
    def get_performance_analysis(self, account=None, instrument=None, start_date=None, end_date=None, period='daily') -> List[Dict[str, Any]]:
        """Get performance analysis data for historical reporting."""
        try:
            # Build WHERE clause
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if instrument:
                where_conditions.append("instrument = ?")
                params.append(instrument)
            
            if start_date:
                where_conditions.append("DATE(entry_time) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("DATE(entry_time) <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            # Determine date grouping based on period
            if period == 'weekly':
                date_group = "strftime('%Y-W%W', entry_time)"
                date_format = "strftime('%Y-W%W', entry_time)"
            elif period == 'monthly':
                date_group = "strftime('%Y-%m', entry_time)"
                date_format = "strftime('%Y-%m', entry_time)"
            else:  # daily
                date_group = "DATE(entry_time)"
                date_format = "DATE(entry_time)"
            
            query = f"""
                SELECT 
                    {date_format} as period,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losers,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(commission) as total_commission,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss ELSE 0 END) as gross_profit,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) ELSE 0 END) as gross_loss,
                    MAX(dollars_gain_loss) as best_trade,
                    MIN(dollars_gain_loss) as worst_trade,
                    COUNT(DISTINCT instrument) as instruments_count
                FROM trades
                WHERE {where_clause}
                GROUP BY {date_group}
                ORDER BY period DESC
            """
            
            self.cursor.execute(query, params)
            
            results = []
            running_pnl = 0
            
            for row in self.cursor.fetchall():
                data = dict(row)
                
                # Calculate additional metrics
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                
                # Calculate running P&L
                running_pnl += data.get('total_pnl', 0)
                data['cumulative_pnl'] = running_pnl
                
                # Calculate profit factor
                gross_profit = data.get('gross_profit', 0)
                gross_loss = data.get('gross_loss', 0)
                data['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0
                
                results.append(data)
            
            # Reverse to get chronological order
            return list(reversed(results))
            
        except Exception as e:
            print(f"Error getting performance analysis: {e}")
            return []
    
    def get_monthly_performance(self, account=None, year=None) -> List[Dict[str, Any]]:
        """Get monthly performance breakdown."""
        try:
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if year:
                where_conditions.append("strftime('%Y', entry_time) = ?")
                params.append(str(year))
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    strftime('%Y', entry_time) as year,
                    strftime('%m', entry_time) as month,
                    strftime('%Y-%m', entry_time) as period,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(commission) as total_commission,
                    MAX(dollars_gain_loss) as best_trade,
                    MIN(dollars_gain_loss) as worst_trade,
                    COUNT(DISTINCT instrument) as instruments_traded
                FROM trades
                WHERE {where_clause}
                GROUP BY strftime('%Y-%m', entry_time)
                ORDER BY period
            """
            
            self.cursor.execute(query, params)
            
            results = []
            for row in self.cursor.fetchall():
                data = dict(row)
                
                # Calculate win rate
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                
                # Add month name
                month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_num = int(data.get('month', 0))
                data['month_name'] = month_names[month_num] if 1 <= month_num <= 12 else ''
                
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"Error getting monthly performance: {e}")
            return []
    
    def get_instrument_performance(self, account=None, start_date=None, end_date=None) -> List[Dict[str, Any]]:
        """Get performance breakdown by instrument."""
        try:
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if start_date:
                where_conditions.append("DATE(entry_time) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("DATE(entry_time) <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    instrument,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losers,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(commission) as total_commission,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss ELSE 0 END) as gross_profit,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) ELSE 0 END) as gross_loss,
                    MAX(dollars_gain_loss) as best_trade,
                    MIN(dollars_gain_loss) as worst_trade,
                    SUM(quantity) as total_volume
                FROM trades
                WHERE {where_clause}
                GROUP BY instrument
                ORDER BY total_pnl DESC
            """
            
            self.cursor.execute(query, params)
            
            results = []
            for row in self.cursor.fetchall():
                data = dict(row)
                
                # Calculate additional metrics
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                
                # Calculate profit factor
                gross_profit = data.get('gross_profit', 0)
                gross_loss = data.get('gross_loss', 0)
                data['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0
                
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"Error getting instrument performance: {e}")
            return []
    
    def get_available_years(self) -> List[int]:
        """Get list of years with trade data."""
        try:
            self.cursor.execute("""
                SELECT DISTINCT strftime('%Y', entry_time) as year
                FROM trades 
                WHERE entry_time IS NOT NULL
                ORDER BY year DESC
            """)
            
            return [int(row[0]) for row in self.cursor.fetchall() if row[0]]
            
        except Exception as e:
            print(f"Error getting available years: {e}")
            return []
    
    def get_execution_quality_analysis(self, account=None, instrument=None, start_date=None, end_date=None) -> Dict[str, Any]:
        """Analyze execution quality and trading patterns."""
        try:
            # Build WHERE clause
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if instrument:
                where_conditions.append("instrument = ?")
                params.append(instrument)
            
            if start_date:
                where_conditions.append("DATE(entry_time) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("DATE(entry_time) <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            # Get execution timing analysis
            timing_query = f"""
                SELECT 
                    strftime('%H', entry_time) as hour,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners
                FROM trades
                WHERE {where_clause}
                GROUP BY strftime('%H', entry_time)
                ORDER BY hour
            """
            
            self.cursor.execute(timing_query, params)
            hourly_data = []
            for row in self.cursor.fetchall():
                data = dict(row)
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                hourly_data.append(data)
            
            # Get position size analysis
            size_query = f"""
                SELECT 
                    CASE 
                        WHEN quantity = 1 THEN '1 Contract'
                        WHEN quantity BETWEEN 2 AND 5 THEN '2-5 Contracts'
                        WHEN quantity BETWEEN 6 AND 10 THEN '6-10 Contracts'
                        ELSE '10+ Contracts'
                    END as size_range,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners
                FROM trades
                WHERE {where_clause}
                GROUP BY size_range
                ORDER BY MIN(quantity)
            """
            
            self.cursor.execute(size_query, params)
            size_data = []
            for row in self.cursor.fetchall():
                data = dict(row)
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                size_data.append(data)
            
            # Get hold time analysis
            hold_time_query = f"""
                SELECT 
                    CASE 
                        WHEN (julianday(exit_time) - julianday(entry_time)) * 24 * 60 < 5 THEN 'Under 5 min'
                        WHEN (julianday(exit_time) - julianday(entry_time)) * 24 * 60 < 30 THEN '5-30 min'
                        WHEN (julianday(exit_time) - julianday(entry_time)) * 24 < 1 THEN '30 min - 1 hour'
                        WHEN (julianday(exit_time) - julianday(entry_time)) < 1 THEN '1-24 hours'
                        ELSE '1+ days'
                    END as hold_time_range,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners,
                    AVG((julianday(exit_time) - julianday(entry_time)) * 24 * 60) as avg_hold_minutes
                FROM trades
                WHERE {where_clause} AND exit_time IS NOT NULL
                GROUP BY hold_time_range
                ORDER BY avg_hold_minutes
            """
            
            self.cursor.execute(hold_time_query, params)
            hold_time_data = []
            for row in self.cursor.fetchall():
                data = dict(row)
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                hold_time_data.append(data)
            
            # Get side bias analysis
            side_query = f"""
                SELECT 
                    side_of_market as side,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners
                FROM trades
                WHERE {where_clause}
                GROUP BY side_of_market
            """
            
            self.cursor.execute(side_query, params)
            side_data = []
            for row in self.cursor.fetchall():
                data = dict(row)
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                side_data.append(data)
            
            # Get streak analysis
            streak_query = f"""
                WITH streak_data AS (
                    SELECT 
                        dollars_gain_loss,
                        CASE WHEN dollars_gain_loss > 0 THEN 'W' ELSE 'L' END as result,
                        ROW_NUMBER() OVER (ORDER BY entry_time) as trade_num
                    FROM trades
                    WHERE {where_clause}
                )
                SELECT 
                    result,
                    COUNT(*) as occurrence_count,
                    AVG(dollars_gain_loss) as avg_pnl
                FROM streak_data
                GROUP BY result
            """
            
            self.cursor.execute(streak_query, params)
            streak_data = [dict(row) for row in self.cursor.fetchall()]
            
            return {
                'hourly_performance': hourly_data,
                'position_size_analysis': size_data,
                'hold_time_analysis': hold_time_data,
                'side_bias_analysis': side_data,
                'streak_analysis': streak_data
            }
            
        except Exception as e:
            print(f"Error getting execution quality analysis: {e}")
            return {}
    
    def get_trade_distribution_analysis(self, account=None, instrument=None) -> Dict[str, Any]:
        """Get trade size and timing distribution analysis."""
        try:
            # Build WHERE clause
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if instrument:
                where_conditions.append("instrument = ?")
                params.append(instrument)
            
            where_clause = " AND ".join(where_conditions)
            
            # Get quantity distribution
            quantity_query = f"""
                SELECT 
                    quantity,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl
                FROM trades
                WHERE {where_clause}
                GROUP BY quantity
                ORDER BY quantity
            """
            
            self.cursor.execute(quantity_query, params)
            quantity_distribution = [dict(row) for row in self.cursor.fetchall()]
            
            # Get day of week distribution
            dow_query = f"""
                SELECT 
                    CASE strftime('%w', entry_time)
                        WHEN '0' THEN 'Sunday'
                        WHEN '1' THEN 'Monday'
                        WHEN '2' THEN 'Tuesday'
                        WHEN '3' THEN 'Wednesday'
                        WHEN '4' THEN 'Thursday'
                        WHEN '5' THEN 'Friday'
                        WHEN '6' THEN 'Saturday'
                    END as day_of_week,
                    strftime('%w', entry_time) as day_num,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winners
                FROM trades
                WHERE {where_clause}
                GROUP BY strftime('%w', entry_time)
                ORDER BY day_num
            """
            
            self.cursor.execute(dow_query, params)
            dow_data = []
            for row in self.cursor.fetchall():
                data = dict(row)
                trade_count = data.get('trade_count', 0)
                winners = data.get('winners', 0)
                data['win_rate'] = (winners / trade_count * 100) if trade_count > 0 else 0
                dow_data.append(data)
            
            # Get P&L distribution ranges
            pnl_query = f"""
                SELECT 
                    CASE 
                        WHEN dollars_gain_loss < -500 THEN 'Large Loss (< -$500)'
                        WHEN dollars_gain_loss < -100 THEN 'Medium Loss (-$500 to -$100)'
                        WHEN dollars_gain_loss < 0 THEN 'Small Loss (-$100 to $0)'
                        WHEN dollars_gain_loss = 0 THEN 'Breakeven'
                        WHEN dollars_gain_loss <= 100 THEN 'Small Win ($0 to $100)'
                        WHEN dollars_gain_loss <= 500 THEN 'Medium Win ($100 to $500)'
                        ELSE 'Large Win (> $500)'
                    END as pnl_range,
                    COUNT(*) as trade_count,
                    SUM(dollars_gain_loss) as total_pnl,
                    MIN(dollars_gain_loss) as min_pnl,
                    MAX(dollars_gain_loss) as max_pnl
                FROM trades
                WHERE {where_clause}
                GROUP BY pnl_range
                ORDER BY MIN(dollars_gain_loss)
            """
            
            self.cursor.execute(pnl_query, params)
            pnl_distribution = [dict(row) for row in self.cursor.fetchall()]
            
            return {
                'quantity_distribution': quantity_distribution,
                'day_of_week_performance': dow_data,
                'pnl_distribution': pnl_distribution
            }
            
        except Exception as e:
            print(f"Error getting trade distribution analysis: {e}")
            return {}
    
    def get_performance_chart_data(self, account=None, instrument=None, start_date=None, end_date=None, period='daily') -> Dict[str, Any]:
        """Get chart data for performance visualization."""
        try:
            # Use existing performance analysis method
            performance_data = self.get_performance_analysis(account, instrument, start_date, end_date, period)
            
            if not performance_data:
                return {'labels': [], 'datasets': []}
            
            labels = [item['period'] for item in performance_data]
            cumulative_pnl = [item['cumulative_pnl'] for item in performance_data]
            daily_pnl = [item['total_pnl'] for item in performance_data]
            
            return {
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Cumulative P&L',
                        'data': cumulative_pnl,
                        'type': 'line',
                        'borderColor': 'rgb(59, 130, 246)',
                        'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                        'fill': True
                    },
                    {
                        'label': 'Period P&L',
                        'data': daily_pnl,
                        'type': 'bar',
                        'backgroundColor': 'rgba(34, 197, 94, 0.7)',
                        'borderColor': 'rgb(34, 197, 94)',
                        'borderWidth': 1
                    }
                ]
            }
            
        except Exception as e:
            print(f"Error getting performance chart data: {e}")
            return {'labels': [], 'datasets': []}
    
    def get_summary_statistics(self, account=None, instrument=None, start_date=None, end_date=None) -> Dict[str, Any]:
        """Get summary statistics for API endpoints."""
        try:
            # Build WHERE clause
            where_conditions = ["entry_time IS NOT NULL"]
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            if instrument:
                where_conditions.append("instrument = ?")
                params.append(instrument)
            
            if start_date:
                where_conditions.append("DATE(entry_time) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("DATE(entry_time) <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(dollars_gain_loss) as total_pnl,
                    AVG(dollars_gain_loss) as avg_pnl,
                    SUM(commission) as total_commission,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss ELSE 0 END) as gross_profit,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) ELSE 0 END) as gross_loss,
                    MAX(dollars_gain_loss) as best_trade,
                    MIN(dollars_gain_loss) as worst_trade,
                    COUNT(DISTINCT instrument) as instruments_traded,
                    COUNT(DISTINCT account) as accounts_traded
                FROM trades
                WHERE {where_clause}
            """
            
            self.cursor.execute(query, params)
            row = self.cursor.fetchone()
            
            if not row:
                return {}
            
            stats = dict(row)
            
            # Calculate additional metrics
            total_trades = stats.get('total_trades', 0)
            winning_trades = stats.get('winning_trades', 0)
            gross_profit = stats.get('gross_profit', 0)
            gross_loss = stats.get('gross_loss', 0)
            
            stats['win_rate'] = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            stats['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            return stats
            
        except Exception as e:
            print(f"Error getting summary statistics: {e}")
            return {}

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

    def delete_trades(self, trade_ids: List[int]) -> bool:
        """Delete multiple trades by their IDs."""
        try:
            # Create placeholders for the SQL query
            placeholders = ','.join('?' for _ in trade_ids)
            
            # Execute the delete query
            self.cursor.execute(f"""
                DELETE FROM trades 
                WHERE id IN ({placeholders})
            """, trade_ids)
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting trades: {e}")
            self.conn.rollback()
            return False

    def add_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Add a single trade to the database with duplicate checking."""
        try:
            # Check for duplicate using account + entry_execution_id
            self.cursor.execute("""
                SELECT COUNT(*) FROM trades
                WHERE account = ? AND entry_execution_id = ?
            """, (trade_data.get('account'), trade_data.get('entry_execution_id')))
            
            if self.cursor.fetchone()[0] > 0:
                print(f"Skipping duplicate trade: {trade_data.get('entry_execution_id')}")
                return True  # Return True to indicate it was processed (already exists)
            
            # Convert datetime objects to proper string format for SQLite
            if trade_data.get('entry_time') is not None:
                if hasattr(trade_data['entry_time'], 'strftime'):  # pandas Timestamp or datetime
                    trade_data['entry_time'] = trade_data['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(trade_data['entry_time'], str):
                    trade_data['entry_time'] = pd.to_datetime(trade_data['entry_time']).strftime('%Y-%m-%d %H:%M:%S')
            
            if trade_data.get('exit_time') is not None:
                if hasattr(trade_data['exit_time'], 'strftime'):  # pandas Timestamp or datetime
                    trade_data['exit_time'] = trade_data['exit_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(trade_data['exit_time'], str):
                    trade_data['exit_time'] = pd.to_datetime(trade_data['exit_time']).strftime('%Y-%m-%d %H:%M:%S')
            
            # Insert the trade
            self.cursor.execute("""
                INSERT INTO trades (
                    instrument, side_of_market, quantity, entry_price, entry_time,
                    exit_time, exit_price, points_gain_loss, dollars_gain_loss,
                    commission, account, entry_execution_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(trade_data.get('instrument', '')),
                str(trade_data.get('side_of_market', '')),
                int(trade_data.get('quantity', 0)),
                float(trade_data.get('entry_price', 0.0)),
                trade_data.get('entry_time'),
                trade_data.get('exit_time'),
                float(trade_data.get('exit_price', 0.0)),
                float(trade_data.get('points_gain_loss', 0.0)),
                float(trade_data.get('dollars_gain_loss', 0.0)),
                float(trade_data.get('commission', 0.0)),
                str(trade_data.get('account', '')),
                str(trade_data.get('entry_execution_id', ''))
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            import logging
            logger = logging.getLogger('database')
            logger.error(f"Error adding trade {trade_data.get('entry_execution_id', 'unknown')}: {e}")
            logger.error(f"Trade data: {trade_data}")
            print(f"Error adding trade: {e}")
            self.conn.rollback()
            return False

    def import_csv(self, csv_path: str) -> bool:
        """Import trades from a CSV file."""
        try:
            print(f"\nImporting trades from {csv_path}...")
            
            # Read CSV file using pandas
            df = pd.read_csv(csv_path)
            print(f"Read {len(df)} rows from CSV")
            print(f"CSV columns: {list(df.columns)}")


            # Define column name mappings
            column_mappings = {
                'Instrument': 'instrument',
                'Side of Market': 'side_of_market',
                'Quantity': 'quantity',
                'Entry Price': 'entry_price',
                'Entry Time': 'entry_time',
                'Exit Time': 'exit_time',
                'Exit Price': 'exit_price',
                'Result Gain/Loss in Points': 'points_gain_loss',
                'Gain/Loss in Dollars': 'dollars_gain_loss',
                'Commission': 'commission',
                'Account': 'account',
                'ID': 'entry_execution_id'  # Map the 'ID' column from CSV to 'entry_execution_id' in DB
            }
            
            # Rename columns based on mappings
            df = df.rename(columns=column_mappings)
            print(f"Columns after mapping: {list(df.columns)}")
            
            # Ensure required columns exist
            required_columns = {
                'instrument', 'side_of_market', 'quantity', 'entry_price',
                'entry_time', 'exit_time', 'exit_price', 'points_gain_loss',
                'dollars_gain_loss', 'commission', 'account', 'entry_execution_id'
            }
            
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                print(f"Missing required columns: {missing_columns}")
                print(f"Available columns: {df.columns}")
                return False

            # Convert datetime columns to ISO format strings
            for col in ['entry_time', 'exit_time']:
                df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

            # Convert to records and verify structure
            df = df.copy()  # Create an explicit copy
            records = [{
                'instrument': str(row['instrument']),
                'side_of_market': str(row['side_of_market']),
                'quantity': int(row['quantity']),
                'entry_price': float(row['entry_price']),
                'entry_time': str(row['entry_time']),
                'exit_time': str(row['exit_time']),
                'exit_price': float(row['exit_price']),
                'points_gain_loss': float(row['points_gain_loss']),
                'dollars_gain_loss': float(row['dollars_gain_loss']),
                'commission': float(row['commission']),
                'account': str(row['account']),
                'entry_execution_id': str(row['entry_execution_id'])
            } for _, row in df.iterrows()]
            
            if len(records) > 0:
                print("Sample record:")
                for key, value in records[0].items():
                    print(f"{key}: {value} (type: {type(value).__name__})")
            print(f"Processing {len(records)} trades...")
            
            trades_added = 0
            trades_skipped = 0

            for row in records:
                try:
                    # Debug: Print SQL parameters
                    print(f"SQL Parameters for duplicate check:")
                    print(f"Account: {str(row['account'])}")
                    print(f"Entry Execution ID: {str(row['entry_execution_id'])}")
                    
                    # Debug info
                    print(f"Processing record with keys: {list(row.keys())}")
                    
                    # Check for duplicate
                    account = str(row['account'])
                    exec_id = str(row['entry_execution_id'])
                    
                    # First verify columns exist
                    self.cursor.execute("PRAGMA table_info(trades)")
                    columns = {row[1] for row in self.cursor.fetchall()}
                    
                    if 'entry_execution_id' not in columns:
                        print("Error: entry_execution_id column not found in trades table!")
                        return False
                        
                    self.cursor.execute("""
                        SELECT COUNT(*) FROM trades
                        WHERE account = ? AND entry_execution_id = ?
                    """, (account, exec_id))
                    
                    count = self.cursor.fetchone()[0]
                    if count > 0:
                        trades_skipped += 1
                        print(f"Skipping duplicate trade: Entry={row['entry_time']}, ExecID={exec_id}, Account={account}")
                        continue
                except KeyError as e:
                    print(f"Error accessing columns: {e}")
                    print(f"Available columns: {list(row.index)}")
                    return False
                except Exception as e:
                    print(f"Error checking for duplicates: {str(e)}")
                    return False

                # Insert if not a duplicate
                self.cursor.execute("""
                    INSERT INTO trades (
                        instrument, side_of_market, quantity, entry_price,
                        entry_time, exit_time, exit_price, points_gain_loss,
                        dollars_gain_loss, commission, account, entry_execution_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['instrument'],
                    row['side_of_market'],
                    row['quantity'],
                    row['entry_price'],
                    row['entry_time'],
                    row['exit_time'],
                    row['exit_price'],
                    row['points_gain_loss'],
                    row['dollars_gain_loss'],
                    row['commission'],
                    row['account'],
                    str(row['entry_execution_id'])
                ))
                trades_added += 1
            
            self.conn.commit()
            print(f"Import complete: {trades_added} trades added, {trades_skipped} duplicates skipped")
            
            # Automatically rebuild positions after importing trades
            if trades_added > 0:
                print("Auto-generating positions from imported trades...")
                position_result = self._rebuild_positions_for_accounts()
                if position_result['positions_created'] > 0:
                    print(f"Generated {position_result['positions_created']} positions from {position_result['trades_processed']} trades")
                else:
                    print("No new positions generated")
            
            return True
            
        except Exception as e:
            print(f"Error importing CSV: {e}")
            self.conn.rollback()
            return False
            
    def _rebuild_positions_for_accounts(self) -> Dict[str, int]:
        """Rebuild positions for all accounts using the position service"""
        try:
            from position_service import PositionService
            
            # Use position service to rebuild positions
            with PositionService(db_path=self.db_path) as position_service:
                result = position_service.rebuild_positions_from_trades()
                return result
        except Exception as e:
            print(f"Error rebuilding positions: {e}")
            return {'positions_created': 0, 'trades_processed': 0}

    def explain_query(self, query: str, params: list = None) -> List[Dict[str, Any]]:
        """Analyze query performance using EXPLAIN QUERY PLAN."""
        try:
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            if params:
                self.cursor.execute(explain_query, params)
            else:
                self.cursor.execute(explain_query)
            
            results = []
            for row in self.cursor.fetchall():
                results.append(dict(row))
            
            return results
        except Exception as e:
            print(f"Error explaining query: {e}")
            return []

    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze database performance and provide recommendations."""
        try:
            performance_info = {}
            
            # Get table info
            self.cursor.execute("SELECT COUNT(*) as trade_count FROM trades")
            performance_info['total_trades'] = self.cursor.fetchone()[0]
            
            # Get index usage information
            self.cursor.execute("PRAGMA index_list(trades)")
            indexes = [dict(row) for row in self.cursor.fetchall()]
            performance_info['indexes'] = len(indexes)
            
            # Get database file size info
            self.cursor.execute("PRAGMA page_count")
            page_count = self.cursor.fetchone()[0]
            self.cursor.execute("PRAGMA page_size")
            page_size = self.cursor.fetchone()[0]
            performance_info['database_size_mb'] = (page_count * page_size) / (1024 * 1024)
            
            # Test query performance for common operations
            import time
            
            # Test pagination query
            start_time = time.time()
            self.cursor.execute("""
                SELECT * FROM trades 
                ORDER BY entry_time DESC 
                LIMIT 50
            """)
            self.cursor.fetchall()
            performance_info['pagination_query_ms'] = (time.time() - start_time) * 1000
            
            # Test filtered query
            start_time = time.time()
            self.cursor.execute("""
                SELECT * FROM trades 
                WHERE dollars_gain_loss > 0 
                ORDER BY entry_time DESC 
                LIMIT 50
            """)
            self.cursor.fetchall()
            performance_info['filtered_query_ms'] = (time.time() - start_time) * 1000
            
            return performance_info
            
        except Exception as e:
            print(f"Error analyzing performance: {e}")
            return {}

    def insert_ohlc_data(self, instrument: str, timeframe: str, timestamp: int, 
                        open_price: float, high_price: float, low_price: float, 
                        close_price: float, volume: int = None) -> bool:
        """Insert OHLC candle data with duplicate prevention."""
        try:
            # Validate required parameters
            if not instrument or not timeframe:
                return False
            
            # Validate timestamp is an integer
            if not isinstance(timestamp, int):
                return False
                
            # Validate prices are numeric
            for price in [open_price, high_price, low_price, close_price]:
                if not isinstance(price, (int, float)):
                    return False
            
            self.cursor.execute("""
                INSERT OR IGNORE INTO ohlc_data 
                (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting OHLC data: {e}")
            self.conn.rollback()
            return False

    def get_ohlc_data(self, instrument: str, timeframe: str, start_timestamp: int = None, 
                     end_timestamp: int = None, limit: int = 1000) -> List[Dict]:
        """Get OHLC data for charting with performance optimization."""
        try:
            where_conditions = ["instrument = ?", "timeframe = ?"]
            params = [instrument, timeframe]
            
            if start_timestamp:
                where_conditions.append("timestamp >= ?")
                params.append(start_timestamp)
            
            if end_timestamp:
                where_conditions.append("timestamp <= ?")
                params.append(end_timestamp)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT instrument, timeframe, timestamp, open_price, high_price, 
                       low_price, close_price, volume
                FROM ohlc_data 
                WHERE {where_clause}
                ORDER BY timestamp ASC
            """
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            
            self.cursor.execute(query, params)
            
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting OHLC data: {e}")
            return []

    def find_ohlc_gaps(self, instrument: str, timeframe: str, start_timestamp: int, 
                      end_timestamp: int) -> List[Tuple[int, int]]:
        """Find gaps in OHLC data for smart backfilling."""
        try:
            # Get all existing timestamps in range
            self.cursor.execute("""
                SELECT timestamp FROM ohlc_data 
                WHERE instrument = ? AND timeframe = ? 
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (instrument, timeframe, start_timestamp, end_timestamp))
            
            existing_timestamps = [row[0] for row in self.cursor.fetchall()]
            
            if not existing_timestamps:
                return [(start_timestamp, end_timestamp)]
            
            gaps = []
            expected_interval = self._get_timeframe_seconds(timeframe)
            
            # Check for gap at the beginning
            if existing_timestamps[0] > start_timestamp:
                gap_end = existing_timestamps[0] - expected_interval
                if gap_end > start_timestamp:
                    gaps.append((start_timestamp, gap_end))
            
            # Check for gaps between existing data
            for i in range(len(existing_timestamps) - 1):
                current_ts = existing_timestamps[i]
                next_ts = existing_timestamps[i + 1]
                expected_next = current_ts + expected_interval
                
                if next_ts > expected_next:
                    # Calculate gap end (last missing timestamp)
                    gap_end = next_ts - expected_interval
                    if gap_end >= expected_next:
                        gaps.append((expected_next, gap_end))
            
            # Check for gap at the end
            if existing_timestamps[-1] < end_timestamp:
                gap_start = existing_timestamps[-1] + expected_interval
                if gap_start < end_timestamp:
                    gaps.append((gap_start, end_timestamp))
            
            return gaps
        except Exception as e:
            print(f"Error finding OHLC gaps: {e}")
            return []

    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds for gap detection."""
        timeframe_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        return timeframe_map.get(timeframe, 60)

    def get_position_executions(self, trade_id: int) -> Dict[str, Any]:
        """Get detailed execution breakdown for a position with FIFO analysis."""
        try:
            # Get the base trade
            trade = self.get_trade_by_id(trade_id)
            if not trade:
                return None
            
            # For positions built from multiple executions, get all related trades
            # This includes trades with the same entry_execution_id prefix or in the same link group
            base_execution_id = trade['entry_execution_id'].split('_to_')[0] if '_to_' in trade['entry_execution_id'] else trade['entry_execution_id']
            
            # Find all related executions (same base entry ID)
            self.cursor.execute("""
                SELECT * FROM trades 
                WHERE entry_execution_id LIKE ? OR 
                      (link_group_id IS NOT NULL AND link_group_id = ?)
                ORDER BY entry_time, exit_time
            """, (f"{base_execution_id}%", trade.get('link_group_id')))
            
            related_trades = [dict(row) for row in self.cursor.fetchall()]
            
            # Analyze execution flow and FIFO matching
            execution_analysis = self._analyze_execution_flow(related_trades, trade)
            
            return {
                'primary_trade': trade,
                'related_executions': related_trades,
                'execution_analysis': execution_analysis,
                'position_summary': self._calculate_position_summary(related_trades)
            }
            
        except Exception as e:
            print(f"Error getting position executions: {e}")
            return None

    def _analyze_execution_flow(self, trades: List[Dict], primary_trade: Dict) -> Dict[str, Any]:
        """Analyze the execution flow and FIFO matching for visualization."""
        try:
            executions = []
            total_quantity = 0
            total_cost_basis = 0
            
            for trade in trades:
                # Entry execution
                entry_execution = {
                    'type': 'entry',
                    'timestamp': trade['entry_time'],
                    'price': trade['entry_price'],
                    'quantity': trade['quantity'],
                    'side': trade['side_of_market'],
                    'execution_id': trade['entry_execution_id'],
                    'cumulative_position': total_quantity + trade['quantity'],
                    'average_price': None  # Will calculate below
                }
                
                # Update position tracking
                total_quantity += trade['quantity']
                total_cost_basis += trade['entry_price'] * trade['quantity']
                entry_execution['average_price'] = total_cost_basis / total_quantity if total_quantity > 0 else 0
                
                executions.append(entry_execution)
                
                # Exit execution
                exit_execution = {
                    'type': 'exit',
                    'timestamp': trade['exit_time'],
                    'price': trade['exit_price'],
                    'quantity': trade['quantity'],
                    'side': 'Sell' if trade['side_of_market'] == 'Long' else 'Buy',
                    'execution_id': trade['entry_execution_id'],
                    'cumulative_position': total_quantity - trade['quantity'],
                    'realized_pnl': trade['dollars_gain_loss'],
                    'points_pnl': trade['points_gain_loss']
                }
                
                # Update position tracking for exit
                total_quantity -= trade['quantity']
                if total_quantity > 0:
                    total_cost_basis -= trade['entry_price'] * trade['quantity']
                else:
                    total_cost_basis = 0
                
                executions.append(exit_execution)
            
            # Sort all executions by timestamp
            executions.sort(key=lambda x: x['timestamp'])
            
            return {
                'executions': executions,
                'total_fills': len(executions),
                'entry_fills': len([e for e in executions if e['type'] == 'entry']),
                'exit_fills': len([e for e in executions if e['type'] == 'exit']),
                'position_lifecycle': self._determine_position_lifecycle(executions)
            }
            
        except Exception as e:
            print(f"Error analyzing execution flow: {e}")
            return {'executions': [], 'total_fills': 0, 'entry_fills': 0, 'exit_fills': 0}

    def _determine_position_lifecycle(self, executions: List[Dict]) -> str:
        """Determine the current state of the position lifecycle."""
        if not executions:
            return 'unknown'
        
        # Check if position is fully closed
        final_position = executions[-1].get('cumulative_position', 0)
        
        if final_position == 0:
            return 'closed'
        elif final_position > 0:
            return 'open_long'
        else:
            return 'open_short'

    def _calculate_position_summary(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate comprehensive position summary statistics."""
        try:
            if not trades:
                return {}
            
            total_pnl = sum(trade['dollars_gain_loss'] for trade in trades)
            total_commission = sum(trade['commission'] for trade in trades)
            total_points = sum(trade['points_gain_loss'] for trade in trades)
            total_quantity = sum(trade['quantity'] for trade in trades)
            
            # Calculate average prices
            avg_entry_price = sum(trade['entry_price'] * trade['quantity'] for trade in trades) / total_quantity if total_quantity > 0 else 0
            avg_exit_price = sum(trade['exit_price'] * trade['quantity'] for trade in trades) / total_quantity if total_quantity > 0 else 0
            
            # Position duration
            entry_times = [trade['entry_time'] for trade in trades]
            exit_times = [trade['exit_time'] for trade in trades]
            
            return {
                'total_pnl': total_pnl,
                'total_commission': total_commission,
                'total_points': total_points,
                'total_quantity': total_quantity,
                'average_entry_price': avg_entry_price,
                'average_exit_price': avg_exit_price,
                'net_pnl': total_pnl - total_commission,
                'first_entry': min(entry_times) if entry_times else None,
                'last_exit': max(exit_times) if exit_times else None,
                'number_of_fills': len(trades) * 2  # Each trade has entry and exit
            }
            
        except Exception as e:
            print(f"Error calculating position summary: {e}")
            return {}

    def get_linked_trades_with_stats(self, group_id: int) -> Dict[str, Any]:
        """Get linked trades with comprehensive statistics - replaces the buggy approach."""
        try:
            trades = self.get_linked_trades(group_id)
            stats = self.get_group_statistics(group_id)
            
            return {
                'trades': trades,
                'total_pnl': stats['total_pnl'],
                'total_commission': stats['total_commission'],
                'trade_count': stats['trade_count']
            }
        except Exception as e:
            print(f"Error getting linked trades with stats: {e}")
            return {'trades': [], 'total_pnl': 0, 'total_commission': 0, 'trade_count': 0}

    def get_ohlc_count(self, instrument: str = None, timeframe: str = None) -> int:
        """Get count of OHLC records for monitoring."""
        try:
            where_conditions = []
            params = []
            
            if instrument:
                where_conditions.append("instrument = ?")
                params.append(instrument)
            
            if timeframe:
                where_conditions.append("timeframe = ?")
                params.append(timeframe)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            self.cursor.execute(f"SELECT COUNT(*) FROM ohlc_data WHERE {where_clause}", params)
            return self.cursor.fetchone()[0]
        except Exception as e:
            print(f"Error getting OHLC count: {e}")
            return 0
    
    def migrate_instrument_names_to_base_symbols(self) -> Dict[str, int]:
        """Migrate OHLC data to use base instrument symbols for consistency.
        
        Converts instruments like 'MNQ SEP25' to 'MNQ' for normalized storage.
        Returns count of records migrated per instrument.
        """
        try:
            # Find instruments with expiration dates (contain spaces)
            self.cursor.execute("""
                SELECT DISTINCT instrument 
                FROM ohlc_data 
                WHERE instrument LIKE '% %'
            """)
            
            instruments_with_expiry = [row[0] for row in self.cursor.fetchall()]
            migration_results = {}
            
            for full_instrument in instruments_with_expiry:
                base_instrument = full_instrument.split()[0]  # Extract base symbol
                
                # Check if base symbol already has data
                self.cursor.execute("""
                    SELECT COUNT(*) FROM ohlc_data 
                    WHERE instrument = ?
                """, (base_instrument,))
                
                existing_count = self.cursor.fetchone()[0]
                
                if existing_count == 0:
                    # No conflicts - migrate all data to base symbol
                    self.cursor.execute("""
                        UPDATE ohlc_data 
                        SET instrument = ?
                        WHERE instrument = ?
                    """, (base_instrument, full_instrument))
                    
                    migration_results[f"{full_instrument} -> {base_instrument}"] = self.cursor.rowcount
                    
                else:
                    # Conflicts exist - copy unique records only
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO ohlc_data 
                        (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                        SELECT ?, timeframe, timestamp, open_price, high_price, low_price, close_price, volume
                        FROM ohlc_data 
                        WHERE instrument = ?
                    """, (base_instrument, full_instrument))
                    
                    copied_count = self.cursor.rowcount
                    
                    # Delete the original records
                    self.cursor.execute("DELETE FROM ohlc_data WHERE instrument = ?", (full_instrument,))
                    deleted_count = self.cursor.rowcount
                    
                    migration_results[f"{full_instrument} -> {base_instrument} (merged)"] = copied_count
            
            self.conn.commit()
            return migration_results
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error migrating instrument names: {e}")
            return {}
