"""
Background Validation Tasks

Celery tasks for automated position-execution integrity validation.
"""
from celery import Task
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import sqlite3

from celery_app import app
from config import config
from domain.services.position_execution_integrity_validator import PositionExecutionIntegrityValidator
from services.position_execution_integrity_service import PositionExecutionIntegrityService
from services.notification_service import NotificationService, NotificationPriority
from repositories.validation_repository import ValidationRepository
from domain.integrity_issue import IssueSeverity
from routes.validation import _load_position_from_db, _load_executions_from_db
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Initialize notification service
notification_service = NotificationService()


class ValidationTask(Task):
    """Base task class for validation with shared setup"""

    _service = None

    @property
    def service(self) -> PositionExecutionIntegrityService:
        """Lazy initialization of integrity service"""
        if self._service is None:
            db_path = str(config.db_path)
            validation_repo = ValidationRepository(db_path)
            validator = PositionExecutionIntegrityValidator()
            self._service = PositionExecutionIntegrityService(validator, validation_repo)
        return self._service


@app.task(
    base=ValidationTask,
    bind=True,
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def validate_position_task(self, position_id: int, auto_repair: bool = False) -> Dict:
    """
    Validate a single position in the background

    Args:
        position_id: ID of the position to validate
        auto_repair: Whether to attempt automatic repair

    Returns:
        Dictionary with validation results
    """
    try:
        logger.info(f"Starting background validation for position {position_id}")

        db_path = str(config.db_path)

        # Load position and executions
        position = _load_position_from_db(db_path, position_id)
        if not position:
            logger.warning(f"Position {position_id} not found")
            return {
                'position_id': position_id,
                'status': 'error',
                'message': 'Position not found'
            }

        executions = _load_executions_from_db(db_path, position_id)

        # Run validation
        result, issues = self.service.validate_position(position, executions, save_results=True)

        # Attempt auto-repair if requested and issues found
        repair_results = None
        if auto_repair and issues:
            logger.info(f"Attempting auto-repair for position {position_id}")
            repair_results = self.service.attempt_auto_repair(
                position_id,
                position,
                executions,
                dry_run=False
            )

        logger.info(
            f"Validation completed for position {position_id}: "
            f"status={result.status.value}, issues={len(issues)}"
        )

        return {
            'position_id': position_id,
            'status': result.status.value,
            'issue_count': len(issues),
            'issues': [issue.to_dict() for issue in issues],
            'repair_attempted': auto_repair,
            'repair_results': {
                issue_id: res.to_dict() for issue_id, res in repair_results.items()
            } if repair_results else None,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error validating position {position_id}: {e}")

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            'position_id': position_id,
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@app.task(
    base=ValidationTask,
    bind=True,
    time_limit=3600,  # 1 hour max
    soft_time_limit=3300  # 55 minutes soft limit
)
def validate_all_positions_task(
    self,
    position_status: Optional[str] = None,
    days_back: Optional[int] = None,
    auto_repair: bool = False
) -> Dict:
    """
    Validate all positions (or filtered subset) in the background

    Args:
        position_status: Filter by status ('open', 'closed', or None for all)
        days_back: Only validate positions from last N days (None for all)
        auto_repair: Whether to attempt automatic repair

    Returns:
        Dictionary with summary results
    """
    try:
        logger.info(f"Starting batch validation (status={position_status}, days_back={days_back})")

        db_path = str(config.db_path)

        # Build query to get positions
        query = "SELECT id FROM positions WHERE 1=1"
        params = []

        if position_status:
            query += " AND position_status = ?"
            params.append(position_status)

        if days_back:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            query += " AND (entry_time >= ? OR exit_time >= ?)"
            params.extend([cutoff_date, cutoff_date])

        # Fetch position IDs
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        position_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        logger.info(f"Found {len(position_ids)} positions to validate")

        # Validate each position
        results = {
            'total_positions': len(position_ids),
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'issues_found': 0,
            'critical_issues': 0,
            'repaired': 0,
            'position_results': []
        }

        for position_id in position_ids:
            try:
                # Load position and executions
                position = _load_position_from_db(db_path, position_id)
                if not position:
                    continue

                executions = _load_executions_from_db(db_path, position_id)

                # Run validation
                result, issues = self.service.validate_position(
                    position,
                    executions,
                    save_results=True
                )

                results['validated'] += 1

                if result.status.value == 'passed':
                    results['passed'] += 1
                elif result.status.value == 'failed':
                    results['failed'] += 1
                    results['issues_found'] += len(issues)

                    # Count critical issues
                    critical = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
                    results['critical_issues'] += critical

                    # Attempt auto-repair if requested
                    if auto_repair:
                        repair_results = self.service.attempt_auto_repair(
                            position_id,
                            position,
                            executions,
                            dry_run=False
                        )

                        # Count successful repairs
                        from domain.services.integrity_repair_service import RepairStatus
                        repaired = sum(
                            1 for r in repair_results.values()
                            if r.status == RepairStatus.SUCCESS
                        )
                        results['repaired'] += repaired
                else:
                    results['errors'] += 1

                # Store individual result
                results['position_results'].append({
                    'position_id': position_id,
                    'status': result.status.value,
                    'issue_count': len(issues)
                })

            except Exception as e:
                logger.error(f"Error validating position {position_id}: {e}")
                results['errors'] += 1

        logger.info(
            f"Batch validation completed: {results['validated']}/{results['total_positions']} validated, "
            f"{results['passed']} passed, {results['failed']} failed, "
            f"{results['issues_found']} issues found, {results['repaired']} repaired"
        )

        # Send notification if critical issues found
        if results['critical_issues'] > 0 or results['failed'] > 10:
            affected_positions = [
                r['position_id'] for r in results['position_results']
                if r['issue_count'] > 0
            ]

            notification_service.send_validation_alert(
                issue_count=results['issues_found'],
                critical_count=results['critical_issues'],
                position_ids=affected_positions,
                details={
                    'total_validated': results['validated'],
                    'passed': results['passed'],
                    'failed': results['failed'],
                    'repaired': results['repaired']
                }
            )

        # Send repair summary if repairs were attempted
        if auto_repair and results['repaired'] > 0:
            repaired_positions = [
                r['position_id'] for r in results['position_results']
                if r.get('repaired', 0) > 0
            ]

            notification_service.send_repair_summary(
                total_repaired=results['repaired'],
                total_failed=results['issues_found'] - results['repaired'],
                position_ids=repaired_positions
            )

        results['timestamp'] = datetime.utcnow().isoformat()
        return results

    except Exception as e:
        logger.error(f"Error in batch validation: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@app.task(
    base=ValidationTask,
    bind=True
)
def validate_recent_positions_task(self, hours: int = 24, auto_repair: bool = True) -> Dict:
    """
    Validate positions that were recently created or modified

    Args:
        hours: Number of hours to look back
        auto_repair: Whether to attempt automatic repair

    Returns:
        Dictionary with validation results
    """
    days_back = max(1, hours // 24)  # Convert to days for query

    logger.info(f"Validating positions from last {hours} hours")

    return validate_all_positions_task(
        position_status=None,
        days_back=days_back,
        auto_repair=auto_repair
    )


@app.task(
    base=ValidationTask,
    bind=True
)
def get_validation_statistics_task(self) -> Dict:
    """
    Get overall validation statistics

    Returns:
        Dictionary with statistics
    """
    try:
        stats = self.service.get_validation_statistics()
        stats['timestamp'] = datetime.utcnow().isoformat()
        return stats
    except Exception as e:
        logger.error(f"Error getting validation statistics: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }