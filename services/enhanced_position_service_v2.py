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
            WHERE soft_deleted = 0 
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
        
        # Convert trades to execution format expected by algorithms
        executions = []
        for trade in trades:
            executions.append({
                'id': trade['id'],
                'instrument': trade['instrument'],
                'account': trade['account'],
                'side_of_market': trade['side_of_market'],
                'quantity': trade['quantity'],
                'entry_price': trade['entry_price'],
                'exit_price': trade['exit_price'],
                'entry_time': datetime.fromisoformat(trade['entry_time']) if isinstance(trade['entry_time'], str) else trade['entry_time'],
                'commission': trade.get('commission', 0)
            })
        
        # Calculate quantity flows
        quantity_flows = calculate_running_quantity(executions)
        
        # Validate boundaries
        validation_errors = validate_position_boundaries(quantity_flows)
        if validation_errors:
            logger.warning(f"Validation errors for {account}/{instrument}: {validation_errors}")
        
        # Group into positions
        position_groups = group_executions_by_position(quantity_flows)
        
        positions_created = 0
        for position_flows in position_groups:
            try:
                # Calculate P&L if position is closed
                if position_flows[-1].running_quantity == 0:
                    # Get instrument multiplier
                    multiplier = self._get_instrument_multiplier(instrument)
                    pnl_data = calculate_position_pnl(position_flows, Decimal(str(multiplier)))
                else:
                    pnl_data = {'error': 'Position is still open'}
                
                # Create position summary
                summary = create_position_summary(position_flows, pnl_data)
                
                # Save position to database
                position_id = self._save_enhanced_position(summary, position_flows)
                if position_id:
                    positions_created += 1
                    
            except Exception as e:
                logger.error(f"Failed to create position from flows: {e}")
                validation_errors.append(f"Position creation failed: {str(e)}")
        
        return {
            'positions_created': positions_created,
            'validation_errors': validation_errors
        }
    
    def _get_instrument_multiplier(self, instrument: str) -> float:
        """Get instrument multiplier for P&L calculations"""
        # Load from config or use default
        try:
            from config import config
            import json
            with open(config.instrument_config, 'r') as f:
                multipliers = json.load(f)
            return float(multipliers.get(instrument, 1.0))
        except Exception as e:
            logger.warning(f"Could not load multiplier for {instrument}: {e}")
            return 1.0
    
    def _save_enhanced_position(self, summary: Dict, flows: List) -> Optional[int]:
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