"""
Position Routes - Handle position-based views and operations
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService
from scripts.TradingLog_db import FuturesDB
from services.position_overlap_integration import rebuild_positions_with_overlap_prevention
from services.position_overlap_prevention import PositionOverlapPrevention
from services.position_overlap_analysis import PositionOverlapAnalyzer
import logging
import os
import glob
import json
from datetime import datetime, timedelta, timezone
import pytz

# Import the chart execution extensions
import scripts.TradingLog_db_extension

positions_bp = Blueprint('positions', __name__)
logger = logging.getLogger('positions')


def _trigger_position_data_fetch(position_ids: list):
    """
    Trigger background OHLC data fetch for newly imported positions.
    Called after successful position import to ensure chart data is available.

    Args:
        position_ids: List of position IDs that were created/updated
    """
    try:
        from tasks.gap_filling import fetch_position_ohlc_data

        if not position_ids:
            return

        logger.info(f"Triggering OHLC data fetch for {len(position_ids)} positions")

        # Get position details for each position
        with FuturesDB() as db:
            for position_id in position_ids:
                try:
                    # Get position info from positions table
                    db.cursor.execute(
                        'SELECT instrument, entry_time, exit_time FROM positions WHERE id = ?',
                        (position_id,)
                    )
                    position = db.cursor.fetchone()
                    if not position:
                        logger.warning(f"Position {position_id} not found in positions table")
                        continue

                    instrument = position[0]
                    if not instrument:
                        continue

                    # Calculate date range with padding
                    # Entry time - 4 hours to exit time + 1 hour
                    entry_time = position[1]
                    exit_time = position[2]

                    if entry_time:
                        if isinstance(entry_time, str):
                            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        start_date = entry_time - timedelta(hours=4)
                    else:
                        # No entry time, use yesterday as fallback
                        start_date = datetime.now() - timedelta(days=1)

                    if exit_time:
                        if isinstance(exit_time, str):
                            exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                        end_date = exit_time + timedelta(hours=1)
                    else:
                        # Open position, use current time + 1 hour
                        end_date = datetime.now() + timedelta(hours=1)

                    # Queue async task (doesn't block import)
                    fetch_position_ohlc_data.delay(
                        position_id=position_id,
                        instrument=instrument,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        timeframes=['1m', '5m', '15m', '1h'],
                        priority='high'
                    )

                    logger.info(f"Queued OHLC fetch for position {position_id} ({instrument})")

                except Exception as e:
                    logger.error(f"Error queuing OHLC fetch for position {position_id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error in _trigger_position_data_fetch: {e}")
        # Don't re-raise - this is a background task that shouldn't fail the import


def calculate_position_chart_date_range(position):
    """
    Calculate optimal chart date range for a position with intelligent padding.

    Position times are stored as local Pacific Time strings. This function converts
    them to UTC for consistency with OHLC data which is stored with UTC timestamps.

    Args:
        position: Position dict with entry_time, exit_time, position_status

    Returns:
        Dict with chart_start_date and chart_end_date as UTC datetime objects,
        or None if calculation fails
    """
    try:
        # Handle missing entry_time
        if not position.get('entry_time'):
            logger.warning(f"Position missing entry_time, cannot calculate chart date range")
            return None

        # Define Pacific timezone (position times are stored in local PT)
        pacific_tz = pytz.timezone('America/Los_Angeles')
        utc_tz = pytz.UTC

        def parse_time_to_utc(time_val):
            """Parse a time value and convert to UTC datetime."""
            if isinstance(time_val, datetime):
                if time_val.tzinfo is None:
                    # Naive datetime - assume Pacific Time
                    return pacific_tz.localize(time_val).astimezone(utc_tz)
                else:
                    return time_val.astimezone(utc_tz)
            elif isinstance(time_val, str):
                # Check if it has timezone info
                if '+' in time_val or time_val.endswith('Z'):
                    time_val = time_val.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(time_val)
                    return dt.astimezone(utc_tz)
                else:
                    # Naive string - parse and assume Pacific Time
                    dt = datetime.fromisoformat(time_val)
                    return pacific_tz.localize(dt).astimezone(utc_tz)
            return None

        # Parse entry_time to UTC
        entry_time = parse_time_to_utc(position['entry_time'])
        if entry_time is None:
            logger.warning(f"Could not parse entry_time: {position['entry_time']}")
            return None

        # Parse exit_time for closed positions
        exit_time_raw = position.get('exit_time')
        if position.get('position_status') == 'closed' and exit_time_raw:
            exit_time = parse_time_to_utc(exit_time_raw)
            if exit_time is None:
                logger.warning(f"Could not parse exit_time: {exit_time_raw}")
                exit_time = datetime.now(utc_tz)
        else:
            # Open position: use current time as end (in UTC)
            exit_time = datetime.now(utc_tz)

        # Calculate position duration
        duration = exit_time - entry_time

        # Apply padding logic based on duration
        if duration < timedelta(hours=1):
            # Very short trades: Provide substantial context (4 hours before/after)
            # This ensures scalpers can see market movement before and especially after the trade
            padding = timedelta(hours=4)
        elif duration > timedelta(days=30):
            # Long trades: Use 20% padding
            padding = duration * 0.20
        else:
            # Standard trades: Use 15% padding with minimum 1 hour
            padding = max(timedelta(hours=1), duration * 0.15)

        # Calculate final date range (all in UTC)
        chart_start_date = entry_time - padding

        if position.get('position_status') == 'closed':
            chart_end_date = exit_time + padding
        else:
            # Open position: don't add padding to "now"
            chart_end_date = exit_time

        # NOTE: We no longer fall back to old data ranges when the position's dates
        # are outside available OHLC data. Instead, we use the position's actual dates
        # and let the on-demand fetch (in position_detail route) download the missing data.
        # This ensures the chart always targets the correct date range for the position.

        # Return naive UTC datetimes (remove tzinfo for compatibility with existing code)
        return {
            'chart_start_date': chart_start_date.replace(tzinfo=None),
            'chart_end_date': chart_end_date.replace(tzinfo=None)
        }

    except Exception as e:
        logger.error(f"Error calculating position chart date range: {e}")
        return None


@positions_bp.route('/')
def positions_dashboard():
    """Main positions dashboard showing aggregated positions instead of individual trades"""
    # Get filter parameters
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_order = request.args.get('sort_order', 'DESC')
    account_filter = request.args.get('account')
    instrument_filter = request.args.get('instrument')
    status_filter = request.args.get('status')  # 'open', 'closed', or None for all
    validation_filter = request.args.get('validation_status')  # Task 9.2: Add validation filter

    # Get pagination parameters
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = int(request.args.get('page_size', 50))
    except (ValueError, TypeError):
        page = 1
        page_size = 50

    # Validate page_size
    allowed_page_sizes = [10, 25, 50, 100]
    if page_size not in allowed_page_sizes:
        page_size = 50

    with PositionService() as pos_service:
        # Build WHERE clause with all filters including validation_status
        where_conditions = []
        params = []

        if account_filter:
            where_conditions.append("account = ?")
            params.append(account_filter)

        if instrument_filter:
            where_conditions.append("instrument = ?")
            params.append(instrument_filter)

        if status_filter:
            where_conditions.append("position_status = ?")
            params.append(status_filter)

        # Task 9.2: Add validation_status filter
        if validation_filter:
            # Convert query param to proper case for database
            if validation_filter.lower() == 'valid':
                where_conditions.append("validation_status = 'Valid'")
            elif validation_filter.lower() == 'invalid':
                where_conditions.append("validation_status = 'Invalid'")
            elif validation_filter.lower() == 'mixed':
                where_conditions.append("validation_status = 'Mixed'")
            elif validation_filter.lower() == 'null' or validation_filter.lower() == 'unreviewed':
                where_conditions.append("validation_status IS NULL")

        where_clause = " AND ".join(where_conditions)
        if where_clause:
            where_clause = "WHERE " + where_clause

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM positions {where_clause}"
        pos_service.cursor.execute(count_sql, params)
        total_count = pos_service.cursor.fetchone()[0]

        # Calculate pagination
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

        # Get positions with pagination
        offset = (page - 1) * page_size
        positions_sql = f"""
            SELECT * FROM positions
            {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        """
        pos_service.cursor.execute(positions_sql, params + [page_size, offset])
        positions = [dict(row) for row in pos_service.cursor.fetchall()]

        # Get statistics
        position_stats = pos_service.get_position_statistics(account=account_filter)

    # Get unique values for filters
    with FuturesDB() as db:
        accounts = db.get_unique_accounts()
        instruments = db.get_unique_instruments()

    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        return redirect(url_for('positions.positions_dashboard',
            page=total_pages,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filter,
            instrument=instrument_filter,
            status=status_filter,
            validation_status=validation_filter
        ))

    return render_template(
        'positions/dashboard.html',
        positions=positions,
        stats=position_stats,
        sort_by=sort_by,
        sort_order=sort_order,
        accounts=accounts,
        instruments=instruments,
        selected_account=account_filter,
        selected_instrument=instrument_filter,
        selected_status=status_filter,
        selected_validation=validation_filter,  # Task 9.2: Pass validation filter to template
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_count=total_count
    )


@positions_bp.route('/<int:position_id>')
def position_detail(position_id):
    """Position detail page showing all executions that make up the position"""
    with PositionService() as pos_service:
        # Get all positions and find the one with matching ID
        result = pos_service.get_positions(page_size=1000)  # Get enough to find the position
        positions = result['positions']
        position = next((p for p in positions if p['id'] == position_id), None)

        if not position:
            return render_template('error.html',
                                 error_message="Position not found",
                                 error_code=404), 404

        # Get the executions that make up this position
        executions = pos_service.get_position_executions(position_id)
        position['executions'] = executions

        logger.debug(f"Position {position_id} details: execution_count={position.get('execution_count')}, actual_executions={len(executions)}")

    # Calculate additional metrics for the detail view
    # Use existing position data for timing analysis
    position['first_execution'] = position['entry_time']
    position['last_execution'] = position.get('exit_time')

    # Calculate optimal chart date range for this position
    date_range = calculate_position_chart_date_range(position)

    # Format dates as ISO strings for JavaScript if calculation succeeded
    chart_start_date = None
    chart_end_date = None
    if date_range:
        chart_start_date = date_range['chart_start_date'].isoformat()
        chart_end_date = date_range['chart_end_date'].isoformat()
        logger.debug(f"Position {position_id} chart date range: {chart_start_date} to {chart_end_date}")
    else:
        logger.debug(f"Position {position_id} will use default chart view (date range calculation failed)")

    # Calculate position duration if closed
    if position['position_status'] == 'closed' and position['exit_time']:
        try:
            entry_dt = datetime.fromisoformat(position['entry_time'].replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(position['exit_time'].replace('Z', '+00:00'))
            duration = exit_dt - entry_dt
            position['duration_minutes'] = duration.total_seconds() / 60
            position['duration_display'] = f"{duration.days}d {duration.seconds//3600}h {(duration.seconds%3600)//60}m"
        except:
            position['duration_minutes'] = 0
            position['duration_display'] = "Unknown"

    # Calculate R:R ratio for closed positions
    if position['position_status'] == 'closed':
        total_pnl = position['total_dollars_pnl']
        commission = position['total_commission']

        if total_pnl > 0 and commission > 0:
            # Winner: Reward / Risk
            position['reward_risk_ratio'] = round(total_pnl / commission, 2)
            position['rr_display'] = f"{position['reward_risk_ratio']}:1"
        elif total_pnl < 0 and commission > 0:
            # Loser: Risk / Reward
            risk_ratio = abs(total_pnl) / commission
            position['reward_risk_ratio'] = round(1 / risk_ratio, 2) if risk_ratio > 0 else 0
            position['rr_display'] = f"1:{round(risk_ratio, 2)}"
        else:
            position['reward_risk_ratio'] = 0
            position['rr_display'] = "N/A"

    # Get FIFO-matched execution pairs for closed positions
    execution_pairs = None
    if position['position_status'] == 'closed':
        try:
            with FuturesDB() as db:
                instrument_multiplier = 2.0  # $2/point for MNQ
                execution_pairs = db.get_position_execution_pairs(position_id, instrument_multiplier)
                logger.debug(f"Position {position_id} execution pairs: {len(execution_pairs.get('execution_pairs', []))} pairs")
        except Exception as e:
            logger.error(f"Error getting execution pairs for position {position_id}: {e}")
            execution_pairs = None

    # Check if OHLC data exists for this position's chart, trigger fetch if missing
    ohlc_fetch_triggered = False
    if chart_start_date and chart_end_date:
        try:
            from tasks.gap_filling import needs_ohlc_data
            instrument = position.get('instrument')
            if instrument and needs_ohlc_data(instrument, chart_start_date, chart_end_date):
                logger.info(f"Position {position_id}: Missing OHLC data for {instrument}, triggering fetch")
                _trigger_position_data_fetch([position_id])
                ohlc_fetch_triggered = True
        except Exception as e:
            logger.warning(f"Failed to check/trigger OHLC data for position {position_id}: {e}")

    return render_template('positions/detail.html',
                         position=position,
                         chart_start_date=chart_start_date,
                         chart_end_date=chart_end_date,
                         execution_pairs=execution_pairs,
                         ohlc_fetch_triggered=ohlc_fetch_triggered)


@positions_bp.route('/rebuild', methods=['POST'])
def rebuild_positions():
    """Rebuild all positions from existing trades data"""
    try:
        with PositionService() as pos_service:
            result = pos_service.rebuild_positions_from_trades()

        return jsonify({
            'success': True,
            'message': f"Successfully rebuilt {result['positions_created']} positions from {result['trades_processed']} trades",
            'positions_created': result['positions_created'],
            'trades_processed': result['trades_processed']
        })

    except Exception as e:
        logger.error(f"Error rebuilding positions: {e}")
        return jsonify({
            'success': False,
            'message': f"Error rebuilding positions: {str(e)}"
        }), 500


@positions_bp.route('/rebuild-enhanced', methods=['POST'])
def rebuild_positions_enhanced():
    """Rebuild all positions with comprehensive validation and overlap prevention"""
    try:
        result = rebuild_positions_with_overlap_prevention()

        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Successfully rebuilt {result['positions_created']} positions from {result['groups_processed']} instrument groups",
                'positions_created': result['positions_created'],
                'groups_processed': result['groups_processed'],
                'warnings': result.get('warnings', []),
                'validation_enabled': True
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Rebuild failed: {result.get('error', 'Unknown error')}",
                'errors': result.get('errors', [])
            }), 500

    except Exception as e:
        logger.error(f"Error rebuilding positions with enhanced validation: {e}")
        return jsonify({
            'success': False,
            'message': f"Error rebuilding positions: {str(e)}"
        }), 500


@positions_bp.route('/api/statistics')
def api_position_statistics():
    """API endpoint for position statistics"""
    account = request.args.get('account')

    try:
        with PositionService() as pos_service:
            stats = pos_service.get_position_statistics(account=account)

        return jsonify({
            'success': True,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Error getting position statistics: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/api/executions/<int:position_id>')
def api_position_executions(position_id):
    """API endpoint to get execution details for a position"""
    try:
        with PositionService() as pos_service:
            position = pos_service.get_position_by_id(position_id)

        if not position:
            return jsonify({
                'success': False,
                'message': 'Position not found'
            }), 404

        return jsonify({
            'success': True,
            'position': position,
            'executions': position.get('executions', [])
        })

    except Exception as e:
        logger.error(f"Error getting position executions: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/api/<int:position_id>/execution-pairs')
def api_position_execution_pairs(position_id):
    """API endpoint to get FIFO-matched execution pairs with per-pair P&L"""
    try:
        # First check if position exists using PositionService
        with PositionService() as pos_service:
            position = pos_service.get_position_by_id(position_id)

        if not position:
            return jsonify({
                'success': False,
                'error': 'Position not found'
            }), 404

        if position.get('position_status') != 'closed':
            return jsonify({
                'success': False,
                'error': 'Cannot calculate pairs for open positions'
            }), 400

        # Get execution pairs using FuturesDB
        with FuturesDB() as db:
            # Use $2/point multiplier for MNQ (standard for micro futures)
            instrument_multiplier = 2.0
            pairs_data = db.get_position_execution_pairs(position_id, instrument_multiplier)

        return jsonify({
            'success': True,
            **pairs_data
        })

    except Exception as e:
        logger.error(f"Error getting position execution pairs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/<int:position_id>/executions-chart')
def api_position_executions_chart(position_id):
    """API endpoint to get execution data formatted for chart arrow display"""
    try:
        # Get query parameters
        timeframe = request.args.get('timeframe', '1h')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Validate timeframe
        valid_timeframes = ['1m', '5m', '1h']
        if timeframe not in valid_timeframes:
            return jsonify({
                'success': False,
                'error': f'Invalid timeframe. Must be one of: {valid_timeframes}'
            }), 400

        with FuturesDB() as db:
            chart_data = db.get_position_executions_for_chart_cached(position_id, timeframe, start_date, end_date)

        if not chart_data:
            return jsonify({
                'success': False,
                'error': 'Position not found'
            }), 404

        return jsonify({
            'success': True,
            **chart_data
        })

    except Exception as e:
        logger.error(f"Error getting position execution chart data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Trade Validation API Endpoints (Task Group 4)

@positions_bp.route('/api/positions')
def api_positions_with_validation_filter():
    """
    GET /api/positions with optional validation_status filter

    Query Parameters:
        validation_status: Filter by validation status (valid|invalid|mixed|null)
        account: Filter by account
        instrument: Filter by instrument
        status: Filter by position status (open|closed)
        page: Page number (default: 1)
        page_size: Items per page (default: 50)

    Returns:
        JSON response with positions list and pagination info
    """
    try:
        # Get filter parameters
        validation_status = request.args.get('validation_status')
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        status = request.args.get('status')

        # Get pagination parameters
        try:
            page = max(1, int(request.args.get('page', 1)))
            page_size = int(request.args.get('page_size', 50))
        except (ValueError, TypeError):
            page = 1
            page_size = 50

        # Validate validation_status parameter if provided
        if validation_status:
            valid_statuses = ['valid', 'invalid', 'mixed', 'null']
            if validation_status.lower() not in valid_statuses:
                return jsonify({
                    'success': False,
                    'error': f'Invalid validation_status. Must be one of: {", ".join(valid_statuses)}'
                }), 400

        with PositionService() as pos_service:
            # Build WHERE clause with validation_status filter
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

            if validation_status:
                # Convert lowercase to proper case for database query
                if validation_status.lower() == 'valid':
                    where_conditions.append("validation_status = 'Valid'")
                elif validation_status.lower() == 'invalid':
                    where_conditions.append("validation_status = 'Invalid'")
                elif validation_status.lower() == 'mixed':
                    where_conditions.append("validation_status = 'Mixed'")
                elif validation_status.lower() == 'null':
                    where_conditions.append("validation_status IS NULL")

            where_clause = " AND ".join(where_conditions)
            if where_clause:
                where_clause = "WHERE " + where_clause

            # Get total count
            count_sql = f"SELECT COUNT(*) FROM positions {where_clause}"
            pos_service.cursor.execute(count_sql, params)
            total_count = pos_service.cursor.fetchone()[0]

            # Get positions with pagination
            offset = (page - 1) * page_size
            positions_sql = f"""
                SELECT * FROM positions
                {where_clause}
                ORDER BY entry_time DESC
                LIMIT ? OFFSET ?
            """
            pos_service.cursor.execute(positions_sql, params + [page_size, offset])
            positions = [dict(row) for row in pos_service.cursor.fetchall()]

        return jsonify({
            'success': True,
            'positions': positions,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
        })

    except Exception as e:
        logger.error(f"Error getting positions with validation filter: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/trades/<int:trade_id>', methods=['PATCH'])
def api_patch_trade_validation(trade_id):
    """
    PATCH /api/trades/:id

    Update a trade's validation status and trigger position rebuild.

    Request Body:
        {
            "trade_validation": "Valid" | "Invalid" | null
        }

    Returns:
        200 OK: Trade updated successfully
        400 Bad Request: Invalid validation value
        404 Not Found: Trade not found
    """
    try:
        # Parse request body
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        trade_validation = data.get('trade_validation')

        # Validate trade_validation value
        if trade_validation is not None and trade_validation not in ['Valid', 'Invalid']:
            return jsonify({
                'success': False,
                'error': 'trade_validation must be "Valid", "Invalid", or null'
            }), 400

        # Check if trade exists and get account/instrument for rebuild
        with FuturesDB() as db:
            db.cursor.execute("SELECT account, instrument FROM trades WHERE id = ?", (trade_id,))
            trade = db.cursor.fetchone()

            if not trade:
                return jsonify({
                    'success': False,
                    'error': 'Trade not found'
                }), 404

            account = trade[0]
            instrument = trade[1]

            # Update trade_validation column
            db.cursor.execute("""
                UPDATE trades
                SET trade_validation = ?
                WHERE id = ?
            """, (trade_validation, trade_id))

            db.conn.commit()

        # Trigger position rebuild for affected account/instrument
        try:
            with PositionService() as pos_service:
                result = pos_service.rebuild_positions_for_account_instrument(account, instrument)
                logger.info(f"Rebuilt positions for {account}/{instrument} after trade {trade_id} validation update")
        except Exception as rebuild_error:
            logger.error(f"Error rebuilding positions after trade validation update: {rebuild_error}")
            # Don't fail the request if rebuild fails
            result = {'error': str(rebuild_error)}

        return jsonify({
            'success': True,
            'trade_id': trade_id,
            'trade_validation': trade_validation,
            'rebuild_result': result
        })

    except Exception as e:
        logger.error(f"Error updating trade validation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/statistics/by-validation')
def api_statistics_by_validation():
    """
    GET /api/statistics/by-validation

    Get performance metrics grouped by validation status.

    Returns:
        JSON response with statistics for each validation category:
        - Valid: Positions marked as valid trades
        - Invalid: Positions marked as invalid trades
        - Mixed: Positions with mixed validation
        - Unreviewed: Positions with no validation data

        Each category includes:
        - total_trades: Number of positions
        - win_rate: Percentage of winning positions
        - avg_pnl: Average P&L per position
        - total_pnl: Total P&L for all positions
    """
    try:
        with PositionService() as pos_service:
            # Query positions grouped by validation_status
            pos_service.cursor.execute("""
                SELECT
                    COALESCE(validation_status, 'Unreviewed') as category,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN total_dollars_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    AVG(total_dollars_pnl) as avg_pnl,
                    SUM(total_dollars_pnl) as total_pnl
                FROM positions
                GROUP BY validation_status
            """)

            results = pos_service.cursor.fetchall()

            # Build statistics dictionary
            statistics = {}
            for row in results:
                category = row[0]
                total_trades = row[1]
                winning_trades = row[2]
                avg_pnl = row[3] or 0.0
                total_pnl = row[4] or 0.0

                # Calculate win rate
                win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

                statistics[category] = {
                    'total_trades': total_trades,
                    'win_rate': round(win_rate, 2),
                    'avg_pnl': round(avg_pnl, 2),
                    'total_pnl': round(total_pnl, 2)
                }

        return jsonify({
            'success': True,
            'statistics': statistics
        })

    except Exception as e:
        logger.error(f"Error getting statistics by validation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/debug')
def debug_positions():
    """Debug page to examine position building logic"""
    from scripts.TradingLog_db import FuturesDB

    # Get recent trades for debugging
    with FuturesDB() as db:
        db.cursor.execute("""
            SELECT * FROM trades
            ORDER BY entry_time DESC
            LIMIT 20
        """)
        recent_trades = [dict(row) for row in db.cursor.fetchall()]

        # Get unique account/instrument combinations
        db.cursor.execute("""
            SELECT DISTINCT account, instrument, COUNT(*) as trade_count
            FROM trades
            GROUP BY account, instrument
            ORDER BY trade_count DESC
        """)
        account_instruments = [dict(row) for row in db.cursor.fetchall()]

    return render_template('positions/debug.html',
                         recent_trades=recent_trades,
                         account_instruments=account_instruments)


@positions_bp.route('/debug/<account>/<instrument>')
def debug_account_instrument(account, instrument):
    """Debug specific account/instrument combination"""
    from scripts.TradingLog_db import FuturesDB

    with FuturesDB() as db:
        # Get all trades for this account/instrument
        db.cursor.execute("""
            SELECT * FROM trades
            WHERE account = ? AND instrument = ?
            ORDER BY entry_time, exit_time
        """, (account, instrument))
        trades = [dict(row) for row in db.cursor.fetchall()]

    # Test position building with detailed logging
    with PositionService() as pos_service:
        # Enable debug logging
        import logging
        position_logger = logging.getLogger('position_service')
        position_logger.setLevel(logging.INFO)

        # Add a handler to capture logs for display
        log_handler = logging.StreamHandler()
        position_logger.addHandler(log_handler)

        # Build positions for this specific combination
        positions = pos_service._build_positions_from_execution_flow(trades, account, instrument)

    return jsonify({
        'account': account,
        'instrument': instrument,
        'trade_count': len(trades),
        'trades': trades,
        'positions_built': len(positions),
        'positions': positions
    })


@positions_bp.route('/delete', methods=['POST'])
def delete_positions():
    """Delete selected positions and their associated executions"""
    try:
        data = request.get_json()

        if not data or 'position_ids' not in data:
            return jsonify({
                'success': False,
                'message': 'No position IDs provided'
            }), 400

        position_ids = data['position_ids']

        if not position_ids:
            return jsonify({
                'success': False,
                'message': 'No position IDs provided'
            }), 400

        # Convert to integers and validate
        try:
            position_ids = [int(pid) for pid in position_ids]
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid position ID format'
            }), 400

        with PositionService() as pos_service:
            deleted_count = pos_service.delete_positions(position_ids)

        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} position{"s" if deleted_count != 1 else ""}',
            'deleted_count': deleted_count
        })

    except Exception as e:
        logger.error(f"Error deleting positions: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting positions: {str(e)}'
        }), 500


@positions_bp.route('/list-csv-files')
def list_csv_files():
    """DEPRECATED: List available CSV files for re-import. Use /api/csv/available-files instead."""
    logger.warning("DEPRECATED: /positions/list-csv-files called. Use /api/csv/available-files instead.")
    try:
        from config import config
        data_dir = config.data_dir

        # Look for CSV files in data directory
        csv_pattern = os.path.join(data_dir, "*.csv")
        csv_files = glob.glob(csv_pattern)

        # Get just the filenames
        filenames = [os.path.basename(f) for f in csv_files]
        filenames.sort(reverse=True)  # Most recent first

        return jsonify({
            'success': True,
            'files': filenames,
            'count': len(filenames)
        })

    except Exception as e:
        logger.error(f"Error listing CSV files: {e}")
        return jsonify({
            'success': False,
            'message': f'Error listing CSV files: {str(e)}'
        }), 500


@positions_bp.route('/reimport-csv', methods=['POST'])
def reimport_csv():
    """DEPRECATED: Re-import trades from a selected CSV file. Use /api/csv/reprocess instead."""
    logger.warning("DEPRECATED: /positions/reimport-csv called. Use /api/csv/reprocess instead.")
    try:
        data = request.get_json()

        if not data or 'filename' not in data:
            return jsonify({
                'success': False,
                'message': 'No filename provided'
            }), 400

        filename = data['filename']

        if not filename:
            return jsonify({
                'success': False,
                'message': 'No filename provided'
            }), 400

        # Security check - ensure filename contains no path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400

        from config import config
        data_dir = config.data_dir
        csv_path = os.path.join(data_dir, filename)

        # Verify file exists
        if not os.path.exists(csv_path):
            return jsonify({
                'success': False,
                'message': f'File not found: {filename}'
            }), 404

        # Import raw executions directly without pre-processing into completed trades
        import pandas as pd

        # Read the raw CSV with robust parsing for malformed files
        try:
            df = pd.read_csv(csv_path,
                           encoding='utf-8-sig',  # Handle BOM characters
                           on_bad_lines='skip',   # Skip malformed lines
                           skipinitialspace=True) # Handle extra spaces
        except Exception as e:
            try:
                # Fallback: use Python engine for more robust parsing
                df = pd.read_csv(csv_path,
                               encoding='utf-8-sig',
                               engine='python',
                               on_bad_lines='skip')
            except Exception as e2:
                return jsonify({
                    'success': False,
                    'message': f'Unable to parse CSV: {str(e2)}'
                }), 400
        print(f"Read {len(df)} raw executions from {filename}")

        # Import raw executions directly to database
        with FuturesDB() as db:
            success = db.import_raw_executions(csv_path)

        if success:
            # Rebuild positions after successful import
            with PositionService() as pos_service:
                result = pos_service.rebuild_positions_from_trades()

            # Trigger OHLC data fetch for newly imported positions
            if result['positions_created'] > 0:
                try:
                    _trigger_position_data_fetch(result.get('position_ids', []))
                except Exception as e:
                    logger.warning(f"Failed to trigger OHLC data fetch for positions: {e}")
                    # Don't fail the import if background fetch fails

            return jsonify({
                'success': True,
                'message': f'Successfully imported {len(df)} executions from {filename}. Rebuilt {result["positions_created"]} positions.',
                'executions_imported': len(df),
                'positions_created': result['positions_created'],
                'trades_processed': result['trades_processed']
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to import executions from {filename}'
            }), 500

    except Exception as e:
        logger.error(f"Error re-importing CSV: {e}")
        return jsonify({
            'success': False,
            'message': f'Error re-importing CSV: {str(e)}'
        }), 500


# Position Validation API Endpoints

@positions_bp.route('/api/validation/prevention-report')
def get_prevention_report():
    """Generate comprehensive position overlap prevention report"""
    try:
        account = request.args.get('account')
        instrument = request.args.get('instrument')

        with PositionOverlapPrevention() as validator:
            report = validator.generate_prevention_report(account=account, instrument=instrument)

        return jsonify({
            'success': True,
            'report': report,
            'report_type': 'prevention_report',
            'filters': {
                'account': account,
                'instrument': instrument
            }
        })

    except Exception as e:
        logger.error(f"Error generating prevention report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/overlap-analysis')
def get_overlap_analysis():
    """Generate comprehensive overlap analysis report"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            report = analyzer.generate_overlap_report()

        return jsonify({
            'success': True,
            'report': report,
            'report_type': 'overlap_analysis'
        })

    except Exception as e:
        logger.error(f"Error generating overlap analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/current-positions')
def get_current_positions_validation():
    """Validate current positions and return structured data"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            analysis = analyzer.analyze_current_positions()

        return jsonify({
            'success': True,
            'analysis': analysis,
            'validation_type': 'current_positions'
        })

    except Exception as e:
        logger.error(f"Error validating current positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/boundary-validation')
def get_boundary_validation():
    """Validate position boundaries and return structured data"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            validation = analyzer.validate_position_boundaries()

        return jsonify({
            'success': True,
            'validation': validation,
            'validation_type': 'boundary_validation'
        })

    except Exception as e:
        logger.error(f"Error validating position boundaries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/summary')
def get_validation_summary():
    """Get comprehensive validation summary combining multiple checks"""
    try:
        account = request.args.get('account')
        instrument = request.args.get('instrument')

        with PositionOverlapAnalyzer() as analyzer:
            current_analysis = analyzer.analyze_current_positions()
            boundary_validation = analyzer.validate_position_boundaries()

        with PositionOverlapPrevention() as validator:
            # Get basic validation data for summary
            pass

        summary = {
            'total_positions': current_analysis.get('total_positions', 0),
            'groups_analyzed': current_analysis.get('groups_analyzed', 0),
            'overlaps_found': current_analysis.get('overlaps_found', 0),
            'boundary_violations': boundary_validation.get('boundary_violations', 0),
            'has_issues': current_analysis.get('overlaps_found', 0) > 0 or boundary_validation.get('boundary_violations', 0) > 0,
            'validation_timestamp': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'summary': summary,
            'details': {
                'current_positions': current_analysis,
                'boundary_validation': boundary_validation
            }
        })

    except Exception as e:
        logger.error(f"Error generating validation summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/health')
def get_validation_health():
    """Quick health check for validation system"""
    try:
        health_status = {
            'validation_system': 'available',
            'overlap_prevention': 'active',
            'enhanced_position_service': 'active',
            'endpoints': [
                '/api/validation/prevention-report',
                '/api/validation/overlap-analysis',
                '/api/validation/current-positions',
                '/api/validation/boundary-validation',
                '/api/validation/summary',
                '/api/validation/health'
            ]
        }

        return jsonify({
            'success': True,
            'status': 'healthy',
            'health': health_status
        })

    except Exception as e:
        logger.error(f"Error checking validation health: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500
