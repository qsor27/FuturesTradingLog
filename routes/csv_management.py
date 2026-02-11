"""
CSV Management Routes for Unified Import System

Provides manual re-processing interface and file management for CSV imports.
Includes status and health check endpoints for NinjaTrader import service.
"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import logging
import shutil
from typing import Dict, Any, List

from services.unified_csv_import_service import unified_csv_import_service
from services.file_watcher import file_watcher
from services.ninjatrader_import_service import ninjatrader_import_service
from services.daily_import_scheduler import daily_import_scheduler
from config import config

logger = logging.getLogger(__name__)
csv_management_bp = Blueprint('csv_management', __name__, url_prefix='/api/csv')


def _trigger_ohlc_fetch_for_import(result: dict):
    """Trigger OHLC data fetch for positions created during import."""
    position_ids = result.get('position_ids', [])
    if not position_ids:
        return
    try:
        from routes.positions import _trigger_position_data_fetch
        logger.info(f"Triggering OHLC data fetch for {len(position_ids)} imported positions")
        _trigger_position_data_fetch(position_ids)
    except Exception as e:
        logger.warning(f"Failed to trigger OHLC data fetch for imported positions: {e}")


# ========================================================================
# Task 5.6: Service Status and Health Check Endpoints
# ========================================================================

@csv_management_bp.route('/import/status')
def get_import_status():
    """
    Get NinjaTrader import service status (Task 5.6).

    Returns:
        JSON with service state: running, last_import_time, last_processed_file,
        error_count, pending_files
    """
    try:
        status = ninjatrader_import_service.get_status()

        return jsonify({
            'success': True,
            **status
        })

    except Exception as e:
        logger.error(f"Error getting import service status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/import/health')
def get_import_health():
    """
    Health check endpoint for monitoring (Task 5.6).

    Returns:
        JSON with health status: healthy (true/false), last_successful_import_time,
        pending_file_count
    """
    try:
        status = ninjatrader_import_service.get_status()

        # Determine if service is healthy
        # Healthy if: running and (no errors or has successfully processed files recently)
        is_healthy = status['running'] and (
            status['error_count'] == 0 or
            status['last_import_time'] is not None
        )

        return jsonify({
            'success': True,
            'healthy': is_healthy,
            'last_successful_import_time': status['last_import_time'],
            'pending_file_count': len(status.get('pending_files', [])),
            'error_count': status['error_count'],
            'redis_connected': status['redis_connected']
        })

    except Exception as e:
        logger.error(f"Error getting import service health: {e}")
        return jsonify({
            'success': False,
            'healthy': False,
            'error': str(e)
        }), 500


# ========================================================================
# Task 6.6: Manual Retry Endpoint for Failed Files
# ========================================================================

@csv_management_bp.route('/import/retry/<filename>', methods=['POST'])
def retry_failed_file(filename: str):
    """
    Manual retry endpoint for failed files (Task 6.6).

    Checks if file exists in data or error folders, moves it back to data
    if in error folder, and triggers immediate processing.

    Args:
        filename: Name of the CSV file to retry

    Returns:
        JSON with success/failure and error details
    """
    try:
        logger.info(f"Manual retry requested for file: {filename}")

        # Validate filename pattern
        if not filename.startswith('NinjaTrader_Executions_') or not filename.endswith('.csv'):
            return jsonify({
                'success': False,
                'error': f'Invalid filename pattern. Expected: NinjaTrader_Executions_YYYYMMDD.csv'
            }), 400

        data_dir = config.data_dir
        error_dir = data_dir / 'error'

        # Check if file exists in data folder
        data_file = data_dir / filename
        if data_file.exists():
            logger.info(f"File {filename} found in data folder. Processing...")
            result = ninjatrader_import_service.process_csv_file(data_file)
            _trigger_ohlc_fetch_for_import(result)
            return jsonify(result)

        # Check if file exists in error folder (may have timestamp suffix)
        error_files = list(error_dir.glob(f'{Path(filename).stem}*.csv'))

        if not error_files:
            return jsonify({
                'success': False,
                'error': f'File not found in data or error folders: {filename}'
            }), 404

        # Use the first matching file (most recent if multiple)
        error_file = error_files[0]
        logger.info(f"Found file in error folder: {error_file.name}. Moving back to data folder...")

        # Move file back to data folder
        target_file = data_dir / filename
        shutil.move(str(error_file), str(target_file))
        logger.info(f"Moved {error_file.name} back to data folder as {filename}")

        # Trigger immediate processing
        result = ninjatrader_import_service.process_csv_file(target_file)

        if result['success']:
            logger.info(f"Successfully reprocessed {filename}: {result.get('executions_imported', 0)} executions imported")
            _trigger_ohlc_fetch_for_import(result)
        else:
            logger.error(f"Failed to reprocess {filename}: {result.get('error', 'Unknown error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in manual retry for {filename}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Legacy CSV Management Endpoints
# ========================================================================

@csv_management_bp.route('/status')
def get_status():
    """Get status of CSV import system and file monitoring"""
    try:
        import_status = unified_csv_import_service.get_processing_status()
        watcher_status = file_watcher.get_monitoring_status()

        return jsonify({
            'success': True,
            'import_service': import_status,
            'file_watcher': watcher_status,
            'data_directory': str(config.data_dir)
        })

    except Exception as e:
        logger.error(f"Error getting CSV management status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/available-files')
def get_available_files():
    """Get list of available CSV files for manual processing"""
    try:
        # Get available files from the unified service
        files = unified_csv_import_service.get_available_files()

        file_list = []
        for file_path in files:
            try:
                stats = file_path.stat()
                file_info = {
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size': stats.st_size,
                    'modified': stats.st_mtime,
                    'is_processed': unified_csv_import_service.is_file_processed(file_path.name),
                    'location': 'data' if file_path.parent.name != 'archive' else 'archive'
                }
                file_list.append(file_info)
            except Exception as e:
                logger.warning(f"Error getting stats for {file_path}: {e}")
                continue

        # Sort by modification time (newest first)
        file_list.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            'success': True,
            'files': file_list,
            'total_files': len(file_list)
        })

    except Exception as e:
        logger.error(f"Error getting available files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/reprocess', methods=['POST'])
def reprocess_file():
    """Manually reprocess a specific CSV file"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        file_path = data.get('file_path')
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'No file_path provided'
            }), 400

        logger.info(f"Manual reprocessing requested for: {file_path}")

        # Use the unified import service for reprocessing
        result = unified_csv_import_service.manual_reprocess_file(file_path)

        if result['success']:
            logger.info(f"Successfully reprocessed {file_path}")
            _trigger_ohlc_fetch_for_import(result)
        else:
            logger.error(f"Failed to reprocess {file_path}: {result.get('error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in manual reprocess: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/process-new-files', methods=['POST'])
def process_new_files():
    """Process all new files using unified import service"""
    try:
        logger.info("Manual processing of all new files requested")

        result = unified_csv_import_service.process_all_new_files()

        if result['success']:
            logger.info(f"Manual processing completed: {result.get('message', 'Success')}")
            _trigger_ohlc_fetch_for_import(result)
        else:
            logger.error(f"Manual processing failed: {result.get('error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in manual process all files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/force-file-check', methods=['POST'])
def force_file_check():
    """Force file watcher to check for new files immediately"""
    try:
        logger.info("Manual file check triggered")

        result = file_watcher.process_now()

        return jsonify({
            'success': True,
            'message': 'File check completed',
            'result': result
        })

    except Exception as e:
        logger.error(f"Error in force file check: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/file-watcher/start', methods=['POST'])
def start_file_watcher():
    """Start the file watcher service"""
    try:
        if file_watcher.is_running():
            return jsonify({
                'success': True,
                'message': 'File watcher is already running'
            })

        file_watcher.start()
        logger.info("File watcher started via API")

        return jsonify({
            'success': True,
            'message': 'File watcher started successfully'
        })

    except Exception as e:
        logger.error(f"Error starting file watcher: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/file-watcher/stop', methods=['POST'])
def stop_file_watcher():
    """Stop the file watcher service"""
    try:
        if not file_watcher.is_running():
            return jsonify({
                'success': True,
                'message': 'File watcher is not running'
            })

        file_watcher.stop()
        logger.info("File watcher stopped via API")

        return jsonify({
            'success': True,
            'message': 'File watcher stopped successfully'
        })

    except Exception as e:
        logger.error(f"Error stopping file watcher: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/reset-processed-files', methods=['POST'])
def reset_processed_files():
    """Reset the list of processed files (for testing/debugging)"""
    try:
        unified_csv_import_service.reset_processed_files()
        logger.info("Processed files list reset via API")

        return jsonify({
            'success': True,
            'message': 'Processed files list has been reset'
        })

    except Exception as e:
        logger.error(f"Error resetting processed files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Task Group 4: Daily Import Scheduler Endpoints
# ========================================================================

@csv_management_bp.route('/daily-import/status')
def get_daily_import_status():
    """
    Get daily import scheduler status.

    Returns scheduler state, next scheduled import time, and import history.
    """
    try:
        status = daily_import_scheduler.get_status()
        return jsonify({
            'success': True,
            **status
        })

    except Exception as e:
        logger.error(f"Error getting daily import scheduler status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/daily-import/manual', methods=['POST'])
def trigger_manual_import():
    """
    Trigger manual import.

    Request body (optional):
        {
            "date": "20251112"  // Optional specific date in YYYYMMDD format
        }

    Returns import results.
    """
    try:
        data = request.get_json() or {}
        specific_date = data.get('date')

        if specific_date:
            logger.info(f"Manual import requested for date: {specific_date}")
        else:
            logger.info("Manual import requested for today's date")

        result = daily_import_scheduler.manual_import(specific_date=specific_date)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in manual import trigger: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/daily-import/start', methods=['POST'])
def start_daily_import_scheduler():
    """
    Start the daily import scheduler.

    This enables automatic imports at 2:05pm PT each day.
    """
    try:
        if daily_import_scheduler.is_running():
            return jsonify({
                'success': True,
                'message': 'Daily import scheduler is already running'
            })

        daily_import_scheduler.start()
        logger.info("Daily import scheduler started via API")

        return jsonify({
            'success': True,
            'message': 'Daily import scheduler started successfully',
            'next_import': daily_import_scheduler._get_next_import_time()
        })

    except Exception as e:
        logger.error(f"Error starting daily import scheduler: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/daily-import/stop', methods=['POST'])
def stop_daily_import_scheduler():
    """
    Stop the daily import scheduler.

    This disables automatic imports (manual imports still work).
    """
    try:
        if not daily_import_scheduler.is_running():
            return jsonify({
                'success': True,
                'message': 'Daily import scheduler is not running'
            })

        daily_import_scheduler.stop()
        logger.info("Daily import scheduler stopped via API")

        return jsonify({
            'success': True,
            'message': 'Daily import scheduler stopped successfully'
        })

    except Exception as e:
        logger.error(f"Error stopping daily import scheduler: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/daily-import/history')
def get_import_history():
    """
    Get import history.

    Returns list of recent imports (last 100).
    """
    try:
        history = daily_import_scheduler.import_history

        return jsonify({
            'success': True,
            'total_imports': len(history),
            'imports': history
        })

    except Exception as e:
        logger.error(f"Error getting import history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# Import History Database Endpoints (Phase 5)
# ========================================================================

@csv_management_bp.route('/imports/history')
def get_db_import_history():
    """
    Get database-backed import history.

    Returns list of imported files from the import_history table,
    including file names, trade counts, and import times.

    Query params:
        limit: Max records to return (default: 100)
        offset: Records to skip for pagination (default: 0)
    """
    import sqlite3
    try:
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))

        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM import_history")
        total = cursor.fetchone()[0]

        # Get paginated history
        cursor.execute("""
            SELECT
                id,
                file_name,
                original_path,
                file_hash,
                import_time,
                import_batch_id,
                archive_path,
                trades_imported,
                accounts_affected
            FROM import_history
            ORDER BY import_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        imports = []
        for row in cursor.fetchall():
            imports.append({
                'id': row['id'],
                'file_name': row['file_name'],
                'original_path': row['original_path'],
                'file_hash': row['file_hash'],
                'import_time': row['import_time'],
                'import_batch_id': row['import_batch_id'],
                'archive_path': row['archive_path'],
                'trades_imported': row['trades_imported'],
                'accounts_affected': row['accounts_affected'].split(',') if row['accounts_affected'] else []
            })

        conn.close()

        return jsonify({
            'success': True,
            'total': total,
            'limit': limit,
            'offset': offset,
            'imports': imports
        })

    except Exception as e:
        logger.error(f"Error getting database import history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/imports/<import_batch_id>/trades')
def get_trades_by_import(import_batch_id: str):
    """
    Get trades imported from a specific batch/file.

    Args:
        import_batch_id: The import batch UUID

    Returns:
        List of trades from that import batch
    """
    import sqlite3
    try:
        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # First get import info
        cursor.execute("""
            SELECT file_name, import_time, trades_imported
            FROM import_history
            WHERE import_batch_id = ?
        """, (import_batch_id,))

        import_info = cursor.fetchone()
        if not import_info:
            return jsonify({
                'success': False,
                'error': f'Import batch not found: {import_batch_id}'
            }), 404

        # Get trades from this batch
        cursor.execute("""
            SELECT
                id, account, instrument, side_of_market, quantity,
                entry_price, exit_price, entry_time, exit_time,
                profit_loss, entry_execution_id, source_file
            FROM trades
            WHERE import_batch_id = ? AND (deleted = 0 OR deleted IS NULL)
            ORDER BY entry_time
        """, (import_batch_id,))

        trades = []
        for row in cursor.fetchall():
            trades.append(dict(row))

        conn.close()

        return jsonify({
            'success': True,
            'import_batch_id': import_batch_id,
            'file_name': import_info['file_name'],
            'import_time': import_info['import_time'],
            'expected_count': import_info['trades_imported'],
            'actual_count': len(trades),
            'trades': trades
        })

    except Exception as e:
        logger.error(f"Error getting trades for import {import_batch_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/imports/orphans')
def get_orphan_imports():
    """
    Get trades whose source CSV files are missing.

    Compares trades.source_file against existing files in data/ and archive/
    directories to find orphan trades.

    Query params:
        account: Optional account filter
    """
    import sqlite3
    try:
        account = request.args.get('account')

        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all unique source files from trades
        query = """
            SELECT DISTINCT source_file
            FROM trades
            WHERE (deleted = 0 OR deleted IS NULL)
              AND source_file IS NOT NULL
              AND source_file != ''
        """
        params = []

        if account:
            query += " AND account = ?"
            params.append(account)

        cursor.execute(query, params)
        source_files = [row['source_file'] for row in cursor.fetchall()]

        # Check which files exist in data/ or archive/
        data_dir = config.data_dir
        archive_dir = data_dir / 'archive'

        missing_files = []
        for filename in source_files:
            file_path = data_dir / filename
            archive_path = archive_dir / filename

            if not file_path.exists() and not archive_path.exists():
                missing_files.append(filename)

        # Get trades from missing files
        orphan_details = []
        total_orphan_trades = 0

        for filename in missing_files:
            query = """
                SELECT
                    COUNT(*) as trade_count,
                    GROUP_CONCAT(DISTINCT account) as accounts,
                    MIN(entry_time) as first_trade,
                    MAX(entry_time) as last_trade,
                    GROUP_CONCAT(id) as trade_ids
                FROM trades
                WHERE (deleted = 0 OR deleted IS NULL)
                  AND source_file = ?
            """
            params = [filename]

            if account:
                query += " AND account = ?"
                params.append(account)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row and row['trade_count'] > 0:
                orphan_details.append({
                    'source_file': filename,
                    'trade_count': row['trade_count'],
                    'accounts': row['accounts'].split(',') if row['accounts'] else [],
                    'date_range': f"{row['first_trade']} to {row['last_trade']}",
                    'trade_ids': [int(x) for x in row['trade_ids'].split(',')] if row['trade_ids'] else []
                })
                total_orphan_trades += row['trade_count']

        conn.close()

        return jsonify({
            'success': True,
            'missing_file_count': len(missing_files),
            'total_orphan_trades': total_orphan_trades,
            'orphan_files': orphan_details
        })

    except Exception as e:
        logger.error(f"Error getting orphan imports: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@csv_management_bp.route('/imports/by-file/<filename>')
def get_import_by_filename(filename: str):
    """
    Get import history for a specific file by name.

    Args:
        filename: The CSV filename (e.g., NinjaTrader_Executions_20251225.csv)

    Returns:
        Import record(s) for this file
    """
    import sqlite3
    try:
        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                file_name,
                original_path,
                file_hash,
                import_time,
                import_batch_id,
                archive_path,
                trades_imported,
                accounts_affected
            FROM import_history
            WHERE file_name = ?
            ORDER BY import_time DESC
        """, (filename,))

        imports = []
        for row in cursor.fetchall():
            imports.append({
                'id': row['id'],
                'file_name': row['file_name'],
                'original_path': row['original_path'],
                'file_hash': row['file_hash'],
                'import_time': row['import_time'],
                'import_batch_id': row['import_batch_id'],
                'archive_path': row['archive_path'],
                'trades_imported': row['trades_imported'],
                'accounts_affected': row['accounts_affected'].split(',') if row['accounts_affected'] else []
            })

        conn.close()

        if not imports:
            return jsonify({
                'success': False,
                'error': f'No import history found for file: {filename}'
            }), 404

        return jsonify({
            'success': True,
            'file_name': filename,
            'import_count': len(imports),
            'imports': imports
        })

    except Exception as e:
        logger.error(f"Error getting import by filename {filename}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
