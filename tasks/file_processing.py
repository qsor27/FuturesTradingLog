"""
File Processing Tasks

Celery tasks for handling file imports, processing, and monitoring.
Replaces the threading-based file watcher service.
"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import json
import shutil
from typing import List, Dict, Any, Optional

from celery import Task
from celery_app import app
from config import config
from database_manager import DatabaseManager

# Import cache manager for invalidation
try:
    from cache_manager import get_cache_manager
    CACHE_INVALIDATION_AVAILABLE = True
except ImportError:
    CACHE_INVALIDATION_AVAILABLE = False
    logger.warning("Cache invalidation not available in Celery tasks")

# Import ExecutionProcessing conditionally
try:
    from ExecutionProcessing import process_trades
    EXECUTION_PROCESSING_AVAILABLE = True
except ImportError as e:
    process_trades = None
    EXECUTION_PROCESSING_AVAILABLE = False

logger = logging.getLogger('file_processing')


def _invalidate_cache_for_import(result: Dict[str, Any]) -> None:
    """Helper function to invalidate cache after file processing"""
    if not CACHE_INVALIDATION_AVAILABLE:
        return
    
    try:
        accounts_processed = result.get('accounts_processed', [])
        
        if accounts_processed:
            cache_manager = get_cache_manager()
            
            # For file processing, we don't know specific instruments yet
            # So we invalidate by account and let position rebuild handle instruments
            for account in accounts_processed:
                invalidation_result = cache_manager.on_position_rebuild(account)
                logger.info(f"Cache invalidated for account {account}: {invalidation_result.get('invalidation_results', {})}")
    
    except Exception as e:
        logger.error(f"Cache invalidation failed in file processing: {e}")
        # Don't raise - cache invalidation failure shouldn't stop processing


class CallbackTask(Task):
    """Base task class with error handling and monitoring"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f'Task {task_id} failed: {exc}')
        logger.error(f'Exception info: {einfo}')
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f'Task {task_id} completed successfully')


