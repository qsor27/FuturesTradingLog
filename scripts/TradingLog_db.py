import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
import os
import logging
import json

# Get database logger
db_logger = logging.getLogger('database')

# Global flag to prevent repeated initialization
_database_initialized = False

class FuturesDB:
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        self.conn = None
        self.cursor = None
    
    def _execute_with_monitoring(self, query: str, params: tuple = None, operation: str = "query", table: str = "unknown"):
        """Execute query with monitoring metrics collection"""
        import time
        
        start_time = time.time()
        
        try:
            if params:
                result = self.cursor.execute(query, params)
            else:
                result = self.cursor.execute(query)
            
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
    
    def _detect_table_from_query(self, query: str) -> str:
        """Detect the primary table being queried for monitoring purposes"""
        query_lower = query.lower().strip()
        
        if 'from trades' in query_lower or 'update trades' in query_lower or 'insert into trades' in query_lower:
            return 'trades'
        elif 'from ohlc_data' in query_lower or 'update ohlc_data' in query_lower or 'insert into ohlc_data' in query_lower:
            return 'ohlc_data'
        elif 'from positions' in query_lower or 'update positions' in query_lower or 'insert into positions' in query_lower:
            return 'positions'
        elif 'from chart_settings' in query_lower or 'update chart_settings' in query_lower:
            return 'chart_settings'
        elif 'from user_profiles' in query_lower or 'update user_profiles' in query_lower or 'insert into user_profiles' in query_lower:
            return 'user_profiles'
        elif 'from profile_history' in query_lower or 'update profile_history' in query_lower or 'insert into profile_history' in query_lower:
            return 'profile_history'
        else:
            return 'unknown'
    
    def _detect_operation_from_query(self, query: str) -> str:
        """Detect the operation type for monitoring purposes"""
        query_lower = query.lower().strip()
        
        if query_lower.startswith('select'):
            return 'select'
        elif query_lower.startswith('insert'):
            return 'insert'
        elif query_lower.startswith('update'):
            return 'update'
        elif query_lower.startswith('delete'):
            return 'delete'
        elif query_lower.startswith('pragma'):
            return 'pragma'
        else:
            return 'other'
    def __enter__(self):
        """Establish database connection when entering context"""
        global _database_initialized
        
        try:
            db_logger.debug(f"Connecting to database: {self.db_path}")
            # timeout=30.0 makes SQLite wait up to 30 seconds for locks instead of failing immediately
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Skip heavy initialization if already done
            if _database_initialized:
                db_logger.debug("Database already initialized, skipping setup")
                return self
            
            # Verify database structure
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            table_exists = self.cursor.fetchone() is not None
            
            if not table_exists:
                db_logger.info("Trades table does not exist, will be created")
            else:
                db_logger.info("Database connection established, performing initial setup")
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
        self.cursor.execute("PRAGMA busy_timeout = 30000")    # Wait up to 30 seconds for locks
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
                entry_execution_id TEXT,
                deleted BOOLEAN DEFAULT 0
            )
        """)
        
        # Add deleted column to existing tables (migration)
        try:
            self.cursor.execute("ALTER TABLE trades ADD COLUMN deleted BOOLEAN DEFAULT 0")
            print("Added 'deleted' column to trades table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("'deleted' column already exists in trades table")
            else:
                print(f"Warning: Could not add 'deleted' column: {e}")
        
        # Create UNIQUE constraint for deduplication (account + entry_execution_id)
        # This enables INSERT OR IGNORE to work properly
        try:
            self.cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_execution
                ON trades(account, entry_execution_id)
                WHERE entry_execution_id IS NOT NULL AND entry_execution_id != ''
            """)
            print("Created/verified unique index: idx_unique_execution")
        except Exception as e:
            print(f"Warning: Could not create unique execution index: {e}")

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
        
        # Create chart settings table for user preferences  
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chart_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                default_timeframe TEXT NOT NULL DEFAULT '1h',
                default_data_range TEXT NOT NULL DEFAULT '1week',
                volume_visibility BOOLEAN NOT NULL DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize default chart settings if table is empty
        self.cursor.execute("SELECT COUNT(*) FROM chart_settings")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute("""
                INSERT INTO chart_settings (id, default_timeframe, default_data_range, volume_visibility)
                VALUES (1, '1h', '1week', 1)
            """)
            print("Initialized default chart settings")
        
        # Create user_profiles table for Setting Profiles/Templates feature
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                profile_name TEXT NOT NULL,
                description TEXT,
                settings_snapshot TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(user_id, profile_name)
            )
        """)
        
        # Create indexes for user_profiles table
        profile_indexes = [
            ("idx_user_profiles_user_id", 
             "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)"),
            ("idx_user_profiles_user_id_profile_name", 
             "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id_profile_name ON user_profiles(user_id, profile_name)"),
            ("idx_user_profiles_is_default", 
             "CREATE INDEX IF NOT EXISTS idx_user_profiles_is_default ON user_profiles(user_id, is_default)"),
            ("idx_user_profiles_created_at", 
             "CREATE INDEX IF NOT EXISTS idx_user_profiles_created_at ON user_profiles(created_at)")
        ]
        
        for index_name, create_sql in profile_indexes:
            try:
                self.cursor.execute(create_sql)
                print(f"Created/verified user profile index: {index_name}")
            except Exception as e:
                print(f"Warning: Could not create user profile index {index_name}: {e}")
        
        # Add version column to user_profiles table (migration for version history)
        try:
            self.cursor.execute("ALTER TABLE user_profiles ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            print("Added 'version' column to user_profiles table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("'version' column already exists in user_profiles table")
            else:
                print(f"Warning: Could not add 'version' column: {e}")
        
        # Create profile_history table for Settings Version History feature
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                settings_snapshot TEXT NOT NULL,
                change_reason TEXT,
                archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles (id) ON DELETE CASCADE
            )
        """)
        
        # Create index for profile_history table
        try:
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_profile_history_profile_id_version_desc
                ON profile_history (user_profile_id, version DESC)
            """)
            print("Created/verified profile history index: idx_profile_history_profile_id_version_desc")
        except Exception as e:
            print(f"Warning: Could not create profile history index: {e}")

        # Create custom_fields table for position custom fields feature
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                field_type TEXT NOT NULL CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select')),
                description TEXT,
                is_required BOOLEAN NOT NULL DEFAULT 0,
                default_value TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                validation_rules TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created/verified custom_fields table")

        # Create position_custom_field_values table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_custom_field_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                custom_field_id INTEGER NOT NULL,
                field_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
                UNIQUE(position_id, custom_field_id)
            )
        """)
        print("Created/verified position_custom_field_values table")

        # Create custom_field_options table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_field_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                custom_field_id INTEGER NOT NULL,
                option_value TEXT NOT NULL,
                option_label TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
                UNIQUE(custom_field_id, option_value)
            )
        """)
        print("Created/verified custom_field_options table")

        # Create indexes for custom fields tables
        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom_fields_name ON custom_fields(name)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom_fields_is_active ON custom_fields(is_active)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_position_id ON position_custom_field_values(position_id)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_field_id ON position_custom_field_values(custom_field_id)")
            print("Created/verified custom fields indexes")
        except Exception as e:
            print(f"Warning: Could not create custom fields indexes: {e}")

        # Run ANALYZE to update query planner statistics
        self.cursor.execute("ANALYZE")
        self.conn.commit()

        # Run pending database migrations
        try:
            db_logger.info("Checking for pending database migrations...")
            from scripts.migrations.migration_runner import MigrationRunner

            migration_runner = MigrationRunner(self.db_path)
            successful, failed = migration_runner.run_pending_migrations()

            if failed > 0:
                db_logger.warning(f"Some migrations failed: {failed} failed, {successful} succeeded")
            elif successful > 0:
                db_logger.info(f"Successfully applied {successful} migration(s)")
            else:
                db_logger.debug("No pending migrations")

        except Exception as e:
            db_logger.error(f"Error running migrations: {e}", exc_info=True)
            print(f"[WARNING] Migration check failed: {e}")
            # Don't fail the entire initialization if migrations fail

        # Mark database as initialized to prevent repeated setup
        _database_initialized = True
        db_logger.info("Database initialization completed successfully")

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

    def update_trade_core_fields(self, trade_id: int, side_of_market: Optional[str] = None,
                                  quantity: Optional[int] = None, entry_price: Optional[float] = None,
                                  exit_price: Optional[float] = None) -> bool:
        """Update core trade fields (side_of_market, quantity, entry_price, exit_price).

        These are critical fields that affect position calculations. After updating,
        positions should be rebuilt for the affected account/instrument.
        """
        try:
            updates = []
            params = []

            if side_of_market is not None:
                # Validate side_of_market value
                valid_sides = ['Buy', 'Sell', 'BuyToCover', 'SellShort', 'Long', 'Short']
                if side_of_market not in valid_sides:
                    db_logger.error(f"Invalid side_of_market value: {side_of_market}")
                    return False
                updates.append("side_of_market = ?")
                params.append(side_of_market)

            if quantity is not None:
                if quantity <= 0:
                    db_logger.error(f"Invalid quantity value: {quantity}")
                    return False
                updates.append("quantity = ?")
                params.append(quantity)

            if entry_price is not None:
                updates.append("entry_price = ?")
                params.append(entry_price)

            if exit_price is not None:
                updates.append("exit_price = ?")
                params.append(exit_price)

            if not updates:
                return True

            query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
            params.append(trade_id)

            self.cursor.execute(query, params)
            self.conn.commit()

            db_logger.info(f"Updated core fields for trade {trade_id}: {updates}")
            return True

        except Exception as e:
            db_logger.error(f"Error updating trade core fields: {e}")
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

    def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute a raw SQL query and return results"""
        try:
            if params:
                result = self._execute_with_monitoring(query, params)
            else:
                result = self._execute_with_monitoring(query)
            return result.fetchall()
        except Exception as e:
            db_logger.error(f"Error executing query: {e}")
            db_logger.debug(f"Query: {query}")
            db_logger.debug(f"Params: {params}")
            return []

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
                ORDER BY id
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
                    commission, account, entry_execution_id, trade_validation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(trade_data.get('instrument', '')),
                str(trade_data.get('side_of_market', '')),
                int(trade_data.get('quantity', 0)),
                float(trade_data.get('entry_price', 0.0)) if trade_data.get('entry_price') is not None else None,
                trade_data.get('entry_time'),
                trade_data.get('exit_time'),
                float(trade_data.get('exit_price')) if trade_data.get('exit_price') is not None else None,
                float(trade_data.get('points_gain_loss')) if trade_data.get('points_gain_loss') is not None else None,
                float(trade_data.get('dollars_gain_loss')) if trade_data.get('dollars_gain_loss') is not None else None,
                float(trade_data.get('commission', 0.0)),
                str(trade_data.get('account', '')),
                str(trade_data.get('entry_execution_id', '')),
                trade_data.get('trade_validation', None)  # Add validation field
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
    
    def import_raw_executions(self, csv_path: str) -> bool:
        """Import raw NinjaTrader executions directly as individual execution records
        Supports both basic (15 fields) and enhanced (23 fields) CSV formats from NinjaScript indicator
        """
        try:
            print(f"\nImporting raw executions from {csv_path}...")
            
            # Read CSV file using pandas with robust error handling
            try:
                df = pd.read_csv(csv_path, 
                               encoding='utf-8-sig',  # Handle BOM characters
                               on_bad_lines='skip',    # Skip malformed lines
                               skipinitialspace=True)  # Handle extra spaces
            except Exception as e:
                try:
                    # Fallback: use Python engine for more robust parsing
                    df = pd.read_csv(csv_path,
                                   encoding='utf-8-sig', 
                                   engine='python',
                                   on_bad_lines='skip')
                except Exception as e2:
                    print(f"Error reading CSV file: {e2}")
                    return False
            
            print(f"Read {len(df)} raw executions from CSV")
            
            # Clean up column names and data
            df.columns = df.columns.str.strip()  # Remove whitespace from column names
            
            # Remove empty columns (caused by trailing commas)
            df = df.dropna(axis=1, how='all')
            
            # Detect CSV format based on column count
            num_cols = len(df.columns)
            print(f"Detected CSV format: {num_cols} columns")
            
            # Validate we have the minimum required columns for basic format
            required_basic_cols = ['Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'E/X', 'Position', 'Order ID', 'Name', 'Commission', 'Rate', 'Account', 'Connection']
            
            # Check if we have all required basic columns
            missing_cols = [col for col in required_basic_cols if col not in df.columns]
            if missing_cols:
                print(f"Error: Missing required columns: {missing_cols}")
                return False
            
            print(f"CSV format validated - basic columns present")
            if num_cols > 15:
                print(f"Enhanced format detected with {num_cols - 14} additional fields")
            
            # Convert timestamps
            df['Time'] = pd.to_datetime(df['Time'])
            
            executions_added = 0
            executions_skipped = 0
            
            for _, execution in df.iterrows():
                try:
                    # Clean up data
                    instrument = str(execution['Instrument']).strip()
                    action = str(execution['Action']).strip()
                    quantity = int(execution['Quantity'])
                    price = float(execution['Price'])
                    timestamp = execution['Time'].strftime('%Y-%m-%d %H:%M:%S')
                    exec_id = str(execution['ID']).strip()
                    entry_exit = str(execution['E/X']).strip()
                    position = str(execution['Position']).strip()
                    account = str(execution['Account']).strip()
                    commission = float(str(execution['Commission']).replace('$', ''))
                    
                    # Check for existing execution ID (including soft-deleted)
                    self.cursor.execute("""
                        SELECT id, deleted FROM trades
                        WHERE entry_execution_id = ? AND account = ?
                        LIMIT 1
                    """, (exec_id, account))
                    
                    existing_record = self.cursor.fetchone()
                    if existing_record:
                        trade_id, is_deleted = existing_record
                        if is_deleted:
                            # Re-activate soft-deleted trade by updating it
                            print(f"Re-activating previously deleted execution: {exec_id}")
                            self.cursor.execute("""
                                UPDATE trades SET 
                                    deleted = 0,
                                    side_of_market = ?,
                                    entry_price = ?,
                                    exit_price = ?,
                                    entry_time = ?,
                                    exit_time = ?,
                                    commission = ?
                                WHERE id = ?
                            """, (side_of_market, price, price, timestamp, timestamp, commission, trade_id))
                            executions_added += 1
                            continue
                        else:
                            # Active duplicate - skip
                            executions_skipped += 1
                            print(f"Skipping active duplicate execution: {exec_id}")
                            continue
                    
                    # Determine side of market based on Action field only
                    # The E/X field from NinjaScript is unreliable (all marked as "Entry")
                    # Use Action to determine the direction of the quantity change
                    if action in ['Buy', 'BuyToCover']:
                        side_of_market = 'Long'  # Positive quantity change
                    elif action in ['Sell', 'SellShort']:
                        side_of_market = 'Short'  # Negative quantity change
                    else:
                        # Fallback for unknown action types
                        side_of_market = 'Long' if 'Buy' in action else 'Short'
                    
                    # Insert as individual execution (not completed trade)
                    self.cursor.execute("""
                        INSERT INTO trades (
                            instrument, side_of_market, quantity, entry_price,
                            entry_time, exit_time, exit_price, points_gain_loss,
                            dollars_gain_loss, commission, account, entry_execution_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        instrument,
                        side_of_market,
                        quantity,
                        price,  # Use execution price as entry price
                        timestamp,
                        timestamp,  # Same time for exit
                        price,  # Same price for exit
                        0,  # No P&L for individual executions
                        0,  # No P&L for individual executions
                        commission,
                        account,
                        exec_id
                    ))
                    
                    executions_added += 1
                    
                except Exception as e:
                    print(f"Error processing execution {execution.get('ID', 'Unknown')}: {e}")
                    continue
            
            self.conn.commit()
            print(f"Import complete: {executions_added} executions added, {executions_skipped} duplicates skipped")
            
            return True
            
        except Exception as e:
            print(f"Error importing raw executions: {e}")
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
        """Insert OHLC candle data with duplicate prevention and monitoring."""
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
            
            # Use monitoring wrapper for database operation
            self._execute_with_monitoring("""
                INSERT OR IGNORE INTO ohlc_data 
                (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume),
            operation="insert", table="ohlc_data")
            
            self.conn.commit()
            
            # Record business metric for OHLC data points
            try:
                from app import record_ohlc_data_points
                record_ohlc_data_points(instrument, timeframe, 1)
            except ImportError:
                pass
            
            return True
        except Exception as e:
            print(f"Error inserting OHLC data: {e}")
            self.conn.rollback()
            return False

    def insert_ohlc_batch(self, records: list) -> bool:
        """
        Bulk inserts OHLC data records. Uses INSERT OR IGNORE to prevent duplicates,
        making the operation safe to re-run.
        """
        if not records:
            return True
            
        try:
            # Validate record structure
            for record in records:
                required_fields = ['timestamp', 'instrument', 'timeframe', 'open', 'high', 'low', 'close']
                if not all(field in record for field in required_fields):
                    raise ValueError(f"Record missing required fields: {required_fields}")
            
            # Prepare bulk insert query with conflict handling
            query = """
            INSERT OR IGNORE INTO ohlc_data 
            (timestamp, instrument, timeframe, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Convert records to tuples for executemany
            data_tuples = []
            for record in records:
                data_tuples.append((
                    record['timestamp'],
                    record['instrument'],
                    record['timeframe'],
                    record['open'],
                    record['high'],
                    record['low'],
                    record['close'],
                    record.get('volume', 0)  # Default to 0 if volume not provided
                ))
            
            # Execute bulk insert
            self.cursor.executemany(query, data_tuples)
            self.conn.commit()
            
            # Record metrics for monitoring
            try:
                from app import record_ohlc_data_points
                for record in records:
                    record_ohlc_data_points(record['instrument'], record['timeframe'], 1)
            except ImportError:
                pass
            
            self.logger.info(f"Bulk inserted {len(records)} OHLC records")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during bulk OHLC insert: {e}")
            self.conn.rollback()
            return False


    def _get_intelligent_limit(self, timeframe: str, duration_days: int = None) -> Optional[int]:
        """Calculate intelligent query limits based on timeframe and duration"""
        # Resolution-aware limits to prevent memory issues while allowing large ranges
        timeframe_limits = {
            '1m': 2000,    # ~1.4 days of 1-minute data
            '3m': 4000,    # ~8.3 days of 3-minute data
            '5m': 6000,    # ~20.8 days of 5-minute data
            '15m': 8000,   # ~83 days of 15-minute data
            '1h': 10000,   # ~417 days of hourly data
            '4h': 12000,   # ~5.5 years of 4-hour data
            '1d': 15000    # ~41 years of daily data
        }
        
        base_limit = timeframe_limits.get(timeframe, 1000)
        
        # For very large ranges with low-res timeframes, allow more data
        if duration_days and duration_days > 90:  # > 3 months
            if timeframe in ['1d', '4h']:
                return None  # No limit for daily/4h data on large ranges
            elif timeframe == '1h':
                return base_limit * 2  # Double limit for hourly
        
        return base_limit

    def get_ohlc_data(self, instrument: str, timeframe: str, start_timestamp: int = None, 
                     end_timestamp: int = None, limit: int = None) -> List[Dict]:
        """Get OHLC data for charting with performance optimization and monitoring."""
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
            
            # Use intelligent limit if not explicitly provided
            if limit is None:
                duration_days = None
                if start_timestamp and end_timestamp:
                    duration_days = (end_timestamp - start_timestamp) / (24 * 3600)
                limit = self._get_intelligent_limit(timeframe, duration_days)
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            
            # Use monitoring wrapper for database operation
            self._execute_with_monitoring(query, params, operation="select", table="ohlc_data")
            
            result = [dict(row) for row in self.cursor.fetchall()]
            
            # Record business metric for chart requests
            try:
                from app import record_chart_request
                record_chart_request(instrument, timeframe)
            except ImportError:
                pass
            
            return result
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

    def get_latest_ohlc_timestamp(self, instrument: str, timeframe: str) -> Optional[int]:
        """Get the latest timestamp for a given instrument and timeframe."""
        try:
            self.cursor.execute("""
                SELECT MAX(timestamp) FROM ohlc_data
                WHERE instrument = ? AND timeframe = ?
            """, (instrument, timeframe))

            result = self.cursor.fetchone()
            return result[0] if result and result[0] else None

        except Exception as e:
            print(f"Error getting latest OHLC timestamp: {e}")
            return None

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
                ORDER BY id
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

    def get_position_execution_pairs(self, position_id: int, instrument_multiplier: float = 2.0) -> Dict[str, Any]:
        """
        Get FIFO-matched execution pairs for a position with per-pair P&L.

        For a position with multiple entries/exits, this matches them using FIFO
        (First-In-First-Out) to calculate P&L for each entry/exit pair.

        Args:
            position_id: The position ID to analyze
            instrument_multiplier: Dollar value per point (default $2 for MNQ)

        Returns:
            Dictionary with execution_pairs list and summary statistics
        """
        try:
            # Get position details
            self.cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
            position = self.cursor.fetchone()
            if not position:
                return {'success': False, 'error': 'Position not found'}

            position = dict(position)
            is_long = position['position_type'] == 'Long'

            # Get all executions for this position
            self.cursor.execute("""
                SELECT t.*, pe.execution_order
                FROM trades t
                JOIN position_executions pe ON t.id = pe.trade_id
                WHERE pe.position_id = ?
                ORDER BY t.entry_time, pe.execution_order
            """, (position_id,))

            trades = [dict(row) for row in self.cursor.fetchall()]

            if not trades:
                return {'success': False, 'error': 'No executions found'}

            # Separate into entries and exits based on position type
            # For Long: Buy = entry, Sell = exit
            # For Short: Sell = entry, Buy = exit
            entry_queue = []  # List of (price, quantity, time, trade_id, commission)
            exit_queue = []   # List of (price, quantity, time, trade_id, commission)

            for trade in trades:
                side = trade['side_of_market']
                qty = trade['quantity']
                commission = trade['commission'] or 0

                if is_long:
                    if side == 'Buy' and trade['entry_price']:
                        # Entry for long position
                        entry_queue.append({
                            'price': trade['entry_price'],
                            'quantity': qty,
                            'time': trade['entry_time'],
                            'trade_id': trade['id'],
                            'commission': commission
                        })
                    elif side == 'Sell' and trade['exit_price']:
                        # Exit for long position
                        exit_queue.append({
                            'price': trade['exit_price'],
                            'quantity': qty,
                            'time': trade['entry_time'],  # exit time stored in entry_time for sell trades
                            'trade_id': trade['id'],
                            'commission': commission
                        })
                else:  # Short position
                    if side == 'Sell' and trade['entry_price']:
                        # Entry for short position
                        entry_queue.append({
                            'price': trade['entry_price'],
                            'quantity': qty,
                            'time': trade['entry_time'],
                            'trade_id': trade['id'],
                            'commission': commission
                        })
                    elif side == 'Buy' and trade['exit_price']:
                        # Exit for short position
                        exit_queue.append({
                            'price': trade['exit_price'],
                            'quantity': qty,
                            'time': trade['entry_time'],
                            'trade_id': trade['id'],
                            'commission': commission
                        })

            # FIFO matching: pair entries with exits
            execution_pairs = []
            pair_number = 0

            # Expand entries and exits to individual units for FIFO matching
            entry_units = []
            for entry in entry_queue:
                for _ in range(entry['quantity']):
                    entry_units.append({
                        'price': entry['price'],
                        'time': entry['time'],
                        'trade_id': entry['trade_id'],
                        'commission': entry['commission'] / entry['quantity']  # Split commission per unit
                    })

            exit_units = []
            for exit in exit_queue:
                for _ in range(exit['quantity']):
                    exit_units.append({
                        'price': exit['price'],
                        'time': exit['time'],
                        'trade_id': exit['trade_id'],
                        'commission': exit['commission'] / exit['quantity']
                    })

            # Match entry units with exit units (FIFO)
            for i, exit_unit in enumerate(exit_units):
                if i < len(entry_units):
                    entry_unit = entry_units[i]
                    pair_number += 1

                    # Calculate P&L for this pair
                    if is_long:
                        points_pnl = exit_unit['price'] - entry_unit['price']
                    else:
                        points_pnl = entry_unit['price'] - exit_unit['price']

                    dollars_pnl = points_pnl * instrument_multiplier
                    total_commission = entry_unit['commission'] + exit_unit['commission']

                    # Calculate duration
                    from datetime import datetime
                    try:
                        entry_dt = datetime.strptime(entry_unit['time'], '%Y-%m-%d %H:%M:%S')
                        exit_dt = datetime.strptime(exit_unit['time'], '%Y-%m-%d %H:%M:%S')
                        duration_seconds = (exit_dt - entry_dt).total_seconds()

                        # Format duration display
                        if duration_seconds < 60:
                            duration_display = f"{int(duration_seconds)}s"
                        elif duration_seconds < 3600:
                            duration_display = f"{int(duration_seconds // 60)}m"
                        elif duration_seconds < 86400:
                            hours = int(duration_seconds // 3600)
                            mins = int((duration_seconds % 3600) // 60)
                            duration_display = f"{hours}h {mins}m"
                        else:
                            days = int(duration_seconds // 86400)
                            hours = int((duration_seconds % 86400) // 3600)
                            duration_display = f"{days}d {hours}h"
                    except:
                        duration_seconds = 0
                        duration_display = "-"

                    execution_pairs.append({
                        'pair_number': pair_number,
                        'entry_time': entry_unit['time'],
                        'exit_time': exit_unit['time'],
                        'entry_price': entry_unit['price'],
                        'exit_price': exit_unit['price'],
                        'quantity': 1,
                        'duration_seconds': duration_seconds,
                        'duration_display': duration_display,
                        'points_pnl': points_pnl,
                        'dollars_pnl': dollars_pnl,
                        'entry_commission': entry_unit['commission'],
                        'exit_commission': exit_unit['commission'],
                        'total_commission': total_commission,
                        'net_pnl': dollars_pnl - total_commission
                    })

            # Calculate summary statistics
            total_pairs = len(execution_pairs)
            winning_pairs = len([p for p in execution_pairs if p['dollars_pnl'] > 0])
            losing_pairs = len([p for p in execution_pairs if p['dollars_pnl'] < 0])
            breakeven_pairs = total_pairs - winning_pairs - losing_pairs

            total_points_pnl = sum(p['points_pnl'] for p in execution_pairs)
            total_dollars_pnl = sum(p['dollars_pnl'] for p in execution_pairs)
            total_commission = sum(p['total_commission'] for p in execution_pairs)

            return {
                'success': True,
                'position_id': position_id,
                'instrument': position['instrument'],
                'position_type': position['position_type'],
                'execution_pairs': execution_pairs,
                'summary': {
                    'total_pairs': total_pairs,
                    'total_quantity': total_pairs,  # Each pair is 1 unit
                    'winning_pairs': winning_pairs,
                    'losing_pairs': losing_pairs,
                    'breakeven_pairs': breakeven_pairs,
                    'win_rate': (winning_pairs / total_pairs * 100) if total_pairs > 0 else 0,
                    'total_points_pnl': total_points_pnl,
                    'total_dollars_pnl': total_dollars_pnl,
                    'total_commission': total_commission,
                    'net_pnl': total_dollars_pnl - total_commission
                }
            }

        except Exception as e:
            db_logger.error(f"Error getting position execution pairs: {e}")
            return {'success': False, 'error': str(e)}

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

    def get_active_instruments_since(self, since_date: datetime) -> List[str]:
        """Get list of instruments that have trade activity since the given date"""
        try:
            # Convert datetime to string for SQLite
            since_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
            
            self.cursor.execute("""
                SELECT DISTINCT instrument 
                FROM trades 
                WHERE entry_time >= ? 
                   OR exit_time >= ?
                ORDER BY instrument
            """, (since_str, since_str))
            
            instruments = [row[0] for row in self.cursor.fetchall()]
            return instruments
            
        except Exception as e:
            print(f"Error getting active instruments: {e}")
            return []

    def get_chart_settings(self) -> Dict[str, Any]:
        """Get chart settings with fallback to defaults"""
        try:
            self.cursor.execute("""
                SELECT default_timeframe, default_data_range, volume_visibility, last_updated
                FROM chart_settings 
                WHERE id = 1
            """)
            row = self.cursor.fetchone()
            
            if row:
                return {
                    'default_timeframe': row[0],
                    'default_data_range': row[1], 
                    'volume_visibility': bool(row[2]),
                    'last_updated': row[3]
                }
            else:
                # Return system defaults if no settings found
                return {
                    'default_timeframe': '1h',
                    'default_data_range': '1week',
                    'volume_visibility': True,
                    'last_updated': None
                }
                
        except Exception as e:
            db_logger.error(f"Error getting chart settings: {e}")
            # Return system defaults on error
            return {
                'default_timeframe': '1h',
                'default_data_range': '1week', 
                'volume_visibility': True,
                'last_updated': None
            }

    def update_chart_settings(self, default_timeframe: str = None, default_data_range: str = None, 
                            volume_visibility: bool = None) -> bool:
        """Update chart settings"""
        try:
            # Validate timeframe options
            valid_timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
            if default_timeframe and default_timeframe not in valid_timeframes:
                raise ValueError(f"Invalid timeframe: {default_timeframe}. Must be one of {valid_timeframes}")
            
            # Validate data range options
            valid_ranges = ['1day', '3days', '1week', '2weeks', '1month', '3months', '6months']
            if default_data_range and default_data_range not in valid_ranges:
                raise ValueError(f"Invalid data range: {default_data_range}. Must be one of {valid_ranges}")
            
            # Build update query dynamically
            updates = []
            params = []
            
            if default_timeframe is not None:
                updates.append("default_timeframe = ?")
                params.append(default_timeframe)
            
            if default_data_range is not None:
                updates.append("default_data_range = ?")
                params.append(default_data_range)
            
            if volume_visibility is not None:
                updates.append("volume_visibility = ?")
                params.append(volume_visibility)
            
            if not updates:
                return True  # Nothing to update
            
            updates.append("last_updated = CURRENT_TIMESTAMP")
            
            # Use INSERT OR REPLACE to handle first-time settings
            if len(params) == 0:
                return True
                
            query = f"""
                INSERT OR REPLACE INTO chart_settings (id, default_timeframe, default_data_range, volume_visibility, last_updated)
                VALUES (1, 
                    COALESCE(?, (SELECT default_timeframe FROM chart_settings WHERE id = 1), '1h'),
                    COALESCE(?, (SELECT default_data_range FROM chart_settings WHERE id = 1), '1week'), 
                    COALESCE(?, (SELECT volume_visibility FROM chart_settings WHERE id = 1), 1),
                    CURRENT_TIMESTAMP
                )
            """
            
            # Pad params to match query parameters
            while len(params) < 3:
                params.append(None)
            
            self.cursor.execute(query, params)
            self.conn.commit()
            
            db_logger.info(f"Updated chart settings: timeframe={default_timeframe}, range={default_data_range}, volume={volume_visibility}")
            return True
            
        except Exception as e:
            db_logger.error(f"Error updating chart settings: {e}")
            self.conn.rollback()
            return False
    
    # User Profile Methods for Setting Profiles/Templates feature
    
    def get_user_profiles(self, user_id: int = 1) -> List[Dict[str, Any]]:
        """Get all user profiles for a specific user"""
        try:
            self.cursor.execute("""
                SELECT id, user_id, profile_name, description, settings_snapshot, 
                       is_default, created_at, updated_at, version
                FROM user_profiles
                WHERE user_id = ?
                ORDER BY is_default DESC, profile_name ASC
            """, (user_id,))
            
            profiles = []
            for row in self.cursor.fetchall():
                profiles.append({
                    'id': row[0],
                    'user_id': row[1],
                    'profile_name': row[2],
                    'description': row[3],
                    'settings_snapshot': json.loads(row[4]) if row[4] else {},
                    'is_default': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                    'version': row[8] if row[8] is not None else 1
                })
            
            return profiles
            
        except Exception as e:
            db_logger.error(f"Error getting user profiles: {e}")
            return []
    
    def get_user_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific user profile by ID"""
        try:
            self.cursor.execute("""
                SELECT id, user_id, profile_name, description, settings_snapshot, 
                       is_default, created_at, updated_at, version
                FROM user_profiles
                WHERE id = ?
            """, (profile_id,))
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'profile_name': row[2],
                    'description': row[3],
                    'settings_snapshot': json.loads(row[4]) if row[4] else {},
                    'is_default': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                    'version': row[8] if row[8] is not None else 1
                }
            return None
            
        except Exception as e:
            db_logger.error(f"Error getting user profile: {e}")
            return None
    
    def get_user_profile_by_name(self, profile_name: str, user_id: int = 1) -> Optional[Dict[str, Any]]:
        """Get a specific user profile by name"""
        try:
            self.cursor.execute("""
                SELECT id, user_id, profile_name, description, settings_snapshot, 
                       is_default, created_at, updated_at, version
                FROM user_profiles
                WHERE user_id = ? AND profile_name = ?
            """, (user_id, profile_name))
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'profile_name': row[2],
                    'description': row[3],
                    'settings_snapshot': json.loads(row[4]) if row[4] else {},
                    'is_default': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                    'version': row[8] if row[8] is not None else 1
                }
            return None
            
        except Exception as e:
            db_logger.error(f"Error getting user profile by name: {e}")
            return None
    
    def create_user_profile(self, profile_name: str, settings_snapshot: Dict[str, Any], 
                           description: str = None, is_default: bool = False, 
                           user_id: int = 1) -> Optional[int]:
        """Create a new user profile"""
        try:
            # If this is being set as default, unset any existing default
            if is_default:
                self.cursor.execute("""
                    UPDATE user_profiles 
                    SET is_default = 0 
                    WHERE user_id = ? AND is_default = 1
                """, (user_id,))
            
            # Insert new profile
            self.cursor.execute("""
                INSERT INTO user_profiles (user_id, profile_name, description, settings_snapshot, is_default)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, profile_name, description, json.dumps(settings_snapshot), is_default))
            
            profile_id = self.cursor.lastrowid
            self.conn.commit()
            
            db_logger.info(f"Created user profile: {profile_name} (ID: {profile_id})")
            return profile_id
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                db_logger.error(f"Profile name '{profile_name}' already exists for user {user_id}")
                return None
            else:
                db_logger.error(f"Error creating user profile: {e}")
                self.conn.rollback()
                return None
        except Exception as e:
            db_logger.error(f"Error creating user profile: {e}")
            self.conn.rollback()
            return None
    
    def update_user_profile(self, profile_id: int, profile_name: str = None, 
                           settings_snapshot: Dict[str, Any] = None, 
                           description: str = None, is_default: bool = None,
                           version: int = None) -> bool:
        """Update an existing user profile"""
        try:
            # Build update query dynamically
            updates = []
            params = []
            
            if profile_name is not None:
                updates.append("profile_name = ?")
                params.append(profile_name)
            
            if settings_snapshot is not None:
                updates.append("settings_snapshot = ?")
                params.append(json.dumps(settings_snapshot))
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if version is not None:
                updates.append("version = ?")
                params.append(version)
            
            if is_default is not None:
                updates.append("is_default = ?")
                params.append(is_default)
                
                # If setting as default, unset any existing default for this user
                if is_default:
                    self.cursor.execute("""
                        SELECT user_id FROM user_profiles WHERE id = ?
                    """, (profile_id,))
                    user_row = self.cursor.fetchone()
                    if user_row:
                        user_id = user_row[0]
                        self.cursor.execute("""
                            UPDATE user_profiles 
                            SET is_default = 0 
                            WHERE user_id = ? AND is_default = 1 AND id != ?
                        """, (user_id, profile_id))
            
            if not updates:
                return True
            
            # Always update the updated_at timestamp
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"UPDATE user_profiles SET {', '.join(updates)} WHERE id = ?"
            params.append(profile_id)
            
            self.cursor.execute(query, params)
            self.conn.commit()
            
            db_logger.info(f"Updated user profile ID: {profile_id}")
            return True
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                db_logger.error(f"Profile name '{profile_name}' already exists for this user")
                return False
            else:
                db_logger.error(f"Error updating user profile: {e}")
                self.conn.rollback()
                return False
        except Exception as e:
            db_logger.error(f"Error updating user profile: {e}")
            self.conn.rollback()
            return False
    
    def delete_user_profile(self, profile_id: int) -> bool:
        """Delete a user profile"""
        try:
            self.cursor.execute("""
                DELETE FROM user_profiles WHERE id = ?
            """, (profile_id,))
            
            if self.cursor.rowcount > 0:
                self.conn.commit()
                db_logger.info(f"Deleted user profile ID: {profile_id}")
                return True
            else:
                db_logger.warning(f"No user profile found with ID: {profile_id}")
                return False
                
        except Exception as e:
            db_logger.error(f"Error deleting user profile: {e}")
            self.conn.rollback()
            return False
    
    def get_default_user_profile(self, user_id: int = 1) -> Optional[Dict[str, Any]]:
        """Get the default user profile for a user"""
        try:
            self.cursor.execute("""
                SELECT id, user_id, profile_name, description, settings_snapshot, 
                       is_default, created_at, updated_at, version
                FROM user_profiles
                WHERE user_id = ? AND is_default = 1
            """, (user_id,))
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'profile_name': row[2],
                    'description': row[3],
                    'settings_snapshot': json.loads(row[4]) if row[4] else {},
                    'is_default': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                    'version': row[8] if row[8] is not None else 1
                }
            return None
            
        except Exception as e:
            db_logger.error(f"Error getting default user profile: {e}")
            return None
    
    # Profile History Management Methods
    
    def create_profile_version(self, profile_id: int, version: int, settings_snapshot: str, 
                              change_reason: str = None) -> Optional[Dict[str, Any]]:
        """
        Create a new historical version record in the profile_history table.
        This is typically called right before updating the main user_profiles record.
        """
        try:
            table = self._detect_table_from_query("INSERT INTO profile_history")
            operation = "insert"
            
            result = self._execute_with_monitoring("""
                INSERT INTO profile_history (user_profile_id, version, settings_snapshot, change_reason)
                VALUES (?, ?, ?, ?)
            """, (profile_id, version, settings_snapshot, change_reason), operation, table)
            
            history_id = self.cursor.lastrowid
            self.conn.commit()
            
            # Return the created record
            return self.get_specific_version(history_id)
            
        except Exception as e:
            db_logger.error(f"Error creating profile version: {e}")
            self.conn.rollback()
            return None
    
    def get_profile_history(self, profile_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve the version history for a specific user profile, sorted from newest to oldest.
        """
        try:
            table = self._detect_table_from_query("SELECT FROM profile_history")
            operation = "select"
            
            self._execute_with_monitoring("""
                SELECT id, user_profile_id, version, settings_snapshot, change_reason, archived_at
                FROM profile_history
                WHERE user_profile_id = ?
                ORDER BY version DESC
                LIMIT ? OFFSET ?
            """, (profile_id, limit, offset), operation, table)
            
            rows = self.cursor.fetchall()
            history_list = []
            
            for row in rows:
                history_list.append({
                    'id': row[0],
                    'user_profile_id': row[1],
                    'version': row[2],
                    'settings_snapshot': json.loads(row[3]) if row[3] else {},
                    'change_reason': row[4],
                    'archived_at': row[5]
                })
            
            return history_list
            
        except Exception as e:
            db_logger.error(f"Error getting profile history: {e}")
            return []
    
    def get_specific_version(self, history_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single, specific historical version by its unique ID.
        Used when a user wants to revert to a specific version.
        """
        try:
            table = self._detect_table_from_query("SELECT FROM profile_history")
            operation = "select"
            
            self._execute_with_monitoring("""
                SELECT id, user_profile_id, version, settings_snapshot, change_reason, archived_at
                FROM profile_history
                WHERE id = ?
            """, (history_id,), operation, table)
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'user_profile_id': row[1],
                    'version': row[2],
                    'settings_snapshot': json.loads(row[3]) if row[3] else {},
                    'change_reason': row[4],
                    'archived_at': row[5]
                }
            return None
            
        except Exception as e:
            db_logger.error(f"Error getting specific version: {e}")
            return None
    
    def delete_old_versions(self, profile_id: int, keep_latest: int = 20) -> int:
        """
        Clean up old history for a profile, keeping a specified number of the most recent versions.
        """
        try:
            table = self._detect_table_from_query("DELETE FROM profile_history")
            operation = "delete"
            
            # Get the IDs of versions to keep
            self._execute_with_monitoring("""
                SELECT id FROM profile_history
                WHERE user_profile_id = ?
                ORDER BY version DESC
                LIMIT ?
            """, (profile_id, keep_latest), "select", table)
            
            keep_ids = [row[0] for row in self.cursor.fetchall()]
            
            if not keep_ids:
                return 0
            
            # Delete old versions
            placeholders = ','.join(['?'] * len(keep_ids))
            params = [profile_id] + keep_ids
            
            self._execute_with_monitoring(f"""
                DELETE FROM profile_history
                WHERE user_profile_id = ? AND id NOT IN ({placeholders})
            """, tuple(params), operation, table)
            
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            
            return deleted_count
            
        except Exception as e:
            db_logger.error(f"Error deleting old versions: {e}")
            self.conn.rollback()
            return 0
    
    def archive_current_version(self, profile_id: int, change_reason: str = None) -> bool:
        """
        Archive the current version of a profile before making changes.
        This method automatically retrieves the current profile and creates a history record.
        """
        try:
            # Get the current profile
            current_profile = self.get_user_profile(profile_id)
            if not current_profile:
                db_logger.error(f"Profile {profile_id} not found for archiving")
                return False
            
            # Get the current version or default to 1
            current_version = current_profile.get('version', 1)
            
            # Create the history record
            history_record = self.create_profile_version(
                profile_id=profile_id,
                version=current_version,
                settings_snapshot=json.dumps(current_profile['settings_snapshot']),
                change_reason=change_reason
            )
            
            return history_record is not None
            
        except Exception as e:
            db_logger.error(f"Error archiving current version: {e}")
            return False
    
    def revert_to_version(self, profile_id: int, history_id: int, change_reason: str = None) -> bool:
        """
        Revert a profile to a specific historical version.
        This creates a new history record and updates the current profile.
        """
        try:
            # Get the historical version
            historical_version = self.get_specific_version(history_id)
            if not historical_version:
                db_logger.error(f"Historical version {history_id} not found")
                return False
            
            # Verify the history belongs to the correct profile
            if historical_version['user_profile_id'] != profile_id:
                db_logger.error(f"Historical version {history_id} does not belong to profile {profile_id}")
                return False
            
            # Archive the current version before reverting
            revert_reason = f"Revert to version {historical_version['version']}"
            if change_reason:
                revert_reason += f" - {change_reason}"
            
            if not self.archive_current_version(profile_id, revert_reason):
                db_logger.error("Failed to archive current version before revert")
                return False
            
            # Get current profile to increment version
            current_profile = self.get_user_profile(profile_id)
            if not current_profile:
                return False
            
            new_version = current_profile.get('version', 1) + 1
            
            # Update the profile with historical settings
            success = self.update_user_profile(
                profile_id=profile_id,
                settings_snapshot=historical_version['settings_snapshot'],
                version=new_version
            )
            
            return success
            
        except Exception as e:
            db_logger.error(f"Error reverting to version: {e}")
            self.conn.rollback()
            return False
    
    # Backup and Recovery Methods
        
        def validate_database_integrity(self) -> bool:
            """
            Validate SQLite database integrity and WAL file status
            Returns True if database passes all integrity checks
            """
            try:
                # Check SQLite integrity
                self.cursor.execute("PRAGMA integrity_check")
                integrity_result = self.cursor.fetchone()
                
                if integrity_result[0].lower() != 'ok':
                    db_logger.error(f"Database integrity check failed: {integrity_result[0]}")
                    return False
                
                # Check if WAL file exists and run checkpoint if needed
                wal_file = f"{self.db_path}-wal"
                if os.path.exists(wal_file):
                    db_logger.info("WAL file detected, running checkpoint")
                    self.cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    checkpoint_result = self.cursor.fetchone()
                    db_logger.info(f"WAL checkpoint result: {checkpoint_result}")
                
                return True
                
            except sqlite3.Error as e:
                db_logger.error(f"Database integrity validation failed: {e}")
                return False
    
        def get_database_info(self) -> Dict[str, Any]:
            """
            Get comprehensive database information for backup management
            Returns database statistics and metadata
            """
            try:
                info = {
                    'file_path': str(self.db_path),
                    'file_size_bytes': 0,
                    'file_size_human': '0 B',
                    'wal_file_exists': False,
                    'wal_file_size': 0,
                    'last_modified': None,
                    'tables': {},
                    'total_records': 0,
                    'vacuum_stats': {},
                    'integrity_status': 'unknown'
                }
                
                # File information
                if os.path.exists(self.db_path):
                    stat_info = os.stat(self.db_path)
                    info['file_size_bytes'] = stat_info.st_size
                    info['file_size_human'] = self._format_bytes(stat_info.st_size)
                    info['last_modified'] = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                    
                    # Check WAL file
                    wal_file = f"{self.db_path}-wal"
                    if os.path.exists(wal_file):
                        wal_stat = os.stat(wal_file)
                        info['wal_file_exists'] = True
                        info['wal_file_size'] = wal_stat.st_size
                
                # Database schema and record counts
                self.cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """)
                
                tables = self.cursor.fetchall()
                total_records = 0
                
                for table_row in tables:
                    table_name = table_row[0]
                    
                    # Get record count
                    self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = self.cursor.fetchone()[0]
                    total_records += count
                    
                    # Get table info
                    self.cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = self.cursor.fetchall()
                    
                    info['tables'][table_name] = {
                        'record_count': count,
                        'column_count': len(columns),
                        'columns': [col[1] for col in columns]  # Column names
                    }
                
                info['total_records'] = total_records
                
                # Database vacuum statistics
                self.cursor.execute("PRAGMA page_count")
                page_count = self.cursor.fetchone()[0]
                
                self.cursor.execute("PRAGMA page_size")
                page_size = self.cursor.fetchone()[0]
                
                self.cursor.execute("PRAGMA freelist_count")
                freelist_count = self.cursor.fetchone()[0]
                
                info['vacuum_stats'] = {
                    'page_count': page_count,
                    'page_size': page_size,
                    'freelist_count': freelist_count,
                    'estimated_size': page_count * page_size,
                    'wasted_space': freelist_count * page_size
                }
                
                # Integrity check
                info['integrity_status'] = 'valid' if self.validate_database_integrity() else 'corrupted'
                
                return info
                
            except Exception as e:
                db_logger.error(f"Failed to get database info: {e}")
                return {'error': str(e)}
    
        def create_backup_metadata(self, backup_type: str = 'manual') -> Dict[str, Any]:
            """
            Create backup metadata for tracking and validation
            Returns metadata dictionary with database statistics
            """
            db_info = self.get_database_info()
            
            metadata = {
                'backup_type': backup_type,
                'timestamp': datetime.now().isoformat(),
                'created_by': 'FuturesDB.create_backup_metadata',
                'database_info': db_info,
                'schema_version': self._get_schema_version(),
                'backup_validation': {
                    'integrity_check': db_info.get('integrity_status', 'unknown'),
                    'record_counts': {
                        table: info['record_count'] 
                        for table, info in db_info.get('tables', {}).items()
                    },
                    'total_size_bytes': db_info.get('file_size_bytes', 0)
                }
            }
            
            return metadata
    
        def validate_backup_compatibility(self, backup_metadata: Dict[str, Any]) -> bool:
            """
            Validate if a backup is compatible with current database schema
            Returns True if backup can be safely restored
            """
            try:
                current_schema = self._get_schema_version()
                backup_schema = backup_metadata.get('schema_version', 'unknown')
                
                if backup_schema == 'unknown':
                    db_logger.warning("Backup schema version unknown, cannot validate compatibility")
                    return False
                
                if current_schema != backup_schema:
                    db_logger.warning(f"Schema version mismatch: current={current_schema}, backup={backup_schema}")
                    # In the future, add migration logic here
                    return False
                
                # Validate expected tables exist
                current_info = self.get_database_info()
                current_tables = set(current_info.get('tables', {}).keys())
                backup_tables = set(backup_metadata.get('database_info', {}).get('tables', {}).keys())
                
                missing_tables = backup_tables - current_tables
                if missing_tables:
                    db_logger.warning(f"Backup contains tables not in current schema: {missing_tables}")
                    return False
                
                return True
                
            except Exception as e:
                db_logger.error(f"Backup compatibility validation failed: {e}")
                return False
    
        def get_backup_recovery_points(self) -> List[Dict[str, Any]]:
            """
            Get available recovery points from various backup sources
            Returns list of available backup points with metadata
            """
            from pathlib import Path
            
            recovery_points = []
            
            # Check for local backup files
            backup_dirs = [
                Path(self.db_path).parent.parent / 'backups' / 'manual',
                Path(self.db_path).parent.parent / 'backups' / 'automated',
                Path(self.db_path).parent.parent / 'backups' / 'safety',
                Path(self.db_path).parent.parent / 'backups' / 'local'
            ]
            
            for backup_dir in backup_dirs:
                if backup_dir.exists():
                    backup_type = backup_dir.name
                    
                    # Look for compressed database files
                    for backup_file in backup_dir.glob("*.db.gz"):
                        stat_info = backup_file.stat()
                        
                        recovery_points.append({
                            'type': backup_type,
                            'source': 'file',
                            'path': str(backup_file),
                            'filename': backup_file.name,
                            'size_bytes': stat_info.st_size,
                            'size_human': self._format_bytes(stat_info.st_size),
                            'created_at': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                            'age_hours': (datetime.now() - datetime.fromtimestamp(stat_info.st_mtime)).total_seconds() / 3600
                        })
                    
                    # Look for manifest files to get additional metadata
                    for manifest_file in backup_dir.glob("manifest_*.json"):
                        try:
                            with open(manifest_file, 'r') as f:
                                manifest_data = json.loads(f.read())
                                
                            # Find corresponding recovery point and add manifest data
                            timestamp = manifest_data.get('timestamp', '')
                            for rp in recovery_points:
                                if rp['type'] == backup_type and timestamp in rp['filename']:
                                    rp['manifest'] = manifest_data
                                    break
                                    
                        except Exception as e:
                            db_logger.warning(f"Failed to read manifest {manifest_file}: {e}")
            
            # Sort by creation time (newest first)
            recovery_points.sort(key=lambda x: x['created_at'], reverse=True)
            
            return recovery_points
    
        def estimate_backup_size(self) -> Dict[str, Any]:
            """
            Estimate backup size and compression ratios
            Returns size estimates for backup planning
            """
            try:
                db_info = self.get_database_info()
                
                # Base database size
                raw_size = db_info.get('file_size_bytes', 0)
                
                # Estimate compression ratio based on data type
                # SQLite databases typically compress 30-70% depending on content
                estimated_compression_ratio = 0.6  # Conservative estimate
                
                # WAL file size if exists
                wal_size = db_info.get('wal_file_size', 0)
                
                estimates = {
                    'raw_database_size': raw_size,
                    'raw_database_human': self._format_bytes(raw_size),
                    'wal_file_size': wal_size,
                    'wal_file_human': self._format_bytes(wal_size),
                    'total_raw_size': raw_size + wal_size,
                    'total_raw_human': self._format_bytes(raw_size + wal_size),
                    'estimated_compressed_size': int((raw_size + wal_size) * estimated_compression_ratio),
                    'estimated_compressed_human': self._format_bytes(int((raw_size + wal_size) * estimated_compression_ratio)),
                    'compression_ratio': estimated_compression_ratio,
                    'backup_recommendations': self._get_backup_recommendations(raw_size + wal_size)
                }
                
                return estimates
                
            except Exception as e:
                db_logger.error(f"Failed to estimate backup size: {e}")
                return {'error': str(e)}
    
        def _get_schema_version(self) -> str:
            """Get current database schema version for compatibility checking"""
            try:
                # Check if we have a schema version table
                self.cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='schema_version'
                """)
                
                if self.cursor.fetchone():
                    self.cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
                    result = self.cursor.fetchone()
                    return result[0] if result else 'unknown'
                else:
                    # Infer version from table structure
                    self.cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                    """)
                    tables = [row[0] for row in self.cursor.fetchall()]
                    
                    # Create a hash of table names as a simple schema version
                    import hashlib
                    schema_hash = hashlib.md5(','.join(sorted(tables)).encode()).hexdigest()[:8]
                    return f"inferred_{schema_hash}"
                    
            except Exception as e:
                db_logger.error(f"Failed to get schema version: {e}")
                return 'unknown'
    
        def _format_bytes(self, bytes_size: int) -> str:
            """Format bytes into human readable string"""
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.1f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.1f} PB"
    
        def _get_backup_recommendations(self, total_size: int) -> List[str]:
            """Get backup recommendations based on database size and usage"""
            recommendations = []
            
            if total_size > 100 * 1024 * 1024:  # > 100MB
                recommendations.append("Consider using incremental backups for large database")
                recommendations.append("Enable S3 backup for off-site storage")
            
            if total_size > 1024 * 1024 * 1024:  # > 1GB
                recommendations.append("Database is large - backup may take significant time")
                recommendations.append("Consider running backups during low-usage periods")
            
            # Check WAL file size
            wal_file = f"{self.db_path}-wal"
            if os.path.exists(wal_file):
                wal_size = os.path.getsize(wal_file)
                if wal_size > 50 * 1024 * 1024:  # > 50MB
                    recommendations.append("Large WAL file detected - consider running PRAGMA wal_checkpoint")
            
            # Check free space
            try:
                import shutil
                free_space = shutil.disk_usage(os.path.dirname(self.db_path)).free
                if total_size > free_space * 0.5:  # Backup would use > 50% of free space
                    recommendations.append("Low disk space - monitor backup storage usage")
            except:
                pass
            
            if not recommendations:
                recommendations.append("Database size is optimal for regular backups")
            
            return recommendations
