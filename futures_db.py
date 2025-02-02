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

    def get_db(self):
        if 'db' not in g:
            db_path = current_app.config['DATABASE_PATH']
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            g.db = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db(self):
        db = g.pop('db', None)
        if db is not None:
            db.close()

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
        
        db.commit()