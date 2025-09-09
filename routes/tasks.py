"""
Task Management API Routes

Flask blueprint for managing Celery tasks through REST API endpoints.
Provides integration between the web interface and the task queue system.
"""

from flask import Blueprint, request, jsonify, current_app
import logging
from typing import Dict, Any, Optional

# Import tasks conditionally to handle environments without Celery
try:
    from tasks.file_processing import (
        check_for_new_files, process_csv_file, trigger_manual_file_check
    )
    from tasks.gap_filling import (
        fill_recent_gaps, fill_gaps_for_instrument, trigger_manual_gap_fill
    )
    from tasks.position_building import (
        rebuild_all_positions, rebuild_positions_for_account, 
        trigger_manual_position_rebuild
    )
    from tasks.cache_maintenance import (
        cleanup_expired_cache, warm_cache_for_instruments,
        trigger_manual_cache_cleanup
    )
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

logger = logging.getLogger('task_api')

# Create blueprint
bp = Blueprint('tasks', __name__, url_prefix='/api/v1/tasks')


def create_task_response(task_result, task_name: str) -> Dict[str, Any]:
    """Create standardized task response"""
    if task_result:
        return {
            'success': True,
            'task_id': task_result.id,
            'task_name': task_name,
            'status': 'queued',
            'message': f'{task_name} task queued successfully'
        }
    else:
        return {
            'success': False,
            'error': f'Failed to queue {task_name} task',
            'status': 'error'
        }


def handle_celery_unavailable() -> Dict[str, Any]:
    """Handle cases where Celery is not available"""
    return {
        'success': False,
        'error': 'Task queue system is not available',
        'status': 'unavailable'
    }, 503


@bp.route('/status', methods=['GET'])
def get_task_system_status():
    """Get status of the task queue system"""
    try:
        if not CELERY_AVAILABLE:
            return jsonify({
                'system_status': 'unavailable',
                'celery_available': False,
                'message': 'Celery task queue is not available'
            })
        
        # Try to get basic system info
        from celery_app import app as celery_app
        
        # Check if we can connect to broker
        try:
            inspector = celery_app.control.inspect()
            active_workers = inspector.active()
            
            if active_workers:
                worker_count = len(active_workers)
                system_status = 'healthy'
            else:
                worker_count = 0
                system_status = 'no_workers'
                
        except Exception as e:
            logger.error(f"Error checking Celery status: {e}")
            worker_count = 0
            system_status = 'connection_error'
        
        return jsonify({
            'system_status': system_status,
            'celery_available': True,
            'worker_count': worker_count,
            'queues': ['default', 'file_processing', 'gap_filling', 'position_building', 'cache_maintenance']
        })
        
    except Exception as e:
        logger.error(f"Error getting task system status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# File Processing Tasks
@bp.route('/file-processing/check', methods=['POST'])
def trigger_file_check():
    """Trigger manual file check for new NinjaTrader executions"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        task_result = trigger_manual_file_check()
        response = create_task_response(task_result, 'file_check')
        
        logger.info(f"File check task queued: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering file check: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/file-processing/process', methods=['POST'])
def trigger_file_processing():
    """Trigger processing of a specific file"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'file_path is required'
            }), 400
        
        task_result = process_csv_file.delay(file_path)
        response = create_task_response(task_result, 'file_processing')
        
        logger.info(f"File processing task queued for {file_path}: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering file processing: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Gap Filling Tasks
@bp.route('/gap-filling/recent', methods=['POST'])
def trigger_recent_gap_fill():
    """Trigger recent gap filling (last 7 days)"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        task_result = fill_recent_gaps.delay()
        response = create_task_response(task_result, 'recent_gap_fill')
        
        logger.info(f"Recent gap fill task queued: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering recent gap fill: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/gap-filling/instrument', methods=['POST'])
def trigger_instrument_gap_fill():
    """Trigger gap filling for a specific instrument"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        data = request.get_json() or {}
        instrument = data.get('instrument')
        days_back = data.get('days_back', 7)
        
        if not instrument:
            return jsonify({
                'success': False,
                'error': 'instrument is required'
            }), 400
        
        task_result = fill_gaps_for_instrument.delay(instrument, days_back)
        response = create_task_response(task_result, f'gap_fill_{instrument}')
        
        logger.info(f"Gap fill task queued for {instrument}: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering instrument gap fill: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Position Building Tasks
@bp.route('/positions/rebuild-all', methods=['POST'])
def trigger_full_position_rebuild():
    """Trigger full position rebuild (heavy operation)"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        # Add warning for heavy operation
        data = request.get_json() or {}
        confirmed = data.get('confirmed', False)
        
        if not confirmed:
            return jsonify({
                'success': False,
                'error': 'This is a heavy operation. Please set "confirmed": true to proceed.',
                'warning': 'Full position rebuild will process all trades and may take several minutes.'
            }), 400
        
        task_result = rebuild_all_positions.delay()
        response = create_task_response(task_result, 'full_position_rebuild')
        
        logger.warning(f"Full position rebuild task queued: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering full position rebuild: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/positions/rebuild-account', methods=['POST'])
def trigger_account_position_rebuild():
    """Trigger position rebuild for specific account"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        data = request.get_json() or {}
        account = data.get('account')
        
        if not account:
            return jsonify({
                'success': False,
                'error': 'account is required'
            }), 400
        
        task_result = rebuild_positions_for_account.delay(account)
        response = create_task_response(task_result, f'position_rebuild_{account}')
        
        logger.info(f"Position rebuild task queued for account {account}: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering account position rebuild: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Cache Maintenance Tasks
@bp.route('/cache/cleanup', methods=['POST'])
def trigger_cache_cleanup():
    """Trigger cache cleanup and optimization"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        task_result = cleanup_expired_cache.delay()
        response = create_task_response(task_result, 'cache_cleanup')
        
        logger.info(f"Cache cleanup task queued: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering cache cleanup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/cache/warm', methods=['POST'])
def trigger_cache_warmup():
    """Trigger cache warm-up for instruments"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        data = request.get_json() or {}
        instruments = data.get('instruments')  # Optional, defaults to active instruments
        
        task_result = warm_cache_for_instruments.delay(instruments)
        response = create_task_response(task_result, 'cache_warmup')
        
        logger.info(f"Cache warmup task queued: {task_result.id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error triggering cache warmup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Task Status and Results
@bp.route('/result/<task_id>', methods=['GET'])
def get_task_result(task_id: str):
    """Get result of a specific task"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        from celery_app import app as celery_app
        
        result = celery_app.AsyncResult(task_id)
        
        response = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None
        }
        
        if result.ready():
            if result.successful():
                response['result'] = result.result
            else:
                response['error'] = str(result.result)
                response['traceback'] = result.traceback
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting task result for {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/active', methods=['GET'])
def get_active_tasks():
    """Get list of currently active tasks"""
    if not CELERY_AVAILABLE:
        return jsonify(handle_celery_unavailable())
    
    try:
        from celery_app import app as celery_app
        
        inspector = celery_app.control.inspect()
        active_tasks = inspector.active()
        
        if not active_tasks:
            return jsonify({
                'active_tasks': {},
                'total_active': 0
            })
        
        # Flatten the results
        all_active = []
        for worker, tasks in active_tasks.items():
            for task in tasks:
                task['worker'] = worker
                all_active.append(task)
        
        return jsonify({
            'active_tasks': active_tasks,
            'flattened_tasks': all_active,
            'total_active': len(all_active)
        })
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Utility endpoints
@bp.route('/queues', methods=['GET'])
def list_available_queues():
    """List all available task queues"""
    return jsonify({
        'queues': [
            {
                'name': 'default',
                'description': 'General purpose tasks'
            },
            {
                'name': 'file_processing',
                'description': 'File import and processing tasks'
            },
            {
                'name': 'gap_filling',
                'description': 'OHLC data gap detection and filling'
            },
            {
                'name': 'position_building',
                'description': 'Position aggregation and rebuilding'
            },
            {
                'name': 'cache_maintenance',
                'description': 'Cache cleanup and optimization'
            }
        ]
    })


# Error handlers
@bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Task endpoint not found'
    }), 404


@bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error in task management'
    }), 500