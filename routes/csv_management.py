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
from config import config

logger = logging.getLogger(__name__)
csv_management_bp = Blueprint('csv_management', __name__, url_prefix='/api/csv')


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
