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
    
    def update_trade_details(self, trade_id: int, notes: str, chart_url: str) -> bool:
        """Update trade notes and chart URL"""
        try:
            db = self.get_db()
            db.execute("""
                UPDATE trades
                SET notes = ?, chart_url = ?
                WHERE id = ?
            """, (notes, chart_url, trade_id))
            db.commit()
            return True
        except sqlite3.Error:
            return False

    def get_unique_accounts(self) -> List[str]:
        """Get a list of unique account names from the database"""
        db = self.get_db()
        accounts = db.execute("""
            SELECT DISTINCT account 
            FROM trades 
            WHERE account IS NOT NULL 
            ORDER BY account
        """).fetchall()
        return [account['account'] for account in accounts]

    def get_trade_by_id(self, trade_id: int) -> Optional[sqlite3.Row]:
        """Get trade details by ID"""
        db = self.get_db()
        trade = db.execute("""
            SELECT * FROM trades WHERE id = ?
        """, (trade_id,)).fetchone()
        return trade

    def get_recent_trades(
        self,
        page_size: int = 50,
        page: int = 1,
        sort_by: str = 'entry_time',
        sort_order: str = 'DESC',
        account: Optional[List[str]] = None,
        trade_result: Optional[str] = None,
        side: Optional[str] = None
    ) -> Tuple[List[sqlite3.Row], int, int]:
        """
        Get recent trades with pagination and filtering
        Returns: (trades, total_count, total_pages)
        """
        db = self.get_db()
        
        # Base query
        query = "SELECT * FROM trades WHERE 1=1"
        count_query = "SELECT COUNT(*) as count FROM trades WHERE 1=1"
        params: List[Any] = []
        
        # Add filters
        if account and account != []:
            placeholders = ','.join('?' * len(account))
            query += f" AND account IN ({placeholders})"
            count_query += f" AND account IN ({placeholders})"
            params.extend(account)
        
        if trade_result:
            if trade_result == 'winner':
                query += " AND dollars_gain_loss > 0"
                count_query += " AND dollars_gain_loss > 0"
            elif trade_result == 'loser':
                query += " AND dollars_gain_loss < 0"
                count_query += " AND dollars_gain_loss < 0"
            elif trade_result == 'breakeven':
                query += " AND dollars_gain_loss = 0"
                count_query += " AND dollars_gain_loss = 0"
        
        if side:
            query += " AND side_of_market = ?"
            count_query += " AND side_of_market = ?"
            params.append(side)
        
        # Get total count for pagination
        total_count = db.execute(count_query, params).fetchone()['count']
        total_pages = (total_count + page_size - 1) // page_size
        
        # Add sorting and pagination
        query += f" ORDER BY {sort_by} {sort_order}"
        query += " LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        
        trades = db.execute(query, params).fetchall()
        return trades, total_count, total_pages

    def get_statistics(self, period_type: str = None, accounts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Calculate trading statistics with period and account filtering"""
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
        
        params: List[Any] = []
        
        # Add time period filter
        if period_type:
            if period_type == 'daily':
                base_query += " AND date(entry_time) = date('now')"
            elif period_type == 'weekly':
                base_query += " AND entry_time >= date('now', '-7 days')"
            elif period_type == 'monthly':
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

    def link_trades(self, trade_ids: List[int]) -> bool:
        """Link multiple trades together"""
        if not trade_ids or len(trade_ids) < 2:
            return False
            
        try:
            db = self.get_db()
            
            # Get the next available group ID
            max_group = db.execute("SELECT MAX(link_group_id) as max_id FROM trades").fetchone()
            next_group_id = (max_group['max_id'] or 0) + 1
            
            # Update all trades with the new group ID
            placeholders = ','.join('?' * len(trade_ids))
            db.execute(f"""
                UPDATE trades
                SET link_group_id = ?
                WHERE id IN ({placeholders})
            """, [next_group_id] + trade_ids)
            
            db.commit()
            return True
            
        except sqlite3.Error:
            return False

    def unlink_trades(self, group_id: int) -> bool:
        """Remove trade links for a group"""
        try:
            db = self.get_db()
            db.execute("""
                UPDATE trades
                SET link_group_id = NULL
                WHERE link_group_id = ?
            """, (group_id,))
            db.commit()
            return True
        except sqlite3.Error:
            return False

    def get_linked_trades(self, group_id: int) -> List[sqlite3.Row]:
        """Get all trades in a linked group"""
        db = self.get_db()
        return db.execute("""
            SELECT * FROM trades
            WHERE link_group_id = ?
            ORDER BY entry_time
        """, (group_id,)).fetchall()

    def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Calculate statistics for a group of linked trades"""
        trades = self.get_linked_trades(group_id)
        if not trades:
            return {}
            
        stats = {
            'total_trades': len(trades),
            'total_pnl': sum(trade['dollars_gain_loss'] for trade in trades),
            'winning_trades': sum(1 for trade in trades if trade['dollars_gain_loss'] > 0),
            'losing_trades': sum(1 for trade in trades if trade['dollars_gain_loss'] < 0)
        }
        
        # Calculate win rate
        stats['win_rate'] = (stats['winning_trades'] / stats['total_trades']) * 100 if stats['total_trades'] > 0 else 0
        
        # Calculate average winner and loser
        winners = [trade['dollars_gain_loss'] for trade in trades if trade['dollars_gain_loss'] > 0]
        losers = [trade['dollars_gain_loss'] for trade in trades if trade['dollars_gain_loss'] < 0]
        
        stats['avg_winner'] = sum(winners) / len(winners) if winners else 0
        stats['avg_loser'] = sum(losers) / len(losers) if losers else 0
        
        return stats

    def delete_trades(self, trade_ids: List[int]) -> bool:
        """Delete multiple trades by their IDs"""
        if not trade_ids:
            return False
            
        try:
            db = self.get_db()
            placeholders = ','.join('?' * len(trade_ids))
            db.execute(f"""
                DELETE FROM trades
                WHERE id IN ({placeholders})
            """, trade_ids)
            db.commit()
            return True
        except sqlite3.Error:
            return False

    def import_csv(self, csv_path: str) -> bool:
        """Import trades from a CSV file"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Format column names
            df.columns = [col.strip() for col in df.columns]
            
            # Convert date columns
            for date_col in ['entry_time', 'exit_time']:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col])
            
            # Insert data into database
            db = self.get_db()
            
            for _, row in df.iterrows():
                db.execute("""
                    INSERT INTO trades (
                        instrument, side_of_market, quantity,
                        entry_price, entry_time, exit_time, exit_price,
                        points_gain_loss, dollars_gain_loss, commission,
                        account
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    row['account']
                ))
            
            db.commit()
            return True
            
        except (pd.errors.EmptyDataError, KeyError, sqlite3.Error) as e:
            print(f"Error importing CSV: {str(e)}")
            return False