"""
Position Validation and Database Cleanup API Endpoints

Provides REST API endpoints for:
1. Position state validation
2. Database cleanup operations
3. Data integrity checks

Ref: agent-os/specs/2025-11-11-position-dashboard-fix/tasks.md
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from scripts.TradingLog_db import FuturesDB
from scripts.cleanup_database import DatabaseCleanup
from domain.models.position import Position

logger = logging.getLogger('validation_cleanup')

validation_cleanup_bp = Blueprint('validation_cleanup', __name__, url_prefix='/api/validation')


@validation_cleanup_bp.route('/positions/validate', methods=['GET'])
def validate_all_positions():
    """
    Validate all positions in the database for state consistency.

    Query Parameters:
        - account: Optional filter by account
        - status: Optional filter by position status (open/closed)
        - include_valid: Boolean to include valid positions in response (default: False)

    Returns:
        JSON with validation results:
        {
            'total_positions': int,
            'valid_count': int,
            'invalid_count': int,
            'validation_timestamp': str,
            'invalid_positions': [
                {
                    'id': int,
                    'instrument': str,
                    'account': str,
                    'errors': List[str],
                    'warnings': List[str],
                    'integrity_score': float
                }
            ]
        }
    """
    try:
        account_filter = request.args.get('account')
        status_filter = request.args.get('status')
        include_valid = request.args.get('include_valid', 'false').lower() == 'true'

        with FuturesDB() as db:
            # Build query
            query = "SELECT * FROM positions WHERE 1=1"
            params = []

            if account_filter:
                query += " AND account = ?"
                params.append(account_filter)

            if status_filter:
                query += " AND position_status = ?"
                params.append(status_filter)

            cursor = db.conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Validate each position
            valid_positions = []
            invalid_positions = []

            for row in rows:
                # Convert row to Position object
                position_data = dict(row)
                position = Position.from_dict(position_data)

                # Validate state
                validation_result = position.validate_state()

                position_summary = {
                    'id': position.id,
                    'instrument': position.instrument,
                    'account': position.account,
                    'position_status': position.position_status.value,
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'integrity_score': validation_result['integrity_score']
                }

                if validation_result['is_valid']:
                    valid_positions.append(position_summary)
                else:
                    invalid_positions.append(position_summary)

            # Prepare response
            response = {
                'total_positions': len(rows),
                'valid_count': len(valid_positions),
                'invalid_count': len(invalid_positions),
                'validation_timestamp': datetime.now().isoformat(),
                'invalid_positions': invalid_positions
            }

            if include_valid:
                response['valid_positions'] = valid_positions

            return jsonify(response), 200

    except Exception as e:
        logger.error(f"Position validation failed: {e}")
        return jsonify({
            'error': 'Position validation failed',
            'message': str(e)
        }), 500


@validation_cleanup_bp.route('/positions/<int:position_id>/validate', methods=['GET'])
def validate_single_position(position_id: int):
    """
    Validate a single position by ID.

    Returns:
        JSON with validation results for the position
    """
    try:
        with FuturesDB() as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Position not found'}), 404

            # Convert to Position object
            position = Position.from_dict(dict(row))

            # Validate state
            validation_result = position.validate_state()

            response = {
                'position_id': position.id,
                'instrument': position.instrument,
                'account': position.account,
                'position_status': position.position_status.value,
                'is_valid': validation_result['is_valid'],
                'errors': validation_result['errors'],
                'warnings': validation_result['warnings'],
                'integrity_score': validation_result['integrity_score'],
                'validation_timestamp': datetime.now().isoformat()
            }

            return jsonify(response), 200

    except Exception as e:
        logger.error(f"Position validation failed: {e}")
        return jsonify({
            'error': 'Position validation failed',
            'message': str(e)
        }), 500


@validation_cleanup_bp.route('/database/stats', methods=['GET'])
def get_database_stats():
    """
    Get database statistics and record counts.

    Returns:
        JSON with database statistics:
        {
            'positions': int,
            'trades': int,
            'position_executions': int,
            'open_positions': int,
            'closed_positions': int,
            'timestamp': str
        }
    """
    try:
        from config import config

        with DatabaseCleanup(str(config.db_path)) as cleanup:
            counts = cleanup.get_record_counts()

            # Get additional position stats
            with FuturesDB() as db:
                cursor = db.conn.cursor()

                cursor.execute("SELECT COUNT(*) as count FROM positions WHERE position_status = 'open'")
                open_count = cursor.fetchone()['count']

                cursor.execute("SELECT COUNT(*) as count FROM positions WHERE position_status = 'closed'")
                closed_count = cursor.fetchone()['count']

                # Get positions with zero entry price (data integrity issue)
                cursor.execute("SELECT COUNT(*) as count FROM positions WHERE average_entry_price = 0")
                zero_entry_count = cursor.fetchone()['count']

                # Get positions with catastrophic P&L
                cursor.execute("SELECT COUNT(*) as count FROM positions WHERE ABS(total_dollars_pnl) > 1000000")
                catastrophic_pnl_count = cursor.fetchone()['count']

            response = {
                'total_positions': counts['positions'],
                'total_trades': counts['trades'],
                'position_executions': counts['position_executions'],
                'open_positions': open_count,
                'closed_positions': closed_count,
                'data_integrity_issues': {
                    'positions_with_zero_entry_price': zero_entry_count,
                    'positions_with_catastrophic_pnl': catastrophic_pnl_count
                },
                'timestamp': datetime.now().isoformat()
            }

            return jsonify(response), 200

    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return jsonify({
            'error': 'Failed to get database stats',
            'message': str(e)
        }), 500


@validation_cleanup_bp.route('/database/cleanup', methods=['POST'])
def cleanup_database():
    """
    Perform database cleanup operations.

    Request Body:
        {
            'action': 'delete_positions' | 'delete_trades' | 'delete_all',
            'confirm': true
        }

    Returns:
        JSON with cleanup results
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        action = data.get('action')
        confirm = data.get('confirm', False)

        if not action:
            return jsonify({'error': 'action field required'}), 400

        if not confirm:
            return jsonify({
                'error': 'Confirmation required',
                'message': 'Set confirm=true to perform deletion. This operation is IRREVERSIBLE.'
            }), 400

        from config import config

        with DatabaseCleanup(str(config.db_path)) as cleanup:
            # Get counts before deletion
            counts_before = cleanup.get_record_counts()

            if action == 'delete_positions':
                positions_deleted = cleanup.delete_positions(confirm=True)
                result = {
                    'action': 'delete_positions',
                    'positions_deleted': positions_deleted,
                    'counts_before': counts_before,
                    'timestamp': datetime.now().isoformat()
                }

            elif action == 'delete_trades':
                trades_deleted = cleanup.delete_trades(confirm=True)
                result = {
                    'action': 'delete_trades',
                    'trades_deleted': trades_deleted,
                    'counts_before': counts_before,
                    'timestamp': datetime.now().isoformat()
                }

            elif action == 'delete_all':
                result = cleanup.delete_all(confirm=True)
                result['counts_before'] = counts_before
                result['action'] = 'delete_all'

            else:
                return jsonify({
                    'error': 'Invalid action',
                    'message': 'action must be one of: delete_positions, delete_trades, delete_all'
                }), 400

            # Verify cleanup
            is_empty = cleanup.verify_empty()
            result['verification_passed'] = is_empty

            return jsonify(result), 200

    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        return jsonify({
            'error': 'Database cleanup failed',
            'message': str(e)
        }), 500


