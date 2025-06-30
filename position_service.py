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
            
            # Get all non-deleted trades ordered by account, instrument, and execution ID (chronological without time dependency)
            self.cursor.execute("""
                SELECT * FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY account, instrument, id
            """)
            
            trades = [dict(row) for row in self.cursor.fetchall()]
            
            if not trades:
                return {'positions_created': 0, 'trades_processed': 0}
            
            # Group trades by account and instrument for position tracking
            account_instrument_groups = {}
            for trade in trades:
                # Normalize account and instrument for consistent grouping
                account = (trade.get('account') or '').strip()
                instrument = (trade.get('instrument') or '').strip()
                
                # Skip trades with missing critical fields
                if not account or not instrument:
                    logger.warning(f"Skipping trade with missing account/instrument: {trade.get('entry_execution_id', 'Unknown')}")
                    continue
                
                key = (account, instrument)
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
        """Build position objects from raw execution data using quantity flow analysis
        
        RAW EXECUTION MODEL: Aggregate individual executions into complete positions.
        Track quantity flow from 0 → +/- → 0 to determine position lifecycle.
        """
        logger.info(f"=== BUILDING POSITIONS FOR {account}/{instrument} ===")
        logger.info(f"Processing {len(trades)} raw executions using QUANTITY FLOW MODEL")
        
        # Sort executions by entry time for chronological processing
        trades_sorted = sorted(trades, key=lambda t: t.get('entry_time', ''))
        
        # Log all raw executions for debugging
        for i, trade in enumerate(trades_sorted):
            entry_exit = "Entry" if trade.get('entry_price') == trade.get('exit_price') else "Exit"
            logger.info(f"Raw Execution {i+1}: {trade['side_of_market']} {trade['quantity']} @ ${trade['entry_price']} | Time: {trade.get('entry_time')} | ID: {trade.get('entry_execution_id', 'N/A')}")
        
        # Build positions from execution flow using quantity tracking
        positions = self._aggregate_executions_into_positions(trades_sorted, account, instrument)
        
        logger.info(f"=== POSITION BUILDING COMPLETE ===")
        logger.info(f"Created {len(positions)} positions from {len(trades_sorted)} raw executions")
        return positions
    
    def _aggregate_executions_into_positions(self, executions: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Aggregate raw executions into complete positions using quantity flow tracking
        
        Algorithm: Track running position quantity (0 → +/- → 0)
        - Position starts when quantity goes from 0 to non-zero
        - Position continues while quantity remains non-zero (same direction)
        - Position ends when quantity returns to 0
        """
        if not executions:
            return []
        
        positions = []
        current_position = None
        running_quantity = 0
        
        logger.info(f"Starting quantity flow analysis for {len(executions)} executions")
        
        for i, execution in enumerate(executions):
            # Get raw execution data from NinjaTrader import
            quantity = abs(int(execution.get('quantity', 0)))
            
            # Determine the quantity change effect based on the stored side_of_market
            # The side_of_market field represents the direction of the quantity change
            action = execution.get('side_of_market', '').strip()
            
            # Convert to signed quantity change effect
            if action == 'Long':
                signed_qty_change = quantity  # Adding long contracts (+)
            elif action == 'Short': 
                signed_qty_change = -quantity  # Adding short contracts (-)
            else:
                logger.warning(f"Unknown side_of_market '{action}' for execution {execution.get('entry_execution_id', 'Unknown')}")
                continue
            
            previous_quantity = running_quantity
            running_quantity += signed_qty_change
            
            logger.info(f"Execution {i+1}: {action} {quantity} contracts | Running: {previous_quantity} → {running_quantity}")
            
            # Position lifecycle logic
            if previous_quantity == 0 and running_quantity != 0:
                # Starting new position (0 → non-zero)
                current_position = {
                    'instrument': instrument,
                    'account': account,
                    'position_type': 'Long' if running_quantity > 0 else 'Short',
                    'entry_time': execution.get('entry_time'),
                    'executions': [execution],
                    'total_quantity': abs(running_quantity),
                    'max_quantity': abs(running_quantity),
                    'position_status': 'open',
                    'execution_count': 1
                }
                logger.info(f"  → Started new {current_position['position_type']} position")
                
            elif current_position and running_quantity == 0:
                # Closing position (non-zero → 0)
                current_position['executions'].append(execution)
                current_position['position_status'] = 'closed'
                current_position['execution_count'] = len(current_position['executions'])
                
                # Calculate position totals (this will set correct entry/exit times)
                self._calculate_position_totals_from_executions(current_position)
                
                positions.append(current_position)
                logger.info(f"  → Closed position with {current_position['execution_count']} executions, Total P&L: ${current_position.get('total_dollars_pnl', 0)}")
                
                current_position = None
                
            elif current_position and running_quantity != 0:
                # Modifying existing position (non-zero → non-zero)
                # Since positions never change sides without going to 0, this is always adding to current position
                current_position['executions'].append(execution)
                current_position['total_quantity'] = abs(running_quantity)
                current_position['max_quantity'] = max(current_position['max_quantity'], abs(running_quantity))
                current_position['execution_count'] = len(current_position['executions'])
                
                # Log whether this was adding to or reducing the position
                if abs(running_quantity) > abs(previous_quantity):
                    logger.info(f"  → Added to {current_position['position_type']} position, new quantity: {abs(running_quantity)}")
                else:
                    logger.info(f"  → Reduced {current_position['position_type']} position, new quantity: {abs(running_quantity)}")
        
        # Handle any remaining open position
        if current_position:
            current_position['position_status'] = 'open'
            self._calculate_position_totals_from_executions(current_position)
            positions.append(current_position)
            logger.info(f"  → Saved open position with {current_position['execution_count']} executions")
        
        logger.info(f"Quantity flow analysis complete: {len(positions)} positions created")
        return positions
    
    def _calculate_position_totals_from_executions(self, position: Dict):
        """Calculate position totals from aggregated executions using FIFO methodology"""
        executions = position['executions']
        
        if not executions:
            position.update({
                'average_entry_price': 0,
                'average_exit_price': 0,
                'total_points_pnl': 0,
                'total_dollars_pnl': 0,
                'total_commission': 0,
                'risk_reward_ratio': 0
            })
            return
        
        # Set actual entry and exit times from first and last executions
        if executions:
            # Sort executions by entry_time to get chronological order
            sorted_executions = sorted(executions, key=lambda x: x.get('entry_time', ''))
            position['entry_time'] = sorted_executions[0].get('entry_time')
            
            # For closed positions, set exit time to the last execution
            if position['position_status'] == 'closed':
                position['exit_time'] = sorted_executions[-1].get('entry_time')
        
        # Separate entry and exit executions based on position direction
        # For a Long position: Long side_of_market = entries, Short side_of_market = exits
        # For a Short position: Short side_of_market = entries, Long side_of_market = exits
        entries = []
        exits = []
        
        for execution in executions:
            side = execution.get('side_of_market', '').strip()
            if position['position_type'] == 'Long':
                # Long position: Long actions add to position, Short actions reduce position
                if side == 'Long':
                    entries.append(execution)
                elif side == 'Short':
                    exits.append(execution)
            else:  # Short position
                # Short position: Short actions add to position, Long actions reduce position
                if side == 'Short':
                    entries.append(execution)
                elif side == 'Long':
                    exits.append(execution)
        
        # Calculate averages and totals
        total_entry_quantity = sum(int(e.get('quantity', 0)) for e in entries)
        total_exit_quantity = sum(int(e.get('quantity', 0)) for e in exits)
        
        # Weighted average entry price
        if entries and total_entry_quantity > 0:
            weighted_entry = sum(float(e.get('entry_price', 0)) * int(e.get('quantity', 0)) for e in entries)
            position['average_entry_price'] = weighted_entry / total_entry_quantity
        else:
            position['average_entry_price'] = 0
        
        # Weighted average exit price
        if exits and total_exit_quantity > 0:
            weighted_exit = sum(float(e.get('entry_price', 0)) * int(e.get('quantity', 0)) for e in exits)
            position['average_exit_price'] = weighted_exit / total_exit_quantity
        else:
            position['average_exit_price'] = position['average_entry_price']
        
        # Calculate P&L for closed positions
        if position['position_status'] == 'closed' and total_entry_quantity > 0 and total_exit_quantity > 0:
            # Use minimum quantity for P&L calculation (handles partial exits)
            pnl_quantity = min(total_entry_quantity, total_exit_quantity)
            
            if position['position_type'] == 'Long':
                points_pnl = position['average_exit_price'] - position['average_entry_price']
            else:  # Short
                points_pnl = position['average_entry_price'] - position['average_exit_price']
            
            position['total_points_pnl'] = points_pnl
            
            # Calculate dollar P&L (need instrument multiplier - assume $20 for MNQ)
            # TODO: Get actual multiplier from config
            multiplier = 20  # MNQ standard multiplier
            position['total_dollars_pnl'] = points_pnl * multiplier * pnl_quantity
        else:
            position['total_points_pnl'] = 0
            position['total_dollars_pnl'] = 0
        
        # Total commission
        position['total_commission'] = sum(float(e.get('commission', 0)) for e in executions)
        
        # Risk/reward ratio
        if position['total_dollars_pnl'] != 0 and position['total_commission'] > 0:
            if position['total_dollars_pnl'] > 0:
                position['risk_reward_ratio'] = abs(position['total_dollars_pnl']) / position['total_commission']
            else:
                position['risk_reward_ratio'] = position['total_commission'] / abs(position['total_dollars_pnl'])
        else:
            position['risk_reward_ratio'] = 0
    
    def _convert_completed_trades_to_positions(self, trades: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Convert completed trades into position records (1:1 mapping)
        
        PURE COMPLETED TRADE MODEL: Each completed trade = one position
        No complex position building needed - trades already have proper entry/exit and P&L
        """
        if not trades:
            return []
        
        logger.info(f"Converting {len(trades)} completed trades to positions")
        
        # Validate that these are indeed completed trades
        self._validate_completed_trades(trades)
        
        positions = []
        skipped_trades = 0
        
        for i, trade in enumerate(trades):
            # Validate individual trade
            if not self._validate_trade_data(trade):
                skipped_trades += 1
                logger.warning(f"Skipping invalid trade {i+1}: {trade.get('entry_execution_id', 'Unknown ID')}")
                continue
                
            # Each completed trade becomes its own position
            position = {
                'instrument': instrument,
                'account': account,
                'position_type': trade['side_of_market'],  # 'Long' or 'Short'
                'entry_time': trade['entry_time'],
                'exit_time': trade.get('exit_time') or trade['entry_time'],  # Use actual exit time
                'executions': [trade],  # Single trade = single execution in position
                'total_quantity': trade['quantity'],
                'max_quantity': trade['quantity'],
                'position_status': 'closed',  # Completed trades are always closed
                'execution_count': 1
            }
            
            # Calculate position totals (sets average prices and P&L from trade data)
            self._calculate_position_totals_from_completed_trade(position)
            
            positions.append(position)
            
            if (i + 1) % 50 == 0:  # Log progress every 50 positions
                logger.info(f"Converted {i + 1}/{len(trades)} completed trades to positions...")
        
        if skipped_trades > 0:
            logger.warning(f"Skipped {skipped_trades} invalid trades out of {len(trades)} total")
            
        logger.info(f"Successfully converted {len(positions)} completed trades to positions")
        return positions
    
    def _validate_completed_trades(self, trades: List[Dict]):
        """Validate that trades are properly formatted completed trades"""
        if not trades:
            return
            
        completed_count = 0
        for trade in trades[:10]:  # Sample first 10 trades for validation
            if (trade.get('exit_price') and 
                trade.get('entry_price') and 
                trade.get('exit_price') != trade.get('entry_price') and
                trade.get('dollars_gain_loss') is not None):
                completed_count += 1
        
        completion_ratio = completed_count / min(len(trades), 10)
        
        if completion_ratio < 0.8:
            logger.warning(f"Only {completion_ratio:.1%} of sampled trades appear to be completed trades. Expected completed trade format with entry/exit prices and P&L.")
        else:
            logger.info(f"Validated {completion_ratio:.1%} of sampled trades are properly formatted completed trades")
    
    def _validate_trade_data(self, trade: Dict) -> bool:
        """Validate individual trade has required fields"""
        required_fields = ['instrument', 'side_of_market', 'quantity', 'entry_price', 'entry_time', 'dollars_gain_loss']
        
        for field in required_fields:
            if field not in trade or trade[field] is None:
                logger.error(f"Trade missing required field '{field}': {trade.get('entry_execution_id', 'Unknown ID')}")
                return False
        
        # Validate data types and ranges
        try:
            quantity = int(trade['quantity'])
            entry_price = float(trade['entry_price'])
            
            if quantity <= 0:
                logger.error(f"Invalid quantity {quantity} for trade {trade.get('entry_execution_id', 'Unknown ID')}")
                return False
                
            if entry_price <= 0:
                logger.error(f"Invalid entry price {entry_price} for trade {trade.get('entry_execution_id', 'Unknown ID')}")
                return False
                
        except (ValueError, TypeError) as e:
            logger.error(f"Data type validation failed for trade {trade.get('entry_execution_id', 'Unknown ID')}: {e}")
            return False
        
        return True
    
    # ARCHITECTURAL CHANGE COMPLETE: Position service now uses PURE COMPLETED TRADE MODEL
    # - Each trade record (from ExecutionProcessing.py) = one complete position  
    # - No complex quantity-based position building or routing logic needed
    # - Consistent 1:1 mapping from completed trades to position records
    
    
    def _calculate_position_totals_from_completed_trade(self, position: Dict):
        """Calculate position totals from a completed trade record
        
        PURE COMPLETED TRADE MODEL: Trade already has calculated entry/exit prices and P&L.
        Simply extract the values from the completed trade - no complex calculations needed.
        """
        executions = position['executions']
        
        if not executions:
            return
        
        # For completed trades, there's only one execution (the completed trade record)
        trade = executions[0]
        
        # Extract pre-calculated values from the completed trade
        position['average_entry_price'] = trade['entry_price']
        position['average_exit_price'] = trade.get('exit_price', trade['entry_price'])
        position['total_points_pnl'] = trade.get('points_gain_loss', 0)
        position['total_dollars_pnl'] = trade['dollars_gain_loss']
        position['total_commission'] = trade['commission']
        position['execution_count'] = 1
        
        # Calculate risk/reward ratio for completed positions
        if position['total_dollars_pnl'] != 0 and position['total_commission'] > 0:
            if position['total_dollars_pnl'] > 0:
                # Winning trade: reward/risk ratio
                position['risk_reward_ratio'] = abs(position['total_dollars_pnl']) / position['total_commission']
            else:
                # Losing trade: risk/reward ratio
                position['risk_reward_ratio'] = position['total_commission'] / abs(position['total_dollars_pnl'])
        else:
            position['risk_reward_ratio'] = 0
    
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
            
            # Soft delete the associated trades (mark as deleted instead of removing)
            if trade_ids:
                trade_placeholders = ','.join(['?'] * len(trade_ids))
                
                # Check which trades are still linked to other positions
                self.cursor.execute(f"""
                    SELECT DISTINCT trade_id FROM position_executions 
                    WHERE trade_id IN ({trade_placeholders})
                """, trade_ids)
                
                still_linked_trades = [row[0] for row in self.cursor.fetchall()]
                
                # Soft delete trades that are no longer linked to any positions
                orphaned_trades = [tid for tid in trade_ids if tid not in still_linked_trades]
                
                if orphaned_trades:
                    orphaned_placeholders = ','.join(['?'] * len(orphaned_trades))
                    self.cursor.execute(f"""
                        UPDATE trades SET deleted = 1
                        WHERE id IN ({orphaned_placeholders})
                    """, orphaned_trades)
                    
                    logger.info(f"Soft deleted {len(orphaned_trades)} orphaned trades along with positions")
            
            self.conn.commit()
            logger.info(f"Successfully deleted {deleted_positions} positions and their executions")
            
            return deleted_positions
            
        except Exception as e:
            logger.error(f"Error deleting positions: {e}")
            self.conn.rollback()
            return 0