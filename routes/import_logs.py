"""
Import Logs Routes

Provides comprehensive import execution logging interface with:
- Paginated, filterable import history
- Row-level log expansion
- Retry and rollback operations
- Log export functionality
- Affected trades viewing
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from datetime import datetime
import logging
import io
import json
from typing import Dict, Any, List

from services.import_logs_service import ImportLogsService
from services.unified_csv_import_service import unified_csv_import_service

logger = logging.getLogger(__name__)
import_logs_bp = Blueprint('import_logs', __name__, url_prefix='/api/import-logs')


# ========================================================================
# Main Import Logs Page
# ========================================================================

@import_logs_bp.route('/page')
def import_logs_page():
    """Render the main import logs page"""
    return render_template('import_logs.html')


# ========================================================================
# Import Logs List Endpoints
# ========================================================================

@import_logs_bp.route('/list')
def get_import_logs_list():
    """
    Get paginated, filterable list of import execution logs.

    Query Parameters:
        status: Filter by status (success, partial, failed)
        account: Filter by account name
        start_date: Filter by import date (from) - ISO format
        end_date: Filter by import date (to) - ISO format
        limit: Maximum number of results (default: 100)
        offset: Number of results to skip (default: 0)

    Returns:
        JSON with import logs list and metadata
    """
    try:
        # Get query parameters
        status = request.args.get('status')
        account = request.args.get('account')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        # Parse dates
        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

        # Get logs from service
        import_logs_service = ImportLogsService()
        logs = import_logs_service.get_import_logs(
            status=status,
            account=account,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        return jsonify({
            'success': True,
            'logs': logs,
            'count': len(logs),
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        logger.error(f"Error getting import logs list: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Import Log Detail Endpoints
# ========================================================================

@import_logs_bp.route('/detail/<import_batch_id>')
def get_import_log_detail(import_batch_id: str):
    """
    Get detailed view of a specific import including row-level logs.

    Args:
        import_batch_id: Batch ID to retrieve

    Returns:
        JSON with import log and all row logs
    """
    try:
        import_logs_service = ImportLogsService()

        # Get main import log
        import_log = import_logs_service.get_import_log_by_batch_id(import_batch_id)
        if not import_log:
            return jsonify({
                'success': False,
                'error': 'Import log not found'
            }), 404

        # Get row logs
        row_logs = import_logs_service.get_row_logs(import_batch_id)

        return jsonify({
            'success': True,
            'import_log': import_log,
            'row_logs': row_logs,
            'row_count': len(row_logs)
        })

    except Exception as e:
        logger.error(f"Error getting import log detail: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@import_logs_bp.route('/failed-rows/<import_batch_id>')
def get_failed_rows(import_batch_id: str):
    """
    Get only failed row logs for a specific import.

    Args:
        import_batch_id: Batch ID to retrieve

    Returns:
        JSON with failed row logs only
    """
    try:
        import_logs_service = ImportLogsService()

        failed_rows = import_logs_service.get_failed_row_logs(import_batch_id)

        return jsonify({
            'success': True,
            'failed_rows': failed_rows,
            'count': len(failed_rows)
        })

    except Exception as e:
        logger.error(f"Error getting failed rows: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Retry and Rollback Operations
# ========================================================================

@import_logs_bp.route('/retry/<import_batch_id>', methods=['POST'])
def retry_import(import_batch_id: str):
    """
    Retry a failed import by moving file back to import directory.

    Args:
        import_batch_id: Batch ID to retry

    Returns:
        JSON with retry result
    """
    try:
        import_logs_service = ImportLogsService()

        success, message = import_logs_service.retry_import(import_batch_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        logger.error(f"Error retrying import: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@import_logs_bp.route('/rollback/<import_batch_id>', methods=['POST'])
def rollback_import(import_batch_id: str):
    """
    Rollback an import by deleting all created trades and clearing cache.

    Args:
        import_batch_id: Batch ID to rollback

    Returns:
        JSON with rollback result
    """
    try:
        import_logs_service = ImportLogsService()

        success, message = import_logs_service.rollback_import(import_batch_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        logger.error(f"Error rolling back import: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Export Operations
# ========================================================================

@import_logs_bp.route('/download/<import_batch_id>')
def download_logs(import_batch_id: str):
    """
    Download import logs as JSON file.

    Args:
        import_batch_id: Batch ID to export

    Returns:
        JSON file download
    """
    try:
        import_logs_service = ImportLogsService()

        success, message, json_data = import_logs_service.export_logs_to_json(import_batch_id)

        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400

        # Create file-like object for download
        file_obj = io.BytesIO(json_data.encode('utf-8'))
        file_obj.seek(0)

        filename = f"import_log_{import_batch_id}.json"

        return send_file(
            file_obj,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Affected Trades Operations
# ========================================================================

@import_logs_bp.route('/affected-trades/<import_batch_id>')
def get_affected_trades(import_batch_id: str):
    """
    Get all trades created by a specific import.

    Args:
        import_batch_id: Batch ID to query

    Returns:
        JSON with list of affected trades
    """
    try:
        import_logs_service = ImportLogsService()

        trades = import_logs_service.get_affected_trades(import_batch_id)

        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades)
        })

    except Exception as e:
        logger.error(f"Error getting affected trades: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Statistics and Summary Endpoints
# ========================================================================

@import_logs_bp.route('/statistics')
def get_import_statistics():
    """
    Get overall import statistics.

    Returns:
        JSON with statistics about all imports
    """
    try:
        import_logs_service = ImportLogsService()

        # Get all logs (no filters)
        all_logs = import_logs_service.get_import_logs(limit=1000)

        # Calculate statistics
        total_imports = len(all_logs)
        successful_imports = sum(1 for log in all_logs if log['status'] == 'success')
        partial_imports = sum(1 for log in all_logs if log['status'] == 'partial')
        failed_imports = sum(1 for log in all_logs if log['status'] == 'failed')

        total_rows = sum(log.get('total_rows', 0) for log in all_logs)
        success_rows = sum(log.get('success_rows', 0) for log in all_logs)
        failed_rows = sum(log.get('failed_rows', 0) for log in all_logs)

        success_rate = (success_rows / total_rows * 100) if total_rows > 0 else 0

        return jsonify({
            'success': True,
            'statistics': {
                'total_imports': total_imports,
                'successful_imports': successful_imports,
                'partial_imports': partial_imports,
                'failed_imports': failed_imports,
                'total_rows_processed': total_rows,
                'total_rows_succeeded': success_rows,
                'total_rows_failed': failed_rows,
                'overall_success_rate': round(success_rate, 2)
            }
        })

    except Exception as e:
        logger.error(f"Error getting import statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