@validation_cleanup_bp.route('/integrity/check', methods=['GET'])
def check_data_integrity():
    """
    Perform comprehensive data integrity checks.

    Returns:
        JSON with integrity check results:
        {
            'checks': [
                {
                    'name': str,
                    'passed': bool,
                    'count': int,
                    'severity': 'error' | 'warning',
                    'message': str
                }
            ],
            'overall_status': 'healthy' | 'warnings' | 'errors',
            'timestamp': str
        }
    """
    try:
        checks = []

        with FuturesDB() as db:
            cursor = db.conn.cursor()

            # Check 1: Positions with zero entry price
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE average_entry_price = 0 AND position_status = 'closed'
            """)
            zero_entry_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Zero Entry Price Check',
                'passed': zero_entry_count == 0,
                'count': zero_entry_count,
                'severity': 'error',
                'message': f'{zero_entry_count} closed positions have zero entry price'
            })

            # Check 2: Open positions with exit times
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE position_status = 'open' AND exit_time IS NOT NULL
            """)
            contradictory_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Contradictory Position State Check',
                'passed': contradictory_count == 0,
                'count': contradictory_count,
                'severity': 'error',
                'message': f'{contradictory_count} open positions have exit_time set'
            })

            # Check 3: Catastrophic P&L values
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE ABS(total_dollars_pnl) > 1000000
            """)
            catastrophic_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Catastrophic P&L Check',
                'passed': catastrophic_count == 0,
                'count': catastrophic_count,
                'severity': 'error',
                'message': f'{catastrophic_count} positions have catastrophic P&L (> $1M)'
            })

            # Check 4: Closed positions without exit times
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE position_status = 'closed' AND exit_time IS NULL
            """)
            missing_exit_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Missing Exit Time Check',
                'passed': missing_exit_count == 0,
                'count': missing_exit_count,
                'severity': 'error',
                'message': f'{missing_exit_count} closed positions missing exit_time'
            })

            # Check 5: Positions with zero execution count
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE execution_count = 0 AND position_status = 'closed'
            """)
            zero_exec_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Zero Execution Count Check',
                'passed': zero_exec_count == 0,
                'count': zero_exec_count,
                'severity': 'warning',
                'message': f'{zero_exec_count} closed positions have zero execution_count'
            })

            # Check 6: Exit time before entry time
            cursor.execute("""
                SELECT COUNT(*) as count FROM positions
                WHERE exit_time IS NOT NULL AND exit_time < entry_time
            """)
            time_order_count = cursor.fetchone()['count']
            checks.append({
                'name': 'Time Order Check',
                'passed': time_order_count == 0,
                'count': time_order_count,
                'severity': 'error',
                'message': f'{time_order_count} positions have exit_time before entry_time'
            })

        # Determine overall status
        has_errors = any(not check['passed'] and check['severity'] == 'error' for check in checks)
        has_warnings = any(not check['passed'] and check['severity'] == 'warning' for check in checks)

        if has_errors:
            overall_status = 'errors'
        elif has_warnings:
            overall_status = 'warnings'
        else:
            overall_status = 'healthy'

        response = {
            'checks': checks,
            'overall_status': overall_status,
            'total_checks': len(checks),
            'passed_checks': sum(1 for check in checks if check['passed']),
            'failed_checks': sum(1 for check in checks if not check['passed']),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        return jsonify({
            'error': 'Integrity check failed',
            'message': str(e)
        }), 500


# Health check endpoint
@validation_cleanup_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the validation/cleanup service"""
    return jsonify({
        'status': 'healthy',
        'service': 'validation-cleanup',
        'timestamp': datetime.now().isoformat()
    }), 200
