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
        """Build position objects by grouping related trade records (corrected logic)"""
        logger.info(f"=== BUILDING POSITIONS FOR {account}/{instrument} ===")
        logger.info(f"Processing {len(trades)} trade records")
        
        # Log all trades first for debugging
        for i, trade in enumerate(trades):
            logger.info(f"Trade {i+1}: {trade['side_of_market']} {trade['quantity']} @ ${trade['entry_price']} -> ${trade['exit_price']} | P&L: ${trade['dollars_gain_loss']} | ID: {trade['entry_execution_id']}")
        
        # Group related trades that belong to the same original position
        position_groups = self._group_related_trades(trades)
        logger.info(f"Grouped {len(trades)} trades into {len(position_groups)} position groups")
        
        positions = []
        for i, group in enumerate(position_groups):
            logger.info(f"\n--- Building Position {i+1} from {len(group)} trade records ---")
            position = self._create_position_from_trade_group(group, account, instrument)
            positions.append(position)
            logger.info(f"Created position: {position['position_type']} {position['total_quantity']} contracts, P&L: ${position['total_dollars_pnl']:.2f}")
        
        logger.info(f"=== POSITION BUILDING COMPLETE ===")
        logger.info(f"Created {len(positions)} positions from {len(trades)} trade records")
        return positions
    
    def _group_related_trades(self, trades: List[Dict]) -> List[List[Dict]]:
        """Group trade records that belong to the same original position - Enhanced Aggregation"""
        if not trades:
            return []
        
        logger.info(f"Grouping {len(trades)} trades...")
        
        # Strategy 1: Group by link_group_id if available
        linked_groups = {}
        unlinked_trades = []
        
        for trade in trades:
            link_group_id = trade.get('link_group_id')
            if link_group_id:
                if link_group_id not in linked_groups:
                    linked_groups[link_group_id] = []
                linked_groups[link_group_id].append(trade)
                logger.info(f"Trade {trade['entry_execution_id']} added to link group {link_group_id}")
            else:
                unlinked_trades.append(trade)
        
        # Strategy 2: Aggressive time-based position grouping
        # Group by account, instrument, side, and close entry times (within 5 minutes)
        position_groups = self._group_by_position_lifecycle(unlinked_trades)
        
        # Combine all groups
        final_groups = []
        
        # Add linked groups
        for group_trades in linked_groups.values():
            final_groups.append(group_trades)
            logger.info(f"Added linked group with {len(group_trades)} trades")
        
        # Add position lifecycle groups
        final_groups.extend(position_groups)
        
        logger.info(f"Final grouping: {len(final_groups)} position groups")
        return final_groups
    
    def _group_by_position_lifecycle(self, trades: List[Dict]) -> List[List[Dict]]:
        """Group trades by position lifecycle - account, instrument, side, and time proximity"""
        if not trades:
            return []
        
        logger.info(f"Grouping {len(trades)} trades by position lifecycle...")
        
        # Sort trades by account, instrument, side, entry time
        trades_sorted = sorted(trades, key=lambda t: (
            t['account'], 
            t['instrument'], 
            t['side_of_market'], 
            t['entry_time']
        ))
        
        groups = []
        current_group = []
        current_account = None
        current_instrument = None
        current_side = None
        current_time_window = None
        
        for trade in trades_sorted:
            account = trade['account']
            instrument = trade['instrument']
            side = trade['side_of_market']
            entry_time = trade['entry_time']
            
            # Parse entry time for comparison
            try:
                from datetime import datetime, timedelta
                trade_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            except:
                # Fallback to string comparison
                trade_dt = entry_time
            
            # Check if this trade belongs to the current group
            should_start_new_group = False
            
            if current_group == []:
                # First trade
                should_start_new_group = False
            elif (account != current_account or 
                  instrument != current_instrument or 
                  side != current_side):
                # Different account, instrument, or side
                should_start_new_group = True
            elif isinstance(trade_dt, datetime) and isinstance(current_time_window, datetime):
                # Check if trade is within 5 minutes of the current group
                time_diff = abs((trade_dt - current_time_window).total_seconds())
                if time_diff > 300:  # 5 minutes
                    should_start_new_group = True
            elif entry_time != current_time_window:
                # Fallback string comparison
                should_start_new_group = True
            
            if should_start_new_group and current_group:
                # Save current group and start new one
                groups.append(current_group)
                logger.info(f"Created position group: {len(current_group)} trades for {current_account} {current_side} {current_instrument}")
                current_group = []
            
            # Add trade to current group
            current_group.append(trade)
            current_account = account
            current_instrument = instrument
            current_side = side
            current_time_window = trade_dt if isinstance(trade_dt, datetime) else entry_time
        
        # Add final group
        if current_group:
            groups.append(current_group)
            logger.info(f"Created final position group: {len(current_group)} trades for {current_account} {current_side} {current_instrument}")
        
        logger.info(f"Position lifecycle grouping: {len(trades)} trades -> {len(groups)} position groups")
        return groups
    
    def _group_by_time_and_side(self, trades: List[Dict]) -> List[List[Dict]]:
        """Group trades by entry time and side to separate distinct positions"""
        if not trades:
            return []
        
        # Sort by entry time
        trades_sorted = sorted(trades, key=lambda t: t['entry_time'])
        
        groups = []
        current_group = []
        current_time = None
        current_side = None
        
        for trade in trades_sorted:
            trade_time = trade['entry_time']
            trade_side = trade['side_of_market']
            
            # If this is the first trade or matches current group criteria
            if (current_time is None or 
                trade_time == current_time and trade_side == current_side):
                current_group.append(trade)
                current_time = trade_time
                current_side = trade_side
            else:
                # Start new group
                if current_group:
                    groups.append(current_group)
                current_group = [trade]
                current_time = trade_time
                current_side = trade_side
        
        # Add final group
        if current_group:
            groups.append(current_group)
        
        logger.info(f"Time/side grouping: {len(trades)} trades -> {len(groups)} groups")
        return groups
    
    def _create_position_from_trade_group(self, trades: List[Dict], account: str, instrument: str) -> Dict:
        """Create a position object from a group of related trade records"""
        if not trades:
            return None
        
        # All trades in group should have same side (Long/Short)
        position_type = trades[0]['side_of_market']
        
        # Calculate total position size by summing all trade quantities
        total_quantity = sum(trade['quantity'] for trade in trades)
        
        # Find earliest entry time and latest exit time
        entry_times = [trade['entry_time'] for trade in trades]
        exit_times = [trade['exit_time'] for trade in trades if trade['exit_time']]
        
        position = {
            'instrument': instrument,
            'account': account,
            'position_type': position_type,
            'entry_time': min(entry_times),
            'exit_time': max(exit_times) if exit_times else None,
            'executions': trades,
            'total_quantity': total_quantity,
            'max_quantity': total_quantity,  # For now, assume this is the max
            'position_status': 'closed' if exit_times else 'open',
            'execution_count': len(trades),
            'total_points_pnl': 0,
            'total_dollars_pnl': 0,
            'total_commission': 0
        }
        
        # Calculate totals
        self._calculate_position_totals(position)
        
        logger.info(f"Created {position_type} position: {total_quantity} contracts from {len(trades)} trade records")
        return position
    
    def _calculate_position_totals(self, position: Dict):
        """Calculate totals for a position from its executions"""
        executions = position['executions']
        
        if not executions:
            return
        
        # Calculate weighted average prices
        total_entry_value = sum(ex['entry_price'] * ex['quantity'] for ex in executions)
        total_quantity = sum(ex['quantity'] for ex in executions)
        position['average_entry_price'] = total_entry_value / total_quantity if total_quantity > 0 else 0
        
        if position['position_status'] == 'closed':
            total_exit_value = sum(ex['exit_price'] * ex['quantity'] for ex in executions)
            position['average_exit_price'] = total_exit_value / total_quantity if total_quantity > 0 else 0
            
            # Calculate position-level points P&L using average prices
            if position['position_type'] == 'Long':
                position['total_points_pnl'] = position['average_exit_price'] - position['average_entry_price']
            else:  # Short
                position['total_points_pnl'] = position['average_entry_price'] - position['average_exit_price']
        else:
            # Open position - no points P&L yet
            position['total_points_pnl'] = 0
        
        # Sum P&L and commission from individual executions
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