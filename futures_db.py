import os
import sqlite3
from flask import current_app, g
import pandas as pd

class FuturesDB:
    def __init__(self):
        self.get_db()
        self._ensure_tables_exist()

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
        
        # Create trades table
        db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                pnl REAL,
                commission REAL,
                net_pnl REAL,
                trade_group INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create trade_links table
        db.execute('''
            CREATE TABLE IF NOT EXISTS trade_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                linked_trade_id INTEGER,
                FOREIGN KEY (trade_id) REFERENCES trades (id),
                FOREIGN KEY (linked_trade_id) REFERENCES trades (id)
            )
        ''')

        # Add indexes for performance
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_trades_group ON trades(trade_group)')
        
        db.commit()

    def vacuum_db(self):
        """Optimize the database file size and performance"""
        db = self.get_db()
        db.execute("VACUUM")
        db.commit()

    def optimize_db(self):
        """Run general database optimizations"""
        db = self.get_db()
        db.execute("PRAGMA optimize")
        db.execute("PRAGMA analysis_limit=1000")
        db.execute("PRAGMA automatic_index=true")
        db.commit()
