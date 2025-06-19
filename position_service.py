"""
Position Service - Aggregates individual trades into position-based view
Transforms execution-based data into position lifecycle tracking
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

# Get logger
logger = logging.getLogger('position_service')


class PositionService:
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
        """Rebuild all positions from existing trades data using position flow analysis"""
        try:
            # Clear existing positions
            self.cursor.execute("DELETE FROM positions")
            self.cursor.execute("DELETE FROM position_executions")
            
            # Get all trades ordered by account, instrument, and time
            self.cursor.execute("""
                SELECT * FROM trades 
                ORDER BY account, instrument, entry_time, exit_time
            """)
            
            trades = [dict(row) for row in self.cursor.fetchall()]
            
            if not trades:
                return {'positions_created': 0, 'trades_processed': 0}
            
            # Group trades by account and instrument for position tracking
            account_instrument_groups = {}
            for trade in trades:
                key = (trade['account'], trade['instrument'])
                if key not in account_instrument_groups:
                    account_instrument_groups[key] = []
                account_instrument_groups[key].append(trade)
            
            positions_created = 0
            trades_processed = 0
            
            # Process each account-instrument combination
            for (account, instrument), group_trades in account_instrument_groups.items():
                logger.info(f"Processing {len(group_trades)} trades for {account}/{instrument}")
                
                # Build positions from execution flow
                positions = self._build_positions_from_execution_flow(group_trades, account, instrument)
                
                # Save positions to database
                for position in positions:
                    position_id = self._save_position(position)
                    if position_id:
                        positions_created += 1
                        trades_processed += len(position['executions'])
            
            self.conn.commit()
            logger.info(f"Rebuild complete: {positions_created} positions created from {trades_processed} trades")
            
            return {
                'positions_created': positions_created,
                'trades_processed': trades_processed
            }
            
        except Exception as e:
            logger.error(f"Error rebuilding positions: {e}")
            self.conn.rollback()
            return {'positions_created': 0, 'trades_processed': 0}
    
    def _build_positions_from_execution_flow(self, trades: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Build position objects based on quantity-based position lifecycle (0 -> +/- -> 0)"""
        logger.info(f"=== BUILDING POSITIONS FOR {account}/{instrument} ===")
        logger.info(f"Processing {len(trades)} trade records")
        
        # Sort trades by entry time to process in chronological order
        trades_sorted = sorted(trades, key=lambda t: t['entry_time'])
        
        # Log all trades first for debugging
        for i, trade in enumerate(trades_sorted):
            logger.info(f"Trade {i+1}: {trade['side_of_market']} {trade['quantity']} @ ${trade['entry_price']} -> ${trade['exit_price']} | P&L: ${trade['dollars_gain_loss']} | ID: {trade['entry_execution_id']}")
        
        # Track position based on contract quantity changes
        positions = self._track_quantity_based_positions(trades_sorted, account, instrument)
        
        logger.info(f"=== POSITION BUILDING COMPLETE ===")
        logger.info(f"Created {len(positions)} positions from {len(trades_sorted)} trade records")
        return positions
    
    def _track_quantity_based_positions(self, trades: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Track positions based purely on contract quantity changes (0 -> +/- -> 0)"""
        if not trades:
            return []
        
        logger.info(f"Tracking quantity-based positions for {len(trades)} trades...")
        
        positions = []
        current_position = None
        current_quantity = 0
        
        for i, trade in enumerate(trades):
            # Determine quantity change based on side
            if trade['side_of_market'] == 'Long':
                quantity_change = trade['quantity']
            else:  # Short
                quantity_change = -trade['quantity']
            
            # Calculate new position quantity
            new_quantity = current_quantity + quantity_change
            
            logger.info(f"Trade {i+1}: {trade['side_of_market']} {trade['quantity']} | Position: {current_quantity} -> {new_quantity}")
            
            # Start new position if we're going from 0 to non-zero
            if current_quantity == 0 and new_quantity != 0:
                logger.info(f"Starting new position: {new_quantity} contracts")
                current_position = {
                    'instrument': instrument,
                    'account': account,
                    'position_type': 'Long' if new_quantity > 0 else 'Short',
                    'entry_time': trade['entry_time'],
                    'exit_time': None,
                    'executions': [trade],
                    'total_quantity': abs(new_quantity),
                    'max_quantity': abs(new_quantity),
                    'position_status': 'open',
                    'execution_count': 1
                }
            
            # Add execution to current position if position exists
            elif current_position is not None:
                current_position['executions'].append(trade)
                current_position['execution_count'] += 1
                current_position['max_quantity'] = max(current_position['max_quantity'], abs(new_quantity))
                
                # Close position if we're back to 0
                if new_quantity == 0:
                    logger.info(f"Closing position: {current_quantity} -> 0")
                    current_position['exit_time'] = trade['exit_time'] or trade['entry_time']
                    current_position['position_status'] = 'closed'
                    
                    # Calculate position totals
                    self._calculate_position_totals(current_position)
                    
                    # Save position and reset
                    positions.append(current_position)
                    logger.info(f"Position closed: {current_position['position_type']} {current_position['total_quantity']} contracts, P&L: ${current_position['total_dollars_pnl']:.2f}")
                    current_position = None
            
            # Update current quantity
            current_quantity = new_quantity
        
        # Handle any remaining open position
        if current_position is not None:
            logger.info(f"Open position remains: {current_position['position_type']} {abs(current_quantity)} contracts")
            self._calculate_position_totals(current_position)
            positions.append(current_position)
        
        logger.info(f"Created {len(positions)} positions from quantity tracking")
        return positions
    
    
    def _calculate_position_totals(self, position: Dict):
        """Calculate totals for a position from its executions using proper FIFO accounting"""
        executions = position['executions']
        
        if not executions:
            return
        
        # Separate entry and exit executions based on position flow
        entry_executions = []
        exit_executions = []
        running_quantity = 0
        
        for execution in executions:
            if position['position_type'] == 'Long':
                if execution['side_of_market'] == 'Long':
                    # Long execution adds to long position
                    entry_executions.append(execution)
                else:
                    # Short execution reduces long position
                    exit_executions.append(execution)
            else:  # Short position
                if execution['side_of_market'] == 'Short':
                    # Short execution adds to short position 
                    entry_executions.append(execution)
                else:
                    # Long execution reduces short position
                    exit_executions.append(execution)
        
        # Calculate average entry price from entry executions
        if entry_executions:
            total_entry_value = sum(ex['entry_price'] * ex['quantity'] for ex in entry_executions)
            total_entry_quantity = sum(ex['quantity'] for ex in entry_executions)
            position['average_entry_price'] = total_entry_value / total_entry_quantity if total_entry_quantity > 0 else 0
        else:
            position['average_entry_price'] = 0
        
        # Calculate average exit price from exit executions if position is closed
        if position['position_status'] == 'closed' and exit_executions:
            total_exit_value = sum(ex['exit_price'] * ex['quantity'] for ex in exit_executions)
            total_exit_quantity = sum(ex['quantity'] for ex in exit_executions)
            position['average_exit_price'] = total_exit_value / total_exit_quantity if total_exit_quantity > 0 else 0
            
            # Calculate position-level points P&L using average prices
            if position['position_type'] == 'Long':
                position['total_points_pnl'] = position['average_exit_price'] - position['average_entry_price']
            else:  # Short
                position['total_points_pnl'] = position['average_entry_price'] - position['average_exit_price']
        else:
            # Open position - no exit price or points P&L yet
            position['average_exit_price'] = None
            position['total_points_pnl'] = 0
        
        # Sum P&L and commission from all executions
        position['total_dollars_pnl'] = sum(ex['dollars_gain_loss'] for ex in executions)
        position['total_commission'] = sum(ex['commission'] for ex in executions)
        position['execution_count'] = len(executions)
        
        # Calculate risk/reward ratio for closed positions
        if position['position_status'] == 'closed' and position['total_dollars_pnl'] != 0:
            # Simple R:R based on total P&L
            if position['total_dollars_pnl'] > 0:
                position['risk_reward_ratio'] = abs(position['total_dollars_pnl']) / position['total_commission'] if position['total_commission'] > 0 else 0
            else:
                position['risk_reward_ratio'] = position['total_commission'] / abs(position['total_dollars_pnl']) if position['total_dollars_pnl'] != 0 else 0
    
    def _save_position(self, position: Dict) -> Optional[int]:
        """Save a position to the database and return the position ID"""
        try:
            # Insert position
            self.cursor.execute("""
                INSERT INTO positions (
                    instrument, account, position_type, entry_time, exit_time,
                    total_quantity, average_entry_price, average_exit_price,
                    total_points_pnl, total_dollars_pnl, total_commission,
                    position_status, execution_count, risk_reward_ratio, max_quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position['instrument'],
                position['account'],
                position['position_type'],
                position['entry_time'],
                position['exit_time'],
                position['total_quantity'],
                position['average_entry_price'],
                position.get('average_exit_price'),
                position['total_points_pnl'],
                position['total_dollars_pnl'],
                position['total_commission'],
                position['position_status'],
                position['execution_count'],
                position.get('risk_reward_ratio'),
                position['max_quantity']
            ))
            
            position_id = self.cursor.lastrowid
            
            # Link executions to position
            for i, execution in enumerate(position['executions']):
                self.cursor.execute("""
                    INSERT INTO position_executions (position_id, trade_id, execution_order)
                    VALUES (?, ?, ?)
                """, (position_id, execution['id'], i + 1))
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error saving position: {e}")
            return None
    
    def get_positions(self, page_size: int = 50, page: int = 1, 
                     account: Optional[str] = None, instrument: Optional[str] = None,
                     status: Optional[str] = None, sort_by: str = 'entry_time',
                     sort_order: str = 'DESC') -> Tuple[List[Dict], int, int]:
        """Get positions with filtering and pagination"""
        try:
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
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Get total count
            self.cursor.execute(f"SELECT COUNT(*) FROM positions WHERE {where_clause}", params)
            total_count = self.cursor.fetchone()[0]
            total_pages = (total_count + page_size - 1) // page_size
            
            # Get positions
            offset = (page - 1) * page_size
            allowed_sort_fields = {'entry_time', 'exit_time', 'instrument', 'total_dollars_pnl', 'account'}
            sort_by = sort_by if sort_by in allowed_sort_fields else 'entry_time'
            sort_order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
            
            query = f"""
                SELECT * FROM positions 
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            
            self.cursor.execute(query, params + [page_size, offset])
            positions = [dict(row) for row in self.cursor.fetchall()]
            
            return positions, total_count, total_pages
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return [], 0, 0
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict]:
        """Get a position by ID with its executions"""
        try:
            # Get position
            self.cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
            position_row = self.cursor.fetchone()
            
            if not position_row:
                return None
            
            position = dict(position_row)
            
            # Get executions for this position
            self.cursor.execute("""
                SELECT t.*, pe.execution_order
                FROM trades t
                JOIN position_executions pe ON t.id = pe.trade_id
                WHERE pe.position_id = ?
                ORDER BY pe.execution_order
            """, (position_id,))
            
            executions = [dict(row) for row in self.cursor.fetchall()]
            position['executions'] = executions
            
            return position
            
        except Exception as e:
            logger.error(f"Error getting position by ID: {e}")
            return None
    
    def get_position_statistics(self, account: Optional[str] = None) -> Dict[str, Any]:
        """Get position-based statistics"""
        try:
            where_conditions = []
            params = []
            
            if account:
                where_conditions.append("account = ?")
                params.append(account)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            self.cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(CASE WHEN position_status = 'closed' THEN 1 ELSE 0 END) as closed_positions,
                    SUM(CASE WHEN position_status = 'open' THEN 1 ELSE 0 END) as open_positions,
                    SUM(CASE WHEN total_dollars_pnl > 0 THEN 1 ELSE 0 END) as winning_positions,
                    SUM(total_dollars_pnl) as total_pnl,
                    AVG(total_dollars_pnl) as avg_pnl,
                    SUM(total_commission) as total_commission,
                    AVG(execution_count) as avg_executions_per_position,
                    COUNT(DISTINCT instrument) as instruments_traded,
                    COUNT(DISTINCT account) as accounts_traded
                FROM positions
                WHERE {where_clause}
            """, params)
            
            row = self.cursor.fetchone()
            stats = dict(row) if row else {}
            
            # Calculate win rate
            total_closed = stats.get('closed_positions', 0)
            winning = stats.get('winning_positions', 0)
            stats['win_rate'] = (winning / total_closed * 100) if total_closed > 0 else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting position statistics: {e}")
            return {}
    
    def delete_positions(self, position_ids: List[int]) -> int:
        """Delete positions and their associated executions"""
        try:
            if not position_ids:
                return 0
            
            # First, get the trade IDs associated with these positions
            placeholders = ','.join(['?'] * len(position_ids))
            
            self.cursor.execute(f"""
                SELECT trade_id FROM position_executions 
                WHERE position_id IN ({placeholders})
            """, position_ids)
            
            trade_ids = [row[0] for row in self.cursor.fetchall()]
            
            # Delete from position_executions table
            self.cursor.execute(f"""
                DELETE FROM position_executions 
                WHERE position_id IN ({placeholders})
            """, position_ids)
            
            # Delete from positions table
            self.cursor.execute(f"""
                DELETE FROM positions 
                WHERE id IN ({placeholders})
            """, position_ids)
            
            deleted_positions = self.cursor.rowcount
            
            # Optionally delete the associated trades if they're no longer linked to any positions
            # This is a design choice - you might want to keep the raw trades for audit purposes
            if trade_ids:
                trade_placeholders = ','.join(['?'] * len(trade_ids))
                
                # Check which trades are still linked to other positions
                self.cursor.execute(f"""
                    SELECT DISTINCT trade_id FROM position_executions 
                    WHERE trade_id IN ({trade_placeholders})
                """, trade_ids)
                
                still_linked_trades = [row[0] for row in self.cursor.fetchall()]
                
                # Delete trades that are no longer linked to any positions
                orphaned_trades = [tid for tid in trade_ids if tid not in still_linked_trades]
                
                if orphaned_trades:
                    orphaned_placeholders = ','.join(['?'] * len(orphaned_trades))
                    self.cursor.execute(f"""
                        DELETE FROM trades 
                        WHERE id IN ({orphaned_placeholders})
                    """, orphaned_trades)
                    
                    logger.info(f"Deleted {len(orphaned_trades)} orphaned trades along with positions")
            
            self.conn.commit()
            logger.info(f"Successfully deleted {deleted_positions} positions and their executions")
            
            return deleted_positions
            
        except Exception as e:
            logger.error(f"Error deleting positions: {e}")
            self.conn.rollback()
            return 0