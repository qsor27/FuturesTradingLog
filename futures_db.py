import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
import os

class FuturesDB:
    def __init__(self, db_path: str = r'C:\TradingTest\backup\futures_trades.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish database connection when entering context"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Makes rows accessible by column name
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        return self

    def get_trade_by_id(self, trade_id: int) -> Dict[str, Any]:
        """Get a single trade by ID."""
        try:
            query = """
                SELECT *
                FROM trades
                WHERE id = ?
            """
            self.cursor.execute(query, (trade_id,))
            trade = dict(self.cursor.fetchone())
            return trade
        except Exception as e:
            print(f"Error getting trade: {e}")
            return None

    def update_trade_details(self, trade_id: int, chart_url: str = None, notes: str = None) -> bool:
        """Update chart URL and notes for a trade."""
        try:
            updates = []
            values = []
            if chart_url is not None:
                updates.append("chart_url = ?")
                values.append(chart_url)
            if notes is not None:
                updates.append("notes = ?")
                values.append(notes)
                
            if not updates:
                return False
                
            query = f"""
                UPDATE trades
                SET {', '.join(updates)}
                WHERE id = ?
            """
            values.append(trade_id)
            
            self.cursor.execute(query, values)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating trade details: {e}")
            self.conn.rollback()
            return False

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up database connection when exiting context"""
        try:
            if exc_type is not None:
                # An exception occurred, so rollback any pending transactions
                if self.conn:
                    self.conn.rollback()
            else:
                # No exception, so commit any pending transactions
                if self.conn:
                    self.conn.commit()
        finally:
            # Always close cursor and connection
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            # Set them to None to ensure we don't try to use them again
            self.cursor = None
            self.conn = None
        return False  # Propagate any exceptions that occurred

    def delete_trades(self, trade_ids: List[int]) -> bool:
        """Delete multiple trades by their IDs."""
        try:
            # Create placeholders for the IN clause
            placeholders = ','.join('?' * len(trade_ids))
            query = f"DELETE FROM trades WHERE id IN ({placeholders})"
            
            self.cursor.execute(query, trade_ids)
            self.conn.commit()
            
            deleted_count = self.cursor.rowcount
            print(f"Deleted {deleted_count} trades")
            return True
        except Exception as e:
            print(f"Error deleting trades: {e}")
            self.conn.rollback()
            return False

    def import_csv(self, filepath: str) -> bool:
        """Import trades from a CSV file."""
        try:
            # Read CSV file
            df = pd.read_csv(filepath)
            
            # Rename columns to match database schema
            column_mapping = {
                'Instrument': 'instrument',
                'Side of Market': 'side_of_market',
                'Quantity': 'quantity',
                'Entry Price': 'entry_price',
                'Entry Time': 'entry_time',
                'Exit Time': 'exit_time',
                'Exit Price': 'exit_price',
                'Result Gain/Loss in Points': 'points_gain_loss',
                'Gain/Loss in Dollars': 'dollars_gain_loss',
                'ID': 'id',
                'Commission': 'commission',
                'Account': 'account'
            }
            df = df.rename(columns=column_mapping)
            
            # Convert timestamps
            for col in ['entry_time', 'exit_time']:
                df[col] = pd.to_datetime(df[col])
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Generate integer ID if not present or not an integer
            if 'id' not in df.columns or not pd.api.types.is_integer_dtype(df['id']):
                df['id'] = range(1, len(df) + 1)
            
            # Ensure id is integer
            df['id'] = df['id'].astype(int)
            
            # Insert each trade
            for _, row in df.iterrows():
                # Clean NaN values and create dict
                trade = {k: v for k, v in row.items() if pd.notna(v)}
                
                # Build dynamic insert query
                columns = list(trade.keys())
                values = list(trade.values())
                placeholders = ['?'] * len(columns)
                
                query = f"""
                    INSERT OR REPLACE INTO trades ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
                
                try:
                    self.cursor.execute(query, values)
                except Exception as e:
                    print(f"Error inserting row: {e}")
                    continue
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error importing CSV: {e}")
            self.conn.rollback()
            return False

    def get_unique_accounts(self) -> List[str]:
        """Get list of unique account names."""
        try:
            query = "SELECT DISTINCT account FROM trades ORDER BY account"
            self.cursor.execute(query)
            return [row['account'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting unique accounts: {e}")
            return []

    def get_recent_trades(self, page_size: int = 50, page: int = 1, sort_by: str = 'entry_time', 
                     sort_order: str = 'DESC', account: str = None, 
                     trade_result: str = None, side: str = None) -> tuple:
        """Get trades with sorting, filtering, and pagination options."""
        try:
            # Validate sort parameters
            valid_sort_columns = ['entry_time', 'id']
            valid_sort_orders = ['ASC', 'DESC']
            
            if sort_by not in valid_sort_columns:
                sort_by = 'entry_time'
            if sort_order not in valid_sort_orders:
                sort_order = 'DESC'
            
            # Build WHERE clause based on filters
            where_clauses = []
            params = []
            
            if account:
                where_clauses.append("account = ?")
                params.append(account)
            
            if trade_result:
                if trade_result == 'winning':
                    where_clauses.append("points_gain_loss > 0")
                elif trade_result == 'losing':
                    where_clauses.append("points_gain_loss < 0")
            
            if side:
                where_clauses.append("side_of_market = ?")
                params.append(side)
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get total count for pagination
            count_query = "SELECT COUNT(*) as total FROM trades"
            if where_clauses:
                count_query += " WHERE " + " AND ".join(where_clauses)
            
            self.cursor.execute(count_query, params)
            total_count = self.cursor.fetchone()['total']
            total_pages = (total_count + page_size - 1) // page_size
            
            # Construct final query with pagination
            query = """
                SELECT 
                    id, 
                    instrument, 
                    side_of_market, 
                    quantity, 
                    entry_price, 
                    entry_time, 
                    exit_time, 
                    exit_price,
                    points_gain_loss, 
                    dollars_gain_loss, 
                    commission, 
                    account
                FROM trades
            """
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
            
            # Add pagination parameters
            params.extend([page_size, offset])
            
            self.cursor.execute(query, params)
            
            # Convert to list of dictionaries with safe type conversion
            trades = []
            for row in self.cursor.fetchall():
                trade = dict(row)
                # Ensure numeric fields are converted to float, with None as fallback
                for field in ['entry_price', 'exit_price', 'points_gain_loss', 'dollars_gain_loss', 'commission']:
                    trade[field] = float(trade[field]) if trade[field] is not None else None
                trades.append(trade)
            
            return trades, total_count, total_pages
            
        except Exception as e:
            print(f"Error getting trades: {e}")
            return [], 0, 0

    def get_statistics(self, timeframe='daily', start_date=None, end_date=None, accounts=None):
        """Get trading statistics for the specified timeframe."""
        try:
            # Base timeframe grouping
            if timeframe == 'daily':
                date_group = "date(entry_time)"
            elif timeframe == 'weekly':
                date_group = "strftime('%Y-W%W', entry_time)"
            elif timeframe == 'monthly':
                date_group = "strftime('%Y-%m', entry_time)"
            else:
                raise ValueError("Invalid timeframe")

            # Build the base query
            query = f"""
                WITH TimeframeTrades AS (
                    SELECT 
                        {date_group} as period,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN side_of_market = 'Long' THEN 1 ELSE 0 END) as long_trades,
                        SUM(CASE WHEN side_of_market = 'Short' THEN 1 ELSE 0 END) as short_trades,
                        SUM(CASE WHEN side_of_market = 'Long' AND dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_longs,
                        SUM(CASE WHEN side_of_market = 'Long' AND dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_longs,
                        SUM(CASE WHEN side_of_market = 'Short' AND dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_shorts,
                        SUM(CASE WHEN side_of_market = 'Short' AND dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_shorts,
                        SUM(dollars_gain_loss) as total_pnl,
                        SUM(points_gain_loss) as total_points,
                        SUM(commission) as total_commission,
                        SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                        COUNT(DISTINCT CASE WHEN dollars_gain_loss > 0 THEN date(entry_time) END) as winning_days,
                        COUNT(DISTINCT CASE WHEN dollars_gain_loss < 0 THEN date(entry_time) END) as losing_days
                    FROM trades
                    WHERE entry_time IS NOT NULL
                """

            # Build parameters list
            params = []

            # Add date range conditions if provided
            if start_date or end_date:
                query += " AND entry_time BETWEEN COALESCE(?, datetime('now', '-30 days')) AND COALESCE(?, datetime('now', '+1 day'))"
                params.extend([start_date, end_date])

            # Add account filtering if provided
            if accounts:
                accounts_placeholders = ','.join(['?' for _ in accounts])
                query += f" AND account IN ({accounts_placeholders})"
                params.extend(accounts)

            # Complete the query
            query += """
                    GROUP BY period
                    ORDER BY period DESC
                )
                SELECT 
                    period,
                    total_trades,
                    winning_trades,
                    losing_trades,
                    ROUND(CAST(winning_trades AS FLOAT) / NULLIF(total_trades, 0) * 100, 2) as win_rate,
                    ROUND(CAST(winning_longs AS FLOAT) / NULLIF(winning_longs + losing_longs, 0) * 100, 2) as long_win_rate,
                    ROUND(CAST(winning_shorts AS FLOAT) / NULLIF(winning_shorts + losing_shorts, 0) * 100, 2) as short_win_rate,
                    total_pnl,
                    total_points,
                    total_commission,
                    winning_days,
                    losing_days,
                    long_trades,
                    short_trades
                FROM TimeframeTrades
            """

            print(f"Executing query with params: {params}")  # Debug print
            self.cursor.execute(query, params)
            results = [dict(row) for row in self.cursor.fetchall()]
            print(f"Found {len(results)} results")  # Debug print
            return results
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return []


if __name__ == "__main__":
    # Example usage
    with FuturesDB() as db:
        # Import trades from CSV
        success = db.import_csv('TradeLog.csv')
        if success:
            print("CSV import successful")
        
        # Display some recent trades
        trades = db.get_recent_trades(5)
        for trade in trades:
            print(f"ID: {trade['id']} | {trade['instrument']} | P&L: ${trade['dollars_gain_loss']}")
