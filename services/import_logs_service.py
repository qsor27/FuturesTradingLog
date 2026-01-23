"""
Import Logs Service

Provides business logic for import execution logging including:
- Recording import execution metadata
- Logging row-by-row processing results
- Querying import logs with filtering
- Retry and rollback operations
- Export functionality
"""

import json
import logging
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

from scripts.database_manager import DatabaseManager
from models.import_execution import (
    ImportExecutionLog,
    ImportExecutionRowLog,
    ImportExecutionSummary,
    ImportStatus,
    RowStatus,
    ErrorCategory
)

# Setup logging
logger = logging.getLogger(__name__)


class ImportLogsService:
    """Service class for import execution logging"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize service with optional database path"""
        self.db_path = db_path
        logger.info("ImportLogsService initialized")

    @contextmanager
    def _get_db(self):
        """Get database connection context manager"""
        with DatabaseManager(self.db_path) as db:
            yield db

    # ========== IMPORT EXECUTION LOG MANAGEMENT ==========

    def create_import_log(self, log_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new import execution log entry.

        Args:
            log_data: Dictionary containing import log data

        Returns:
            Tuple of (success, message, import_batch_id)
        """
        try:
            # Validate using Pydantic model
            log_model = ImportExecutionLog(**log_data)

            with self._get_db() as db:
                # Insert into database
                db.cursor.execute("""
                    INSERT INTO import_execution_logs (
                        import_batch_id, file_name, file_path, file_hash,
                        import_time, status, total_rows, success_rows,
                        failed_rows, skipped_rows, processing_time_ms,
                        affected_accounts, error_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_model.import_batch_id,
                    log_model.file_name,
                    log_model.file_path,
                    log_model.file_hash,
                    log_model.import_time,
                    log_model.status,  # Already converted to string by use_enum_values
                    log_model.total_rows,
                    log_model.success_rows,
                    log_model.failed_rows,
                    log_model.skipped_rows,
                    log_model.processing_time_ms,
                    log_model.affected_accounts,
                    log_model.error_summary,
                    log_model.created_at
                ))

                db.commit()

                logger.info(f"Created import log: {log_model.import_batch_id}")
                return True, "Import log created", log_model.import_batch_id

        except Exception as e:
            logger.error(f"Error creating import log: {e}")
            return False, f"Failed to create import log: {str(e)}", None

    def update_import_log(self, import_batch_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Update an existing import execution log.

        Args:
            import_batch_id: Batch ID to update
            updates: Dictionary of fields to update

        Returns:
            Tuple of (success, message)
        """
        try:
            with self._get_db() as db:
                # Build UPDATE query dynamically
                set_clauses = []
                values = []

                for key, value in updates.items():
                    set_clauses.append(f"{key} = ?")
                    values.append(value)

                values.append(import_batch_id)

                query = f"""
                    UPDATE import_execution_logs
                    SET {', '.join(set_clauses)}
                    WHERE import_batch_id = ?
                """

                db.cursor.execute(query, values)
                db.commit()

                logger.info(f"Updated import log: {import_batch_id}")
                return True, "Import log updated"

        except Exception as e:
            logger.error(f"Error updating import log: {e}")
            return False, f"Failed to update import log: {str(e)}"

    def create_row_log(self, row_data: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
        """
        Create a row-level import log entry.

        Args:
            row_data: Dictionary containing row log data

        Returns:
            Tuple of (success, message, row_log_id)
        """
        try:
            # Validate using Pydantic model
            row_model = ImportExecutionRowLog(**row_data)

            with self._get_db() as db:
                # Insert into database
                db.cursor.execute("""
                    INSERT INTO import_execution_row_logs (
                        import_batch_id, row_number, status, error_message,
                        error_category, raw_row_data, validation_errors,
                        created_trade_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_model.import_batch_id,
                    row_model.row_number,
                    row_model.status,  # Already converted to string by use_enum_values
                    row_model.error_message,
                    row_model.error_category if row_model.error_category else None,  # Already converted
                    row_model.raw_row_data,
                    row_model.validation_errors,
                    row_model.created_trade_id,
                    row_model.created_at
                ))

                row_id = db.cursor.lastrowid
                db.commit()

                return True, "Row log created", row_id

        except Exception as e:
            logger.error(f"Error creating row log: {e}")
            return False, f"Failed to create row log: {str(e)}", None

    def create_row_logs_batch(self, rows: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
        """
        Create multiple row logs in a single transaction for performance.

        Args:
            rows: List of row log dictionaries

        Returns:
            Tuple of (success, message, rows_created)
        """
        try:
            with self._get_db() as db:
                created_count = 0

                for row_data in rows:
                    row_model = ImportExecutionRowLog(**row_data)

                    db.cursor.execute("""
                        INSERT INTO import_execution_row_logs (
                            import_batch_id, row_number, status, error_message,
                            error_category, raw_row_data, validation_errors,
                            created_trade_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row_model.import_batch_id,
                        row_model.row_number,
                        row_model.status,  # Already converted to string by use_enum_values
                        row_model.error_message,
                        row_model.error_category if row_model.error_category else None,  # Already converted
                        row_model.raw_row_data,
                        row_model.validation_errors,
                        row_model.created_trade_id,
                        row_model.created_at
                    ))

                    created_count += 1

                db.commit()

                logger.info(f"Created {created_count} row logs in batch")
                return True, f"Created {created_count} row logs", created_count

        except Exception as e:
            logger.error(f"Error creating batch row logs: {e}")
            return False, f"Failed to create batch row logs: {str(e)}", 0

    # ========== QUERY OPERATIONS ==========

    def get_import_logs(
        self,
        status: Optional[str] = None,
        account: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get import logs with optional filtering.

        Args:
            status: Filter by status (success, partial, failed)
            account: Filter by account name
            start_date: Filter by import date (from)
            end_date: Filter by import date (to)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of import log dictionaries
        """
        try:
            with self._get_db() as db:
                query = "SELECT * FROM import_execution_logs WHERE 1=1"
                params = []

                # Apply filters
                if status:
                    query += " AND status = ?"
                    params.append(status)

                if account:
                    query += " AND affected_accounts LIKE ?"
                    params.append(f'%"{account}"%')

                if start_date:
                    query += " AND import_time >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND import_time <= ?"
                    params.append(end_date)

                # Order by most recent first
                query += " ORDER BY import_time DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                db.cursor.execute(query, params)
                rows = db.cursor.fetchall()

                # Convert to dictionaries
                results = []
                for row in rows:
                    results.append(dict(row))

                logger.debug(f"Retrieved {len(results)} import logs")
                return results

        except Exception as e:
            logger.error(f"Error retrieving import logs: {e}")
            return []

    def get_import_log_by_batch_id(self, import_batch_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific import log by batch ID"""
        try:
            with self._get_db() as db:
                db.cursor.execute(
                    "SELECT * FROM import_execution_logs WHERE import_batch_id = ?",
                    (import_batch_id,)
                )
                row = db.cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Error retrieving import log: {e}")
            return None

    def get_row_logs(self, import_batch_id: str) -> List[Dict[str, Any]]:
        """Get all row-level logs for a specific import"""
        try:
            with self._get_db() as db:
                db.cursor.execute("""
                    SELECT * FROM import_execution_row_logs
                    WHERE import_batch_id = ?
                    ORDER BY row_number ASC
                """, (import_batch_id,))

                rows = db.cursor.fetchall()

                # Convert to dictionaries
                results = []
                for row in rows:
                    results.append(dict(row))

                logger.debug(f"Retrieved {len(results)} row logs for {import_batch_id}")
                return results

        except Exception as e:
            logger.error(f"Error retrieving row logs: {e}")
            return []

    def get_failed_row_logs(self, import_batch_id: str) -> List[Dict[str, Any]]:
        """Get only failed row logs for a specific import"""
        try:
            with self._get_db() as db:
                db.cursor.execute("""
                    SELECT * FROM import_execution_row_logs
                    WHERE import_batch_id = ? AND status = 'failed'
                    ORDER BY row_number ASC
                """, (import_batch_id,))

                rows = db.cursor.fetchall()

                results = []
                for row in rows:
                    results.append(dict(row))

                logger.debug(f"Retrieved {len(results)} failed row logs for {import_batch_id}")
                return results

        except Exception as e:
            logger.error(f"Error retrieving failed row logs: {e}")
            return []

    def get_affected_trades(self, import_batch_id: str) -> List[Dict[str, Any]]:
        """Get all trades created by a specific import"""
        try:
            with self._get_db() as db:
                db.cursor.execute("""
                    SELECT t.*
                    FROM trades t
                    WHERE t.import_batch_id = ?
                    ORDER BY t.entry_time ASC
                """, (import_batch_id,))

                rows = db.cursor.fetchall()

                results = []
                for row in rows:
                    results.append(dict(row))

                logger.debug(f"Retrieved {len(results)} trades for {import_batch_id}")
                return results

        except Exception as e:
            logger.error(f"Error retrieving affected trades: {e}")
            return []

    # ========== RETRY AND ROLLBACK OPERATIONS ==========

    def retry_import(self, import_batch_id: str) -> Tuple[bool, str]:
        """
        Retry a failed import by moving file back to import directory.

        Args:
            import_batch_id: Batch ID to retry

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get import log
            import_log = self.get_import_log_by_batch_id(import_batch_id)
            if not import_log:
                return False, f"Import log not found: {import_batch_id}"

            file_path = Path(import_log['file_path'])

            # Check if file still exists (might be in archive)
            if not file_path.exists():
                # Try to find in archive
                from config import config
                archive_path = config.data_dir / 'archive' / file_path.name
                if archive_path.exists():
                    # Move from archive back to data directory
                    target_path = config.data_dir / file_path.name
                    shutil.move(str(archive_path), str(target_path))
                    logger.info(f"Moved {file_path.name} from archive for retry")

                    return True, f"File moved back for retry: {file_path.name}"
                else:
                    return False, f"File not found: {file_path.name}"

            return True, f"File ready for retry: {file_path.name}"

        except Exception as e:
            logger.error(f"Error retrying import: {e}")
            return False, f"Failed to retry import: {str(e)}"

    def rollback_import(self, import_batch_id: str) -> Tuple[bool, str]:
        """
        Rollback an import by deleting all created trades and clearing cache.

        Args:
            import_batch_id: Batch ID to rollback

        Returns:
            Tuple of (success, message)
        """
        try:
            with self._get_db() as db:
                # Get count of trades to delete
                db.cursor.execute("""
                    SELECT COUNT(*) as count FROM trades
                    WHERE import_batch_id = ?
                """, (import_batch_id,))

                count = db.cursor.fetchone()['count']

                if count == 0:
                    return True, "No trades to rollback"

                # Delete trades (soft delete)
                db.cursor.execute("""
                    UPDATE trades
                    SET deleted = 1
                    WHERE import_batch_id = ?
                """, (import_batch_id,))

                db.commit()

                # Invalidate cache
                try:
                    from scripts.cache_manager import get_cache_manager
                    cache_manager = get_cache_manager()
                    cache_manager.invalidate_all_caches()
                except Exception as cache_err:
                    logger.warning(f"Could not invalidate cache: {cache_err}")

                logger.info(f"Rolled back {count} trades for {import_batch_id}")
                return True, f"Rolled back {count} trades"

        except Exception as e:
            logger.error(f"Error rolling back import: {e}")
            return False, f"Failed to rollback import: {str(e)}"

    # ========== EXPORT OPERATIONS ==========

    def export_logs_to_json(self, import_batch_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        Export import logs to JSON format.

        Args:
            import_batch_id: Batch ID to export

        Returns:
            Tuple of (success, message, json_data)
        """
        try:
            import_log = self.get_import_log_by_batch_id(import_batch_id)
            if not import_log:
                return False, "Import log not found", None

            row_logs = self.get_row_logs(import_batch_id)

            export_data = {
                'import_log': import_log,
                'row_logs': row_logs,
                'exported_at': datetime.now().isoformat()
            }

            json_data = json.dumps(export_data, indent=2, default=str)

            return True, "Export successful", json_data

        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return False, f"Failed to export logs: {str(e)}", None

    # ========== UTILITY METHODS ==========

    @staticmethod
    def generate_batch_id(file_path: str) -> str:
        """Generate unique batch ID for an import"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = Path(file_path).stem
        return f"batch_{timestamp}_{file_name}"

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()
