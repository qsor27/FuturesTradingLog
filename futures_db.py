import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
import os

class FuturesDB:
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish database connection when entering context"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Verify database structure
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        table_exists = self.cursor.fetchone() is not None
        
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
            return True
            
        except Exception as e:
            print(f"Error importing CSV: {e}")
            self.conn.rollback()
            return False

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
            
            self.cursor.execute(f"""
                SELECT instrument, timeframe, timestamp, open_price, high_price, 
                       low_price, close_price, volume
                FROM ohlc_data 
                WHERE {where_clause}
                ORDER BY timestamp ASC
                LIMIT ?
            """, params + [limit])
            
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
                gaps.append((start_timestamp, existing_timestamps[0] - expected_interval))
            
            # Check for gaps between existing data
            for i in range(len(existing_timestamps) - 1):
                current_ts = existing_timestamps[i]
                next_ts = existing_timestamps[i + 1]
                expected_next = current_ts + expected_interval
                
                if next_ts > expected_next:
                    gaps.append((expected_next, next_ts - expected_interval))
            
            # Check for gap at the end
            if existing_timestamps[-1] < end_timestamp:
                gaps.append((existing_timestamps[-1] + expected_interval, end_timestamp))
            
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
