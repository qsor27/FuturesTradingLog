"""
Position Building Tasks

Celery tasks for position building and rebuilding.
Uses the new position engine for bulletproof position creation.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from celery import Task
from celery_app import app
from config import config
from scripts.database_manager import DatabaseManager
from services.position_engine import PositionEngine
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2

logger = logging.getLogger('position_building')


class CallbackTask(Task):
    """Base task class with error handling and monitoring"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f'Position building task {task_id} failed: {exc}')
        logger.error(f'Exception info: {einfo}')
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f'Position building task {task_id} completed successfully')


@app.task(base=CallbackTask, bind=True)
def rebuild_all_positions(self):
    """
    Rebuild all positions from scratch using the new position engine
    This is a heavy operation and should be used sparingly
    """
    try:
        logger.info("Starting full position rebuild")
        
        with DatabaseManager() as db:
            # Get all non-deleted trades
            trades_query = """
                SELECT * FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY account, instrument, entry_time
            """
            
            result = db.cursor.execute(trades_query)
            raw_executions = [dict(row) for row in result.fetchall()]
            
            if not raw_executions:
                logger.info("No trades found for position building")
                return {'status': 'no_trades', 'positions_created': 0}
            
            logger.info(f"Processing {len(raw_executions)} executions for position building")
            
            # Use the new position engine
            positions = PositionEngine.build_positions_from_executions(raw_executions)
            
            # Clear existing positions
            db.cursor.execute("DELETE FROM positions")
            db.cursor.execute("DELETE FROM position_executions")
            
            # Save new positions to database
            positions_created = 0
            for position in positions:
                position_id = _save_position_to_database(db, position)
                if position_id:
                    positions_created += 1
                    # Link executions to position
                    _link_executions_to_position(db, position_id, position.executions)
            
            db.commit()
            
            logger.info(f"Position rebuild completed: {positions_created} positions created from {len(raw_executions)} executions")
            
            return {
                'status': 'success',
                'positions_created': positions_created,
                'executions_processed': len(raw_executions)
            }
            
    except Exception as e:
        logger.error(f"Error in rebuild_all_positions: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


@app.task(base=CallbackTask, bind=True)
def rebuild_positions_for_account(self, account: str):
    """
    Rebuild positions for a specific account
    
    Args:
        account: Account name to rebuild positions for
    """
    try:
        logger.info(f"Rebuilding positions for account: {account}")
        
        with DatabaseManager() as db:
            # Get trades for this account
            trades_query = """
                SELECT * FROM trades 
                WHERE account = ? AND (deleted = 0 OR deleted IS NULL)
                ORDER BY instrument, entry_time
            """
            
            result = db.cursor.execute(trades_query, (account,))
            raw_executions = [dict(row) for row in result.fetchall()]
            
            if not raw_executions:
                logger.info(f"No trades found for account: {account}")
                return {'status': 'no_trades', 'account': account, 'positions_created': 0}
            
            logger.info(f"Processing {len(raw_executions)} executions for account {account}")
            
            # Use the new position engine
            positions = PositionEngine.build_positions_from_executions(raw_executions)
            
            # Remove existing positions for this account
            db.cursor.execute("DELETE FROM positions WHERE account = ?", (account,))
            
            # Remove execution links for this account's positions
            db.cursor.execute("""
                DELETE FROM position_executions 
                WHERE position_id IN (
                    SELECT id FROM positions WHERE account = ?
                )
            """, (account,))
            
            # Save new positions
            positions_created = 0
            position_ids = []
            for position in positions:
                if position.account == account:  # Double-check account match
                    position_id = _save_position_to_database(db, position)
                    if position_id:
                        positions_created += 1
                        position_ids.append(position_id)
                        # Link executions to position
                        _link_executions_to_position(db, position_id, position.executions)

            db.commit()

            logger.info(f"Position rebuild for {account} completed: {positions_created} positions created")

            # Trigger OHLC data fetch for newly created positions
            if position_ids:
                try:
                    from routes.positions import _trigger_position_data_fetch
                    _trigger_position_data_fetch(position_ids)
                    logger.info(f"Triggered OHLC fetch for {len(position_ids)} positions in account {account}")
                except Exception as e:
                    logger.warning(f"Failed to trigger OHLC fetch for account {account}: {e}")

            return {
                'status': 'success',
                'account': account,
                'positions_created': positions_created,
                'position_ids': position_ids,
                'executions_processed': len(raw_executions)
            }
            
    except Exception as e:
        logger.error(f"Error rebuilding positions for account {account}: {e}")
        raise self.retry(exc=e, countdown=180, max_retries=3)


@app.task(base=CallbackTask, bind=True)
def rebuild_positions_for_instrument(self, instrument: str):
    """
    Rebuild positions for a specific instrument across all accounts
    
    Args:
        instrument: Instrument symbol to rebuild positions for
    """
    try:
        logger.info(f"Rebuilding positions for instrument: {instrument}")
        
        with DatabaseManager() as db:
            # Get trades for this instrument
            trades_query = """
                SELECT * FROM trades 
                WHERE instrument = ? AND (deleted = 0 OR deleted IS NULL)
                ORDER BY account, entry_time
            """
            
            result = db.cursor.execute(trades_query, (instrument,))
            raw_executions = [dict(row) for row in result.fetchall()]
            
            if not raw_executions:
                logger.info(f"No trades found for instrument: {instrument}")
                return {'status': 'no_trades', 'instrument': instrument, 'positions_created': 0}
            
            logger.info(f"Processing {len(raw_executions)} executions for instrument {instrument}")
            
            # Use the new position engine
            positions = PositionEngine.build_positions_from_executions(raw_executions)
            
            # Remove existing positions for this instrument
            db.cursor.execute("DELETE FROM positions WHERE instrument = ?", (instrument,))
            
            # Remove execution links for this instrument's positions
            db.cursor.execute("""
                DELETE FROM position_executions 
                WHERE position_id IN (
                    SELECT id FROM positions WHERE instrument = ?
                )
            """, (instrument,))
            
            # Save new positions
            positions_created = 0
            for position in positions:
                if position.instrument == instrument:  # Double-check instrument match
                    position_id = _save_position_to_database(db, position)
                    if position_id:
                        positions_created += 1
                        # Link executions to position
                        _link_executions_to_position(db, position_id, position.executions)
            
            db.commit()
            
            logger.info(f"Position rebuild for {instrument} completed: {positions_created} positions created")
            
            return {
                'status': 'success',
                'instrument': instrument,
                'positions_created': positions_created,
                'executions_processed': len(raw_executions)
            }
            
    except Exception as e:
        logger.error(f"Error rebuilding positions for instrument {instrument}: {e}")
        raise self.retry(exc=e, countdown=180, max_retries=3)


@app.task(base=CallbackTask, bind=True)
def check_rebuild_needed(self):
    """
    Check if position rebuild is needed based on data inconsistencies
    Scheduled to run daily at 1 AM
    """
    try:
        logger.info("Checking if position rebuild is needed")
        
        with DatabaseManager() as db:
            # Check for trades without corresponding positions
            orphaned_trades_query = """
                SELECT COUNT(*) as orphaned_count
                FROM trades t
                LEFT JOIN position_executions pe ON t.id = pe.trade_id
                WHERE pe.trade_id IS NULL 
                AND (t.deleted = 0 OR t.deleted IS NULL)
            """
            
            result = db.cursor.execute(orphaned_trades_query)
            orphaned_count = result.fetchone()[0]
            
            # Check for positions without trades
            orphaned_positions_query = """
                SELECT COUNT(*) as orphaned_positions
                FROM positions p
                LEFT JOIN position_executions pe ON p.id = pe.position_id
                WHERE pe.position_id IS NULL
            """
            
            result = db.cursor.execute(orphaned_positions_query)
            orphaned_positions = result.fetchone()[0]
            
            # Check for recent trades (last 24 hours) that might need position updates
            recent_trades_query = """
                SELECT COUNT(*) as recent_count
                FROM trades 
                WHERE created_at >= datetime('now', '-1 day')
                AND (deleted = 0 OR deleted IS NULL)
            """
            
            result = db.cursor.execute(recent_trades_query)
            recent_trades = result.fetchone()[0]
            
            logger.info(f"Rebuild check: {orphaned_count} orphaned trades, {orphaned_positions} orphaned positions, {recent_trades} recent trades")
            
            # Determine if rebuild is needed
            rebuild_needed = False
            reasons = []
            
            if orphaned_count > 10:  # Threshold for orphaned trades
                rebuild_needed = True
                reasons.append(f"{orphaned_count} orphaned trades")
            
            if orphaned_positions > 5:  # Threshold for orphaned positions
                rebuild_needed = True
                reasons.append(f"{orphaned_positions} orphaned positions")
            
            if recent_trades > 50:  # Threshold for recent activity
                rebuild_needed = True
                reasons.append(f"{recent_trades} recent trades requiring position updates")
            
            result = {
                'status': 'checked',
                'rebuild_needed': rebuild_needed,
                'orphaned_trades': orphaned_count,
                'orphaned_positions': orphaned_positions,
                'recent_trades': recent_trades,
                'reasons': reasons
            }
            
            if rebuild_needed:
                logger.info(f"Position rebuild needed: {', '.join(reasons)}")
                # Trigger selective rebuild instead of full rebuild
                rebuild_task = rebuild_recent_positions.delay(days_back=7)
                result['rebuild_task_id'] = rebuild_task.id
            else:
                logger.info("No position rebuild needed")
            
            return result
            
    except Exception as e:
        logger.error(f"Error in check_rebuild_needed: {e}")
        raise self.retry(exc=e, countdown=3600, max_retries=1)  # 1 hour delay


@app.task(base=CallbackTask, bind=True)
def rebuild_recent_positions(self, days_back: int = 7):
    """
    Rebuild positions for accounts with recent activity
    
    Args:
        days_back: Number of days to look back for recent activity
    """
    try:
        logger.info(f"Rebuilding positions for accounts with activity in last {days_back} days")
        
        with DatabaseManager() as db:
            # Get accounts with recent trades
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d %H:%M:%S')
            
            accounts_query = """
                SELECT DISTINCT account 
                FROM trades 
                WHERE entry_time >= ? 
                AND (deleted = 0 OR deleted IS NULL)
                ORDER BY account
            """
            
            result = db.cursor.execute(accounts_query, (cutoff_date,))
            accounts = [row[0] for row in result.fetchall()]
            
            if not accounts:
                logger.info("No accounts with recent activity found")
                return {'status': 'no_recent_activity', 'accounts_processed': 0}
            
            logger.info(f"Found {len(accounts)} accounts with recent activity: {accounts}")
            
            # Rebuild positions for each account
            total_positions = 0
            results = {}
            
            for account in accounts:
                try:
                    # Queue individual account rebuild
                    result = rebuild_positions_for_account.delay(account)
                    results[account] = {
                        'task_id': result.id,
                        'status': 'queued'
                    }
                    logger.info(f"Queued position rebuild for account: {account}")
                    
                except Exception as e:
                    logger.error(f"Failed to queue rebuild for account {account}: {e}")
                    results[account] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            return {
                'status': 'success',
                'accounts_processed': len(accounts),
                'days_back': days_back,
                'rebuild_results': results
            }
            
    except Exception as e:
        logger.error(f"Error in rebuild_recent_positions: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


def _save_position_to_database(db: DatabaseManager, position) -> Optional[int]:
    """Save a position object to the database"""
    try:
        query = """
            INSERT INTO positions (
                account, instrument, side, entry_time, exit_time,
                entry_price, exit_price, quantity, points_gain_loss,
                dollars_gain_loss, commission, duration_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Calculate duration if position is closed
        duration_minutes = None
        if position.exit_time and position.entry_time:
            try:
                entry_dt = datetime.fromisoformat(position.entry_time.replace('Z', '+00:00'))
                exit_dt = datetime.fromisoformat(position.exit_time.replace('Z', '+00:00'))
                duration_minutes = int((exit_dt - entry_dt).total_seconds() / 60)
            except Exception:
                pass
        
        params = (
            position.account,
            position.instrument,
            position.side.value,
            position.entry_time,
            position.exit_time,
            position.average_entry_price,
            position.average_exit_price,
            position.total_quantity,
            position.total_points_pnl,
            position.total_dollars_pnl,
            position.total_commission,
            duration_minutes
        )
        
        result = db.cursor.execute(query, params)
        return result.lastrowid
        
    except Exception as e:
        logger.error(f"Error saving position to database: {e}")
        return None


def _link_executions_to_position(db: DatabaseManager, position_id: int, executions) -> None:
    """Link execution records to a position"""
    try:
        for i, execution in enumerate(executions):
            # Find the trade ID by execution ID
            trade_query = """
                SELECT id FROM trades 
                WHERE entry_execution_id = ? 
                AND account = ? 
                AND instrument = ?
                LIMIT 1
            """
            
            result = db.cursor.execute(trade_query, (
                execution.id, 
                execution.account, 
                execution.instrument
            ))
            
            trade_row = result.fetchone()
            if trade_row:
                trade_id = trade_row[0]
                
                # Link the trade to the position
                link_query = """
                    INSERT OR IGNORE INTO position_executions (position_id, trade_id, execution_order)
                    VALUES (?, ?, ?)
                """
                
                db.cursor.execute(link_query, (position_id, trade_id, i))
        
    except Exception as e:
        logger.error(f"Error linking executions to position {position_id}: {e}")


@app.task(base=CallbackTask, bind=True)
def auto_rebuild_positions_async(self, account: str, instrument_list: List[str]) -> Dict[str, Any]:
    """
    Asynchronously rebuild positions for specific account/instrument combinations
    
    This task provides async capabilities for bulk position building with 
    progress tracking and status reporting.
    
    Args:
        self: Celery task instance (bound for progress tracking)
        account: Account identifier for position rebuilding
        instrument_list: List of instruments to rebuild positions for
        
    Returns:
        Dict containing:
        - status: 'success', 'partial_success', or 'error'
        - account: Account processed
        - total_instruments: Total number of instruments requested
        - successful_instruments: Number of successfully processed instruments
        - failed_instruments: Number of failed instruments
        - results: Dict mapping instrument -> result details
        - start_time: Processing start timestamp
        - end_time: Processing end timestamp
    """
    start_time = datetime.now()
    
    try:
        logger.info(f"Starting async position rebuild for account {account} with {len(instrument_list)} instruments: {instrument_list}")
        
        # Initialize result structure
        result = {
            'status': 'success',
            'account': account,
            'total_instruments': len(instrument_list),
            'successful_instruments': 0,
            'failed_instruments': 0,
            'results': {},
            'start_time': start_time.isoformat(),
            'end_time': None
        }
        
        # Process each instrument
        for i, instrument in enumerate(instrument_list):
            try:
                # Update progress
                progress = int((i / len(instrument_list)) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': len(instrument_list),
                        'progress': progress,
                        'instrument': instrument,
                        'status': f'Processing {instrument}...'
                    }
                )
                
                logger.info(f"Processing instrument {i+1}/{len(instrument_list)}: {instrument}")
                
                # Use the enhanced position service for incremental rebuild
                with EnhancedPositionServiceV2() as position_service:
                    instrument_result = position_service.rebuild_positions_for_account_instrument(account, instrument)
                    
                result['results'][instrument] = instrument_result
                result['successful_instruments'] += 1
                
                logger.info(f"Successfully processed {instrument}: {instrument_result.get('positions_created', 0)} positions created")
                
            except Exception as e:
                logger.error(f"Error processing instrument {instrument} for account {account}: {e}")
                result['results'][instrument] = {
                    'status': 'error',
                    'error': str(e),
                    'account': account,
                    'instrument': instrument
                }
                result['failed_instruments'] += 1
        
        # Determine overall status
        if result['failed_instruments'] == 0:
            result['status'] = 'success'
        elif result['successful_instruments'] > 0:
            result['status'] = 'partial_success'
        else:
            result['status'] = 'error'
        
        # Final progress update
        self.update_state(
            state='SUCCESS' if result['status'] == 'success' else 'PARTIAL_SUCCESS',
            meta={
                'current': len(instrument_list),
                'total': len(instrument_list),
                'progress': 100,
                'status': f'Completed: {result["successful_instruments"]} successful, {result["failed_instruments"]} failed'
            }
        )
        
        end_time = datetime.now()
        result['end_time'] = end_time.isoformat()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Async position rebuild completed for account {account}: "
                   f"{result['successful_instruments']} successful, {result['failed_instruments']} failed "
                   f"in {processing_time:.2f} seconds")
        
        return result
        
    except Exception as e:
        logger.error(f"Critical error in auto_rebuild_positions_async for account {account}: {e}")
        
        # Update progress to indicate failure
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'status': 'Critical error occurred',
                'account': account,
                'instruments': instrument_list
            }
        )
        
        # Return error result instead of raising (for better API compatibility)
        end_time = datetime.now()
        return {
            'status': 'error',
            'account': account,
            'total_instruments': len(instrument_list),
            'successful_instruments': 0,
            'failed_instruments': len(instrument_list),
            'results': {instrument: {'status': 'error', 'error': str(e)} for instrument in instrument_list},
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'error': str(e)
        }


# Manual task triggers for API endpoints
@app.task(base=CallbackTask)
def trigger_manual_position_rebuild(scope: str = 'all', target: str = None):
    """
    Manually trigger position rebuild (for API endpoints)
    
    Args:
        scope: 'all', 'account', or 'instrument'
        target: Account or instrument name if scope is not 'all'
    """
    if scope == 'all':
        return rebuild_all_positions.delay()
    elif scope == 'account' and target:
        return rebuild_positions_for_account.delay(target)
    elif scope == 'instrument' and target:
        return rebuild_positions_for_instrument.delay(target)
    else:
        raise ValueError(f"Invalid scope '{scope}' or missing target")


@app.task(base=CallbackTask)
def get_position_rebuild_status():
    """Get status of position rebuild operations (for monitoring)"""
    try:
        with DatabaseManager() as db:
            # Get position counts by account
            counts_query = """
                SELECT account, COUNT(*) as position_count
                FROM positions 
                GROUP BY account
                ORDER BY account
            """
            
            result = db.cursor.execute(counts_query)
            account_counts = {row[0]: row[1] for row in result.fetchall()}
            
            # Get total counts
            total_query = "SELECT COUNT(*) FROM positions"
            result = db.cursor.execute(total_query)
            total_positions = result.fetchone()[0]
            
            total_trades_query = "SELECT COUNT(*) FROM trades WHERE deleted = 0 OR deleted IS NULL"
            result = db.cursor.execute(total_trades_query)
            total_trades = result.fetchone()[0]
            
            return {
                'status': 'success',
                'total_positions': total_positions,
                'total_trades': total_trades,
                'account_breakdown': account_counts
            }
            
    except Exception as e:
        logger.error(f"Error getting position rebuild status: {e}")
        return {'status': 'error', 'error': str(e)}