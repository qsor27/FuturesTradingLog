    def _ensure_tables_exist(self):
        db = self.get_db()
        
        # Create trades table with all needed columns
        db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Create indexes for performance
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(entry_time)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_group ON trades(link_group_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_execution_id ON trades(entry_execution_id)')
        
        # Verify entry_execution_id column exists (for backward compatibility)
        columns = {row[1] for row in db.execute("PRAGMA table_info(trades)").fetchall()}
        if 'entry_execution_id' not in columns:
            print("Adding missing entry_execution_id column...")
            db.execute("ALTER TABLE trades ADD COLUMN entry_execution_id TEXT")
            
        db.commit()