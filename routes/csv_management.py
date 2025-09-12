"""
CSV Management Routes for Unified Import System

Provides manual re-processing interface and file management for CSV imports.
"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import logging
from typing import Dict, Any, List

from services.unified_csv_import_service import unified_csv_import_service
from services.file_watcher import file_watcher
from config import config

logger = logging.getLogger(__name__)
csv_management_bp = Blueprint('csv_management', __name__, url_prefix='/api/csv')


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