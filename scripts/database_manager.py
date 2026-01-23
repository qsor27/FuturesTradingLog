"""
New Database Manager using Repository Pattern

This is the new, refactored database manager that replaces the monolithic TradingLog_db.py
with a clean repository pattern for better maintainability and separation of concerns.
"""

import sqlite3
import os
import logging
from typing import Optional
from contextlib import contextmanager

from repositories import (
    TradeRepository,
    PositionRepository,
    OHLCRepository,
    SettingsRepository,
    ProfileRepository,
    StatisticsRepository,
    CustomFieldsRepository
)

# Get database logger
db_logger = logging.getLogger('database')


class DatabaseManager:
    """
    Modern database manager using Repository pattern
    
    This replaces the monolithic FuturesDB class with a clean separation of concerns.
    Each domain (trades, positions, OHLC, etc.) has its own repository with focused responsibility.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize database manager with optional path override"""
        from config import config
        self.db_path = db_path or config.db_path
        self.conn = None
        self.cursor = None
        
        # Repository instances (created when connection is established)
        self.trades = None
        self.positions = None
        self.ohlc = None
        self.settings = None
        self.profiles = None
        self.statistics = None
        self.custom_fields = None
    
    def __enter__(self):
        """Establish database connection and initialize repositories"""
        try:
            db_logger.info(f"Connecting to database: {self.db_path}")
            # timeout=30.0 makes SQLite wait up to 30 seconds for locks instead of failing immediately
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Apply SQLite performance optimizations
            self._apply_sqlite_optimizations()
            
            # Initialize database schema if needed
            self._initialize_schema()
            
            # Create repository instances
            self._initialize_repositories()
            
            db_logger.debug("Database connection and repositories initialized successfully")
            return self
            
        except Exception as e:
            db_logger.error(f"Failed to initialize database: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up database connection"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
                db_logger.error(f"Transaction rolled back due to error: {exc_val}")
            
            self.conn.close()
            db_logger.debug("Database connection closed")
    
    def _apply_sqlite_optimizations(self):
        """Apply SQLite performance optimizations"""
        optimizations = [
            "PRAGMA busy_timeout = 30000",    # Wait up to 30 seconds for locks (prevents 'database is locked' errors)
            "PRAGMA journal_mode = DELETE",   # Use DELETE mode instead of WAL for Docker compatibility
            "PRAGMA synchronous = normal",
            "PRAGMA temp_store = memory",
            "PRAGMA mmap_size = 1073741824",  # 1GB
            "PRAGMA cache_size = -64000"      # 64MB cache
        ]
        
        for pragma in optimizations:
            self.cursor.execute(pragma)
        
        db_logger.debug("Applied SQLite performance optimizations")
    
    def _initialize_schema(self):
        """Initialize database schema if tables don't exist"""
        # Check if main tables exist
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        tables_exist = self.cursor.fetchone() is not None
        
        if not tables_exist:
            db_logger.info("Creating database schema...")
            self._create_tables()
            self._create_indexes()
            self.conn.commit()
            db_logger.info("Database schema created successfully")
        else:
            db_logger.debug("Database schema already exists")
            # Run migrations for existing databases
            self._run_migrations()
            self._create_indexes()  # Ensure indexes exist
            self.conn.commit()
    
    def _create_tables(self):
        """Create all required database tables"""
        
        # Trades table
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
                deleted BOOLEAN DEFAULT 0,
                source_file TEXT,
                import_batch_id TEXT
            )
        """)
        
        # OHLC data table
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
        
        # Positions table  
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                account TEXT NOT NULL,
                instrument TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity INTEGER NOT NULL,
                points_gain_loss REAL,
                dollars_gain_loss REAL,
                commission REAL,
                duration_minutes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted BOOLEAN DEFAULT 0
            )
        """)
        
        # Position executions linking table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_executions (
                id INTEGER PRIMARY KEY,
                position_id INTEGER NOT NULL,
                trade_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (position_id) REFERENCES positions (id),
                FOREIGN KEY (trade_id) REFERENCES trades (id),
                UNIQUE(position_id, trade_id)
            )
        """)
        
        # Chart settings table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chart_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                default_timeframe TEXT NOT NULL DEFAULT '1h',
                default_data_range TEXT NOT NULL DEFAULT '1week',
                volume_visibility BOOLEAN NOT NULL DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User profiles table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                profile_name TEXT NOT NULL,
                description TEXT,
                settings_snapshot TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(user_id, profile_name)
            )
        """)
        
        # Profile history table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_history (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                settings_snapshot TEXT NOT NULL,
                change_reason TEXT,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (profile_id) REFERENCES user_profiles (id) ON DELETE CASCADE
            )
        """)
        
        # Import history table for tracking source files
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY,
                file_name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                import_batch_id TEXT NOT NULL UNIQUE,
                archive_path TEXT,
                trades_imported INTEGER DEFAULT 0,
                accounts_affected TEXT
            )
        """)

        # Initialize default chart settings
        self.cursor.execute("SELECT COUNT(*) FROM chart_settings")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute("""
                INSERT INTO chart_settings (id, default_timeframe, default_data_range, volume_visibility)
                VALUES (1, '1h', '1week', 1)
            """)
    
    def _create_indexes(self):
        """Create performance-optimized indexes"""
        
        indexes = [
            # Trades table indexes
            "CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)",
            "CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account)",
            "CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument)",
            "CREATE INDEX IF NOT EXISTS idx_trades_dollars_gain_loss ON trades(dollars_gain_loss)",
            "CREATE INDEX IF NOT EXISTS idx_trades_entry_execution_id ON trades(entry_execution_id, account)",
            "CREATE INDEX IF NOT EXISTS idx_trades_link_group_id ON trades(link_group_id)",
            "CREATE INDEX IF NOT EXISTS idx_trades_account_entry_time ON trades(account, entry_time)",
            "CREATE INDEX IF NOT EXISTS idx_trades_side_entry_time ON trades(side_of_market, entry_time)",
            "CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time)",
            "CREATE INDEX IF NOT EXISTS idx_trades_deleted ON trades(deleted)",
            "CREATE INDEX IF NOT EXISTS idx_trades_source_file ON trades(source_file)",
            "CREATE INDEX IF NOT EXISTS idx_trades_import_batch_id ON trades(import_batch_id)",

            # Import history indexes
            "CREATE INDEX IF NOT EXISTS idx_import_history_file_name ON import_history(file_name)",
            "CREATE INDEX IF NOT EXISTS idx_import_history_import_batch_id ON import_history(import_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_import_history_import_time ON import_history(import_time DESC)",
            
            # OHLC data indexes  
            "CREATE INDEX IF NOT EXISTS idx_ohlc_instrument_timeframe_timestamp ON ohlc_data(instrument, timeframe, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp ON ohlc_data(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_instrument ON ohlc_data(instrument)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe ON ohlc_data(timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_high_price ON ohlc_data(high_price)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_low_price ON ohlc_data(low_price)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_close_price ON ohlc_data(close_price)",
            "CREATE INDEX IF NOT EXISTS idx_ohlc_volume ON ohlc_data(volume)",
            
            # Positions table indexes
            "CREATE INDEX IF NOT EXISTS idx_positions_account_instrument ON positions(account, instrument)",
            "CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time)",
            "CREATE INDEX IF NOT EXISTS idx_positions_exit_time ON positions(exit_time)",
            "CREATE INDEX IF NOT EXISTS idx_positions_deleted ON positions(deleted)",
            
            # Position executions indexes
            "CREATE INDEX IF NOT EXISTS idx_position_executions_position_id ON position_executions(position_id)",
            "CREATE INDEX IF NOT EXISTS idx_position_executions_trade_id ON position_executions(trade_id)",
            
            # User profiles indexes
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id_profile_name ON user_profiles(user_id, profile_name)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_is_default ON user_profiles(user_id, is_default)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_created_at ON user_profiles(created_at)",
            
            # Profile history indexes
            "CREATE INDEX IF NOT EXISTS idx_profile_history_profile_id_saved_at ON profile_history(profile_id, saved_at DESC)"
        ]
        
        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except Exception as e:
                db_logger.warning(f"Could not create index: {e}")

    def _run_migrations(self):
        """Run database migrations for existing databases"""
        db_logger.info("Running database migrations...")

        # Migration 1: Add source_file and import_batch_id columns to trades table
        self._migrate_trades_source_tracking()

        # Migration 2: Create import_history table
        self._migrate_import_history_table()

        # Migration 3: Create import_execution_logs table
        self._migrate_import_execution_logs_table()

        # Migration 4: Create import_execution_row_logs table
        self._migrate_import_execution_row_logs_table()

        # Migration 5: Add import_row_log_id column to trades table
        self._migrate_trades_import_row_log_id()

        db_logger.info("Database migrations completed")

    def _migrate_trades_source_tracking(self):
        """Add source_file and import_batch_id columns to trades table if missing"""
        # Check which columns exist
        self.cursor.execute("PRAGMA table_info(trades)")
        existing_columns = {row[1] for row in self.cursor.fetchall()}

        # Add source_file column if missing
        if 'source_file' not in existing_columns:
            try:
                self.cursor.execute("ALTER TABLE trades ADD COLUMN source_file TEXT")
                db_logger.info("Added source_file column to trades table")
            except Exception as e:
                db_logger.warning(f"Could not add source_file column: {e}")

        # Add import_batch_id column if missing
        if 'import_batch_id' not in existing_columns:
            try:
                self.cursor.execute("ALTER TABLE trades ADD COLUMN import_batch_id TEXT")
                db_logger.info("Added import_batch_id column to trades table")
            except Exception as e:
                db_logger.warning(f"Could not add import_batch_id column: {e}")

    def _migrate_import_history_table(self):
        """Create import_history table if it doesn't exist"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY,
                file_name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                import_batch_id TEXT NOT NULL UNIQUE,
                archive_path TEXT,
                trades_imported INTEGER DEFAULT 0,
                accounts_affected TEXT
            )
        """)

    def _migrate_import_execution_logs_table(self):
        """Create import_execution_logs table for detailed import logging"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_batch_id TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL CHECK(status IN ('success', 'partial', 'failed')),
                total_rows INTEGER NOT NULL DEFAULT 0,
                success_rows INTEGER NOT NULL DEFAULT 0,
                failed_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                processing_time_ms INTEGER,
                affected_accounts TEXT,
                error_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for import_execution_logs
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_import_execution_logs_batch_id ON import_execution_logs(import_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_import_execution_logs_status ON import_execution_logs(status)",
            "CREATE INDEX IF NOT EXISTS idx_import_execution_logs_import_time ON import_execution_logs(import_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_import_execution_logs_file_name ON import_execution_logs(file_name)"
        ]

        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except Exception as e:
                db_logger.warning(f"Could not create index: {e}")

        db_logger.info("Created import_execution_logs table with indexes")

    def _migrate_import_execution_row_logs_table(self):
        """Create import_execution_row_logs table for row-level import logging"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_execution_row_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_batch_id TEXT NOT NULL,
                row_number INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('success', 'failed', 'skipped')),
                error_message TEXT,
                error_category TEXT CHECK(error_category IN ('validation_error', 'parsing_error', 'duplicate_error', 'database_error', 'business_logic_error', NULL)),
                raw_row_data TEXT,
                validation_errors TEXT,
                created_trade_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (import_batch_id) REFERENCES import_execution_logs(import_batch_id) ON DELETE CASCADE,
                FOREIGN KEY (created_trade_id) REFERENCES trades(id) ON DELETE SET NULL
            )
        """)

        # Create indexes for import_execution_row_logs
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_import_row_logs_batch_id ON import_execution_row_logs(import_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_import_row_logs_status ON import_execution_row_logs(status)",
            "CREATE INDEX IF NOT EXISTS idx_import_row_logs_trade_id ON import_execution_row_logs(created_trade_id)"
        ]

        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except Exception as e:
                db_logger.warning(f"Could not create index: {e}")

        db_logger.info("Created import_execution_row_logs table with indexes")

    def _migrate_trades_import_row_log_id(self):
        """Add import_row_log_id column to trades table"""
        # Check if column exists
        self.cursor.execute("PRAGMA table_info(trades)")
        existing_columns = {row[1] for row in self.cursor.fetchall()}

        if 'import_row_log_id' not in existing_columns:
            try:
                self.cursor.execute("ALTER TABLE trades ADD COLUMN import_row_log_id INTEGER")
                db_logger.info("Added import_row_log_id column to trades table")

                # Create index
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_import_row_log_id ON trades(import_row_log_id)")
                db_logger.info("Created index on import_row_log_id column")
            except Exception as e:
                db_logger.warning(f"Could not add import_row_log_id column: {e}")
    
    def _initialize_repositories(self):
        """Initialize all repository instances"""
        self.trades = TradeRepository(self.conn, self.cursor)
        self.positions = PositionRepository(self.conn, self.cursor)
        self.ohlc = OHLCRepository(self.conn, self.cursor)
        self.settings = SettingsRepository(self.conn, self.cursor)
        self.profiles = ProfileRepository(self.conn, self.cursor)
        self.statistics = StatisticsRepository(self.conn, self.cursor)
        self.custom_fields = CustomFieldsRepository(self.conn, self.cursor)

        db_logger.debug("All repositories initialized")
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        try:
            yield
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            db_logger.error(f"Transaction rolled back: {e}")
            raise
    
    def commit(self):
        """Commit current transaction"""
        self.conn.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        self.conn.rollback()


# Backward compatibility function for existing code
def create_database_manager(db_path: str = None) -> DatabaseManager:
    """Factory function to create a new database manager instance"""
    return DatabaseManager(db_path)