@app.task(base=CallbackTask, bind=True)
def check_for_new_files(self):
    """
    Check data directory for new NinjaTrader execution files
    Scheduled to run every 5 minutes
    """
    try:
        if not config.auto_import_enabled:
            logger.debug("Auto-import is disabled, skipping file check")
            return {'status': 'skipped', 'reason': 'auto_import_disabled'}
        
        if not EXECUTION_PROCESSING_AVAILABLE:
            logger.warning("ExecutionProcessing module not available")
            return {'status': 'error', 'reason': 'execution_processing_unavailable'}
        
        # Get list of CSV files in data directory
        data_dir = Path(config.data_dir)
        csv_files = list(data_dir.glob("NinjaTrader_Executions_*.csv"))
        
        if not csv_files:
            logger.debug("No NinjaTrader execution files found")
            return {'status': 'no_files', 'files_found': 0}
        
        # Load processed files tracker
        processed_files = _load_processed_files()
        new_files = []
        
        for csv_file in csv_files:
            file_path_str = str(csv_file)
            file_stat = csv_file.stat()
            file_key = f"{file_path_str}:{file_stat.st_mtime}"
            
            if file_key not in processed_files:
                new_files.append({
                    'path': file_path_str,
                    'size': file_stat.st_size,
                    'modified': file_stat.st_mtime,
                    'key': file_key
                })
        
        if not new_files:
            logger.debug(f"No new files to process. Found {len(csv_files)} already processed files.")
            return {'status': 'no_new_files', 'total_files': len(csv_files)}
        
        # Process new files
        results = []
        for file_info in new_files:
            try:
                # Trigger file processing task
                result = process_csv_file.delay(file_info['path'])
                results.append({
                    'file': file_info['path'],
                    'task_id': result.id,
                    'status': 'queued'
                })
                
                # Mark as processed
                processed_files.add(file_info['key'])
                
                logger.info(f"Queued processing for file: {file_info['path']}")
                
            except Exception as e:
                logger.error(f"Failed to queue processing for {file_info['path']}: {e}")
                results.append({
                    'file': file_info['path'],
                    'status': 'error',
                    'error': str(e)
                })
        
        # Save updated processed files list
        _save_processed_files(processed_files)
        
        return {
            'status': 'success',
            'new_files_found': len(new_files),
            'processing_results': results
        }
        
    except Exception as e:
        logger.error(f"Error in check_for_new_files: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@app.task(base=CallbackTask, bind=True)
def process_csv_file(self, file_path: str):
    """
    Process a single CSV file containing NinjaTrader executions
    
    Args:
        file_path: Path to the CSV file to process
    """
    try:
        logger.info(f"Processing CSV file: {file_path}")
        
        if not EXECUTION_PROCESSING_AVAILABLE:
            raise ValueError("ExecutionProcessing module not available")
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file security
        from ExecutionProcessing import validate_file_security
        is_valid, error_msg = validate_file_security(file_path)
        if not is_valid:
            raise ValueError(f"File security validation failed: {error_msg}")
        
        # Load instrument multipliers
        multipliers = _load_multipliers()
        
        # Process the trades
        result = process_trades(
            csv_file_path=file_path,
            multipliers=multipliers,
            delete_existing=False  # Don't delete existing trades
        )
        
        if result.get('success', False):
            # Archive the processed file
            _archive_processed_file(file_path_obj)
            
            # Invalidate cache for processed data
            _invalidate_cache_for_import(result)
            
            # Trigger position rebuild if needed
            if result.get('trades_imported', 0) > 0:
                rebuild_positions_for_accounts.delay(
                    accounts=result.get('accounts_processed', [])
                )
            
            logger.info(f"Successfully processed {file_path}: {result.get('trades_imported', 0)} trades imported")
            
            return {
                'status': 'success',
                'file': file_path,
                'trades_imported': result.get('trades_imported', 0),
                'accounts_processed': result.get('accounts_processed', []),
                'processing_time': result.get('processing_time', 0)
            }
        else:
            error_msg = result.get('error', 'Unknown error during processing')
            logger.error(f"Failed to process {file_path}: {error_msg}")
            raise ValueError(error_msg)
            
    except Exception as e:
        logger.error(f"Error processing CSV file {file_path}: {e}")
        raise self.retry(exc=e, countdown=120, max_retries=2)


@app.task(base=CallbackTask, bind=True)
def rebuild_positions_for_accounts(self, accounts: List[str]):
    """
    Rebuild positions for specific accounts after new trade imports
    
    Args:
        accounts: List of account names to rebuild positions for
    """
    try:
        from tasks.position_building import rebuild_positions_for_account
        
        logger.info(f"Rebuilding positions for accounts: {accounts}")
        
        results = []
        for account in accounts:
            try:
                # Queue individual account rebuild
                result = rebuild_positions_for_account.delay(account)
                results.append({
                    'account': account,
                    'task_id': result.id,
                    'status': 'queued'
                })
                logger.info(f"Queued position rebuild for account: {account}")
                
            except Exception as e:
                logger.error(f"Failed to queue position rebuild for {account}: {e}")
                results.append({
                    'account': account,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'accounts_processed': len(accounts),
            'rebuild_results': results
        }
        
    except Exception as e:
        logger.error(f"Error in rebuild_positions_for_accounts: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=2)


def _load_processed_files() -> set:
    """Load the set of already processed files"""
    try:
        processed_files_path = Path(config.data_dir) / 'processed_files.json'
        if processed_files_path.exists():
            with open(processed_files_path, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_files', []))
        return set()
    except Exception as e:
        logger.warning(f"Could not load processed files list: {e}")
        return set()


def _save_processed_files(processed_files: set) -> None:
    """Save the set of processed files"""
    try:
        processed_files_path = Path(config.data_dir) / 'processed_files.json'
        data = {
            'processed_files': list(processed_files),
            'last_updated': datetime.now().isoformat()
        }
        with open(processed_files_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save processed files list: {e}")


def _load_multipliers() -> Dict[str, int]:
    """Load instrument multipliers from config"""
    try:
        multipliers_path = Path(config.data_dir) / 'config' / 'instrument_multipliers.json'
        if multipliers_path.exists():
            with open(multipliers_path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Could not load instrument multipliers: {e}")
        return {}


def _archive_processed_file(file_path: Path) -> None:
    """Move processed file to archive directory"""
    try:
        archive_dir = Path(config.data_dir) / 'archive'
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archived_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        archive_path = archive_dir / archived_name
        
        shutil.move(str(file_path), str(archive_path))
        logger.info(f"Archived processed file: {file_path} -> {archive_path}")
        
    except Exception as e:
        logger.warning(f"Could not archive processed file {file_path}: {e}")


# Manual task triggers for API endpoints
@app.task(base=CallbackTask)
def trigger_manual_file_check():
    """Manually trigger file check (for API endpoints)"""
    return check_for_new_files.delay()


@app.task(base=CallbackTask)
def process_specific_file(file_path: str):
    """Process a specific file manually (for API endpoints)"""
    return process_csv_file.delay(file_path)