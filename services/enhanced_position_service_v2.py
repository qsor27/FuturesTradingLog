"""
Enhanced Position Service V2 - Using Refactored Algorithms

Integrates the new modular position algorithms with the existing position service architecture.
Maintains backward compatibility while providing improved maintainability.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging

from services.position_algorithms import (
    calculate_running_quantity,
    group_executions_by_position,
    calculate_position_pnl,
    validate_position_boundaries,
    aggregate_position_statistics,
    create_position_summary
)

# Get logger
logger = logging.getLogger('enhanced_position_service_v2')


class EnhancedPositionServiceV2:
    """
    Enhanced position service using refactored algorithms.
    
    Provides the same interface as the original PositionService but uses
    the new modular, testable functions internally.
    """
    
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        
    def __enter__(self):
        """Establish database connection when entering context"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Create positions table if it doesn't exist
        self._create_positions_table()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection when exiting context"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
    
    def _create_positions_table(self):
        """Create the positions table for aggregated position tracking"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                instrument TEXT NOT NULL,
                account TEXT NOT NULL,
                position_type TEXT NOT NULL,  -- 'Long' or 'Short'
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                total_quantity INTEGER NOT NULL,
                average_entry_price REAL NOT NULL,
                average_exit_price REAL,
                total_points_pnl REAL,
                total_dollars_pnl REAL,
                total_commission REAL,
                position_status TEXT NOT NULL,  -- 'open', 'closed'
                execution_count INTEGER DEFAULT 0,
                risk_reward_ratio REAL,
                max_quantity INTEGER,  -- Peak position size
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance
        indexes = [
            ("idx_positions_instrument", "CREATE INDEX IF NOT EXISTS idx_positions_instrument ON positions(instrument)"),
            ("idx_positions_account", "CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account)"),
            ("idx_positions_entry_time", "CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time)"),
            ("idx_positions_status", "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(position_status)"),
            ("idx_positions_account_instrument", "CREATE INDEX IF NOT EXISTS idx_positions_account_instrument ON positions(account, instrument)"),
        ]
        
        for index_name, create_sql in indexes:
            try:
                self.cursor.execute(create_sql)
            except Exception as e:
                logger.warning(f"Could not create index {index_name}: {e}")
        
        # Create position_executions mapping table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_executions (
                id INTEGER PRIMARY KEY,
                position_id INTEGER NOT NULL,
                trade_id INTEGER NOT NULL,
                execution_order INTEGER NOT NULL,  -- Order within the position
                FOREIGN KEY (position_id) REFERENCES positions (id),
                FOREIGN KEY (trade_id) REFERENCES trades (id),
                UNIQUE(position_id, trade_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_executions_position_id 
            ON position_executions(position_id)
        """)
        
        self.conn.commit()
    
    def rebuild_positions_from_trades(self) -> Dict[str, int]:
        """Rebuild all positions from existing trades data using new algorithms"""
        logger.info("Starting position rebuild using enhanced algorithms")
        
        # Clear existing positions
        self.cursor.execute("DELETE FROM position_executions")
        self.cursor.execute("DELETE FROM positions")
        
        # Get all trades grouped by account and instrument
        self.cursor.execute("""
            SELECT * FROM trades 
            ORDER BY account, instrument, entry_time
        """)
        
        all_trades = [dict(row) for row in self.cursor.fetchall()]
        
        # Group trades by account and instrument
        grouped_trades = {}
        for trade in all_trades:
            key = (trade['account'], trade['instrument'])
            if key not in grouped_trades:
                grouped_trades[key] = []
            grouped_trades[key].append(trade)
        
        # Process each group using new algorithms
        stats = {
            'total_positions': 0,
            'accounts_processed': 0,
            'instruments_processed': 0,
            'validation_errors': []
        }
        
        for (account, instrument), trades in grouped_trades.items():
            try:
                result = self._process_trades_for_instrument(trades, account, instrument)
                stats['total_positions'] += result['positions_created']
                
                if result['validation_errors']:
                    stats['validation_errors'].extend(result['validation_errors'])
                    
            except Exception as e:
                error_msg = f"Failed to process {account}/{instrument}: {str(e)}"
                logger.error(error_msg)
                stats['validation_errors'].append(error_msg)
        
        stats['accounts_processed'] = len(set(key[0] for key in grouped_trades.keys()))
        stats['instruments_processed'] = len(set(key[1] for key in grouped_trades.keys()))
        
        # Add expected keys for backward compatibility with routes
        stats['positions_created'] = stats['total_positions']
        stats['trades_processed'] = len(all_trades)
        
        logger.info(f"Position rebuild completed: {stats}")
        return stats
    
    def _process_trades_for_instrument(self, trades: List[Dict], account: str, instrument: str) -> Dict[str, Any]:
        """Process trades for a single account/instrument combination using new algorithms"""
        if not trades:
            return {'positions_created': 0, 'validation_errors': []}
        
        logger.debug(f"Processing {len(trades)} trades for {account}/{instrument}")
        
        # Since each trade record represents a complete round-trip position,
        # directly create position records from trade data
        positions_created = 0
        validation_errors = []
        
        for trade in trades:
            try:
                logger.info(f"DEBUG: Processing trade {trade['id']}: {trade.get('entry_price')} -> {trade.get('exit_price')}")
                position_id = self._create_position_from_trade(trade)
                if position_id:
                    positions_created += 1
                    logger.info(f"Created position {position_id} from trade {trade['id']}")
                else:
                    logger.warning(f"No position ID returned for trade {trade['id']}")
            except Exception as e:
                error_msg = f"Failed to create position from trade {trade['id']}: {str(e)}"
                logger.error(error_msg)
                validation_errors.append(error_msg)
        
        return {
            'positions_created': positions_created,
            'validation_errors': validation_errors
        }
    
    def _create_position_from_trade(self, trade: Dict) -> Optional[int]:
        """Create a position record directly from a trade record"""
        
        logger.info(f"DEBUG: _create_position_from_trade called for trade {trade['id']}")
        logger.info(f"DEBUG: exit_price={trade.get('exit_price')}, exit_time={trade.get('exit_time')}")
        
        # Only create positions for completed trades (have exit data)
        if not trade.get('exit_price') or not trade.get('exit_time'):
            logger.warning(f"Skipping incomplete trade {trade['id']} - no exit data: exit_price={trade.get('exit_price')}, exit_time={trade.get('exit_time')}")
            return None
        
        # Convert entry/exit times to proper format
        entry_time = trade['entry_time']
        exit_time = trade['exit_time']
        
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)
        
        # Calculate P&L using existing trade data
        points_pnl = trade.get('points_gain_loss', 0)
        dollars_pnl = trade.get('dollars_gain_loss', 0)
        
        # If P&L not calculated, calculate it
        if points_pnl is None:
            if trade['side_of_market'] == 'Long':
                points_pnl = trade['exit_price'] - trade['entry_price']
            else:  # Short
                points_pnl = trade['entry_price'] - trade['exit_price']
        
        if dollars_pnl is None:
            dollars_pnl = points_pnl * trade['quantity']
        
        # Insert position record
        self.cursor.execute("""
            INSERT INTO positions (
                instrument, account, position_type, entry_time, exit_time,
                total_quantity, average_entry_price, average_exit_price,
                total_points_pnl, total_dollars_pnl, total_commission,
                position_status, execution_count, max_quantity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['instrument'],
            trade['account'],
            trade['side_of_market'],  # 'Long' or 'Short'
            entry_time,
            exit_time,
            trade['quantity'],
            trade['entry_price'],
            trade['exit_price'],
            points_pnl,
            dollars_pnl,
            trade.get('commission', 0),
            'closed',
            1,  # Single trade = 1 execution
            trade['quantity']  # Max quantity is same as total for single trades
        ))
        
        position_id = self.cursor.lastrowid
        
        # Create position_execution mapping
        self.cursor.execute("""
            INSERT INTO position_executions (position_id, trade_id, execution_order)
            VALUES (?, ?, ?)
        """, (position_id, trade['id'], 1))
        
        return position_id
    
    def get_positions(self, account: Optional[str] = None, instrument: Optional[str] = None) -> List[Dict]:
        """Save position using enhanced summary data"""
        try:
            if 'error' in summary:
                logger.warning(f"Cannot save position with error: {summary['error']}")
                return None
            
            # Prepare position data
            position_data = {
                'instrument': summary['instrument'],
                'account': summary['account'],
                'position_type': summary.get('position_type', 'Unknown'),
                'entry_time': summary['entry_time'],
                'exit_time': summary.get('exit_time'),
                'total_quantity': summary.get('position_size', 0),
                'average_entry_price': summary.get('avg_entry_price', 0),
                'average_exit_price': summary.get('avg_exit_price'),
                'total_points_pnl': summary.get('points_pnl'),
                'total_dollars_pnl': summary.get('net_pnl'),
                'total_commission': summary.get('total_commission', 0),
                'position_status': summary['status'],
                'execution_count': summary['execution_count'],
                'max_quantity': summary.get('max_quantity', 0)
            }
            
            # Insert position
            insert_sql = """
                INSERT INTO positions (
                    instrument, account, position_type, entry_time, exit_time,
                    total_quantity, average_entry_price, average_exit_price,
                    total_points_pnl, total_dollars_pnl, total_commission,
                    position_status, execution_count, max_quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.cursor.execute(insert_sql, (
                position_data['instrument'],
                position_data['account'],
                position_data['position_type'],
                position_data['entry_time'],
                position_data['exit_time'],
                position_data['total_quantity'],
                position_data['average_entry_price'],
                position_data['average_exit_price'],
                position_data['total_points_pnl'],
                position_data['total_dollars_pnl'],
                position_data['total_commission'],
                position_data['position_status'],
                position_data['execution_count'],
                position_data['max_quantity']
            ))
            
            position_id = self.cursor.lastrowid
            
            # Map executions to position
            for i, flow in enumerate(flows):
                execution_id = flow.execution.get('id')
                if execution_id:
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO position_executions 
                        (position_id, trade_id, execution_order)
                        VALUES (?, ?, ?)
                    """, (position_id, execution_id, i))
            
            logger.debug(f"Saved enhanced position {position_id} for {position_data['account']}/{position_data['instrument']}")
            return position_id
            
        except Exception as e:
            logger.error(f"Failed to save enhanced position: {e}")
            return None
    
    def get_positions(self, page_size: int = 50, page: int = 1, 
                     account: Optional[str] = None, 
                     instrument: Optional[str] = None,
                     status: Optional[str] = None) -> Dict[str, Any]:
        """Get positions with pagination and filtering"""
        # Build WHERE clause
        where_conditions = []
        params = []
        
        if account:
            where_conditions.append("account = ?")
            params.append(account)
        
        if instrument:
            where_conditions.append("instrument = ?")
            params.append(instrument)
        
        if status:
            where_conditions.append("position_status = ?")
            params.append(status)
        
        where_clause = " AND ".join(where_conditions)
        if where_clause:
            where_clause = "WHERE " + where_clause
        
        # Get total count
        count_sql = f"SELECT COUNT(*) FROM positions {where_clause}"
        self.cursor.execute(count_sql, params)
        total_count = self.cursor.fetchone()[0]
        
        # Get positions with pagination
        offset = (page - 1) * page_size
        positions_sql = f"""
            SELECT * FROM positions 
            {where_clause}
            ORDER BY entry_time DESC 
            LIMIT ? OFFSET ?
        """
        self.cursor.execute(positions_sql, params + [page_size, offset])
        positions = [dict(row) for row in self.cursor.fetchall()]
        
        return {
            'positions': positions,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    
    def get_position_statistics(self, account: Optional[str] = None) -> Dict[str, Any]:
        """Get position statistics using new aggregation algorithms"""
        # Build WHERE clause
        where_clause = ""
        params = []
        
        if account:
            where_clause = "WHERE account = ?"
            params.append(account)
        
        # Get all positions
        sql = f"SELECT * FROM positions {where_clause}"
        self.cursor.execute(sql, params)
        positions = [dict(row) for row in self.cursor.fetchall()]
        
        # Convert to format expected by aggregation function
        positions_data = []
        for pos in positions:
            positions_data.append({
                'net_pnl': pos.get('total_dollars_pnl', 0)
            })
        
        # Use new aggregation algorithm
        stats = aggregate_position_statistics(positions_data)
        
        # Add additional database-level statistics
        stats.update({
            'total_positions_in_db': len(positions),
            'open_positions': len([p for p in positions if p.get('position_status') == 'open']),
            'closed_positions': len([p for p in positions if p.get('position_status') == 'closed'])
        })
        
        return stats

    def rebuild_positions_for_trades(self, trade_ids: List[int]) -> Dict[str, Any]:
        """
        Rebuild positions affected by specific trades using incremental updates
        
        Args:
            trade_ids: List of trade IDs that have been added/modified
            
        Returns:
            Dictionary with rebuild statistics and affected account/instrument combinations
        """
        if not trade_ids:
            return {'positions_affected': 0, 'accounts_processed': [], 'instruments_processed': [], 'validation_errors': []}
        
        logger.info(f"Starting incremental rebuild for {len(trade_ids)} trades")
        
        # Get affected trades and determine account/instrument combinations
        affected_combinations = self._analyze_trade_impact(trade_ids)
        
        if not affected_combinations:
            logger.warning(f"No valid trades found for IDs: {trade_ids}")
            return {'positions_affected': 0, 'accounts_processed': [], 'instruments_processed': [], 'validation_errors': []}
        
        # Rebuild positions for each affected combination
        stats = {
            'positions_affected': 0,
            'accounts_processed': [],
            'instruments_processed': [],
            'validation_errors': []
        }
        
        for account, instrument in affected_combinations:
            try:
                result = self.rebuild_positions_for_account_instrument(account, instrument)
                stats['positions_affected'] += result['positions_created']
                stats['validation_errors'].extend(result['validation_errors'])
                
                if account not in stats['accounts_processed']:
                    stats['accounts_processed'].append(account)
                if instrument not in stats['instruments_processed']:
                    stats['instruments_processed'].append(instrument)
                    
            except Exception as e:
                error_msg = f"Failed to rebuild positions for {account}/{instrument}: {str(e)}"
                logger.error(error_msg)
                stats['validation_errors'].append(error_msg)
        
        logger.info(f"Incremental rebuild completed: {stats['positions_affected']} positions affected")
        return stats

    def rebuild_positions_for_account_instrument(self, account: str, instrument: str) -> Dict[str, Any]:
        """
        Rebuild positions for a specific account/instrument combination
        
        Args:
            account: Account identifier
            instrument: Instrument identifier
            
        Returns:
            Dictionary with rebuild statistics for this combination
        """
        logger.info(f"Rebuilding positions for {account}/{instrument}")
        
        # Remove existing positions for this account/instrument
        self._clear_positions_for_account_instrument(account, instrument)
        
        # Get all trades for this account/instrument
        self.cursor.execute("""
            SELECT * FROM trades 
            WHERE account = ? AND instrument = ? AND (deleted = 0 OR deleted IS NULL)
            ORDER BY entry_time
        """, (account, instrument))
        
        trades = [dict(row) for row in self.cursor.fetchall()]
        
        if not trades:
            logger.warning(f"No trades found for {account}/{instrument}")
            return {'positions_created': 0, 'validation_errors': []}
        
        # Process trades using existing algorithm
        result = self._process_trades_for_instrument(trades, account, instrument)
        
        logger.info(f"Rebuilt {result['positions_created']} positions for {account}/{instrument}")
        return result

    def _analyze_trade_impact(self, trade_ids: List[int]) -> List[Tuple[str, str]]:
        """
        Analyze which account/instrument combinations are affected by the given trades
        
        Args:
            trade_ids: List of trade IDs to analyze
            
        Returns:
            List of (account, instrument) tuples that need position rebuilds
        """
        if not trade_ids:
            return []
        
        # Get account/instrument combinations for the given trade IDs
        placeholders = ','.join('?' * len(trade_ids))
        self.cursor.execute(f"""
            SELECT DISTINCT account, instrument 
            FROM trades 
            WHERE id IN ({placeholders}) AND (deleted = 0 OR deleted IS NULL)
        """, trade_ids)
        
        combinations = [(row['account'], row['instrument']) for row in self.cursor.fetchall()]
        logger.debug(f"Trade impact analysis: {len(combinations)} account/instrument combinations affected")
        
        return combinations

    def _clear_positions_for_account_instrument(self, account: str, instrument: str):
        """
        Clear existing positions and position_executions for a specific account/instrument
        
        Args:
            account: Account identifier
            instrument: Instrument identifier
        """
        logger.debug(f"Clearing existing positions for {account}/{instrument}")
        
        # Get position IDs for this account/instrument
        self.cursor.execute("""
            SELECT id FROM positions 
            WHERE account = ? AND instrument = ?
        """, (account, instrument))
        
        position_ids = [row['id'] for row in self.cursor.fetchall()]
        
        if position_ids:
            # Remove position executions first (foreign key constraint)
            placeholders = ','.join('?' * len(position_ids))
            self.cursor.execute(f"""
                DELETE FROM position_executions 
                WHERE position_id IN ({placeholders})
            """, position_ids)
            
            # Remove positions
            self.cursor.execute("""
                DELETE FROM positions 
                WHERE account = ? AND instrument = ?
            """, (account, instrument))
            
            logger.debug(f"Cleared {len(position_ids)} positions for {account}/{instrument}")

    def get_position_executions(self, position_id: int) -> List[Dict[str, Any]]:
        """
        Get all executions that make up a specific position
        
        Args:
            position_id: The position ID to get executions for
            
        Returns:
            List of execution dictionaries with trade details
        """
        self.cursor.execute("""
            SELECT 
                t.*,
                pe.execution_order,
                t.side_of_market,
                t.quantity,
                t.entry_price,
                t.exit_price,
                t.entry_time,
                t.exit_time,
                t.points_gain_loss,
                t.dollars_gain_loss,
                t.commission,
                t.entry_execution_id
            FROM position_executions pe
            JOIN trades t ON pe.trade_id = t.id
            WHERE pe.position_id = ?
            ORDER BY pe.execution_order, t.entry_time
        """, (position_id,))
        
        executions = [dict(row) for row in self.cursor.fetchall()]
        
        logger.debug(f"Found {len(executions)} executions for position {position_id}")
        return executions

    def delete_positions(self, position_ids: List[int]) -> int:
        """
        Delete positions and their associated position_executions records
        
        Args:
            position_ids: List of position IDs to delete
            
        Returns:
            Number of positions actually deleted
        """
        if not position_ids:
            return 0
        
        deleted_count = 0
        
        try:
            # Delete in correct order due to foreign key constraints
            placeholders = ','.join('?' * len(position_ids))
            
            # First delete position_executions records
            self.cursor.execute(f"""
                DELETE FROM position_executions 
                WHERE position_id IN ({placeholders})
            """, position_ids)
            
            deleted_executions = self.cursor.rowcount
            logger.debug(f"Deleted {deleted_executions} position execution records")
            
            # Then delete positions
            self.cursor.execute(f"""
                DELETE FROM positions 
                WHERE id IN ({placeholders})
            """, position_ids)
            
            deleted_count = self.cursor.rowcount
            logger.info(f"Successfully deleted {deleted_count} positions and {deleted_executions} associated execution records")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting positions {position_ids}: {e}")
            raise


def test_enhanced_service():
    """Test function for the enhanced service"""
    print("Testing Enhanced Position Service V2...")
    
    try:
        with EnhancedPositionServiceV2() as service:
            # Test position rebuild
            result = service.rebuild_positions_from_trades()
            print(f"Rebuild result: {result}")
            
            # Test position retrieval
            positions = service.get_positions(page_size=10)
            print(f"Retrieved {len(positions['positions'])} positions")
            
            # Test statistics
            stats = service.get_position_statistics()
            print(f"Statistics: {stats}")
            
        print("✓ Enhanced Position Service V2 test completed successfully")
        
    except Exception as e:
        print(f"✗ Enhanced Position Service V2 test failed: {e}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    test_enhanced_service()