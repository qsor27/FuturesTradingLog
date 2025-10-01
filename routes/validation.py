"""
Validation API Routes

REST API endpoints for position-execution integrity validation operations.
"""
from flask import Blueprint, request, jsonify
from typing import Optional
from datetime import datetime

from services.position_execution_integrity_service import PositionExecutionIntegrityService
from domain.services.position_execution_integrity_validator import PositionExecutionIntegrityValidator
from repositories.validation_repository import ValidationRepository
from domain.integrity_issue import IssueSeverity, ResolutionStatus
from utils.logging_config import get_logger
from config import config
from scripts.TradingLog_db import FuturesDB

logger = get_logger(__name__)

# Create blueprint
validation_bp = Blueprint('validation', __name__, url_prefix='/api/validation')

# Initialize services (will be injected via app context)
_integrity_service: Optional[PositionExecutionIntegrityService] = None


def init_validation_routes(app):
    """Initialize validation routes with app context"""
    global _integrity_service

    db_path = app.config.get('DATABASE_PATH', str(config.db_path))

    # Initialize repositories
    validation_repo = ValidationRepository(str(db_path))

    # Initialize validator and service
    validator = PositionExecutionIntegrityValidator()
    _integrity_service = PositionExecutionIntegrityService(validator, validation_repo)

    logger.info("Validation routes initialized")


def get_integrity_service() -> PositionExecutionIntegrityService:
    """Get the integrity service instance"""
    if _integrity_service is None:
        raise RuntimeError("Validation routes not initialized. Call init_validation_routes() first.")
    return _integrity_service


def _load_position_from_db(db_path: str, position_id: int):
    """Load position from database and convert to domain model"""
    import sqlite3
    from domain.models.position import Position, PositionType, PositionStatus

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Check if integrity fields exist in the row
    try:
        last_validated_at = row['last_validated_at']
        last_validated_at = datetime.fromisoformat(last_validated_at) if last_validated_at else None
    except (KeyError, IndexError):
        last_validated_at = None

    try:
        validation_status = row['validation_status'] or 'not_validated'
    except (KeyError, IndexError):
        validation_status = 'not_validated'

    try:
        integrity_score = row['integrity_score'] or 0.0
    except (KeyError, IndexError):
        integrity_score = 0.0

    return Position(
        id=row['id'],
        instrument=row['instrument'],
        account=row['account'],
        position_type=PositionType[row['position_type'].upper()],
        position_status=PositionStatus[row['position_status'].upper()],
        entry_time=datetime.fromisoformat(row['entry_time']),
        exit_time=datetime.fromisoformat(row['exit_time']) if row['exit_time'] else None,
        total_quantity=row['total_quantity'],
        max_quantity=row['max_quantity'],
        average_entry_price=row['average_entry_price'],
        execution_count=row['execution_count'],
        last_validated_at=last_validated_at,
        validation_status=validation_status,
        integrity_score=integrity_score
    )


def _load_executions_from_db(db_path: str, position_id: int):
    """Load executions for position from database and convert to domain models"""
    import sqlite3
    from domain.models.execution import Execution

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM executions WHERE trade_id = ? ORDER BY execution_time",
        (position_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    executions = []
    for row in rows:
        try:
            trade_id = row['trade_id']
        except (KeyError, IndexError):
            trade_id = None

        try:
            processed = bool(row['processed'])
        except (KeyError, IndexError):
            processed = False

        executions.append(Execution(
            id=row['id'],
            execution_id=row['execution_id'],
            instrument=row['instrument'],
            account=row['account'],
            side_of_market=row['side_of_market'],
            quantity=row['quantity'],
            price=row['price'],
            execution_time=datetime.fromisoformat(row['execution_time']),
            trade_id=trade_id,
            processed=processed
        ))

    return executions


@validation_bp.route('/positions/<int:position_id>', methods=['POST'])
def validate_position(position_id: int):
    """
    Validate a single position against its executions

    POST /api/validation/positions/{id}

    Query Parameters:
        - save_results: bool (default=True) - Whether to save validation results

    Returns:
        {
            "validation_id": int,
            "position_id": int,
            "status": str,
            "timestamp": str,
            "issue_count": int,
            "issues": [...]
        }
    """
    try:
        from flask import current_app
        service = get_integrity_service()
        save_results = request.args.get('save_results', 'true').lower() == 'true'

        # Get database path from Flask app config (for testing) or global config
        db_path = current_app.config.get('DATABASE_PATH', str(config.db_path))

        # Load position from database
        position = _load_position_from_db(db_path, position_id)

        if not position:
            return jsonify({
                "error": "Position not found",
                "position_id": position_id
            }), 404

        # Load executions for this position
        executions = _load_executions_from_db(db_path, position_id)

        # Run validation
        result, issues = service.validate_position(position, executions, save_results)

        return jsonify({
            "validation_id": result.validation_id,
            "position_id": result.position_id,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "issue_count": result.issue_count,
            "issues": [issue.to_dict() for issue in issues]
        }), 200

    except Exception as e:
        logger.error(f"Error validating position {position_id}: {e}")
        return jsonify({
            "error": "Validation failed",
            "message": str(e)
        }), 500


@validation_bp.route('/batch', methods=['POST'])
def validate_batch():
    """
    Validate multiple positions in batch

    POST /api/validation/batch

    Request Body:
        {
            "position_ids": [1, 2, 3, ...],
            "save_results": true
        }

    Returns:
        {
            "total_positions": int,
            "passed": int,
            "failed": int,
            "errors": int,
            "results": {
                "position_id": {
                    "validation_id": int,
                    "status": str,
                    "issue_count": int
                },
                ...
            }
        }
    """
    try:
        from flask import current_app
        service = get_integrity_service()
        data = request.get_json()

        if not data or 'position_ids' not in data:
            return jsonify({
                "error": "Invalid request",
                "message": "position_ids required in request body"
            }), 400

        position_ids = data['position_ids']
        save_results = data.get('save_results', True)

        # Get database path from Flask app config (for testing) or global config
        db_path = current_app.config.get('DATABASE_PATH', str(config.db_path))

        positions = []
        executions_by_position = {}

        for position_id in position_ids:
            position = _load_position_from_db(db_path, position_id)
            if position:
                positions.append(position)
                executions = _load_executions_from_db(db_path, position_id)
                executions_by_position[position_id] = executions

        # Run batch validation
        results = service.validate_positions_batch(
            positions,
            executions_by_position,
            save_results
        )

        # Summarize results
        passed = sum(1 for r, _ in results.values() if r.status.value == 'passed')
        failed = sum(1 for r, _ in results.values() if r.status.value == 'failed')
        errors = sum(1 for r, _ in results.values() if r.status.value == 'error')

        return jsonify({
            "total_positions": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "results": {
                pos_id: {
                    "validation_id": result.validation_id,
                    "status": result.status.value,
                    "issue_count": result.issue_count,
                    "timestamp": result.timestamp.isoformat()
                }
                for pos_id, (result, _) in results.items()
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in batch validation: {e}")
        return jsonify({
            "error": "Batch validation failed",
            "message": str(e)
        }), 500


@validation_bp.route('/results/<int:validation_id>', methods=['GET'])
def get_validation_result(validation_id: int):
    """
    Get validation result by ID

    GET /api/validation/results/{id}

    Returns:
        {
            "validation_id": int,
            "position_id": int,
            "status": str,
            "timestamp": str,
            "issue_count": int,
            "issues": [...]
        }
    """
    try:
        from flask import current_app
        service = get_integrity_service()

        # Get database path from Flask app config (for testing) or global config
        db_path = current_app.config.get('DATABASE_PATH', str(config.db_path))

        # Get validation result
        from repositories.validation_repository import ValidationRepository
        validation_repo = ValidationRepository(db_path)

        result = validation_repo.get_validation_result(validation_id)

        if not result:
            return jsonify({
                "error": "Validation result not found",
                "validation_id": validation_id
            }), 404

        # Get issues for this validation
        issues = validation_repo.get_integrity_issues(validation_id=validation_id)

        return jsonify({
            "validation_id": result.validation_id,
            "position_id": result.position_id,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "issue_count": result.issue_count,
            "validation_type": result.validation_type,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_message": result.error_message,
            "issues": [issue.to_dict() for issue in issues]
        }), 200

    except Exception as e:
        logger.error(f"Error getting validation result {validation_id}: {e}")
        return jsonify({
            "error": "Failed to get validation result",
            "message": str(e)
        }), 500


@validation_bp.route('/issues', methods=['GET'])
def get_integrity_issues():
    """
    Get integrity issues with optional filtering

    GET /api/validation/issues

    Query Parameters:
        - position_id: int (optional) - Filter by position
        - severity: str (optional) - Filter by severity (critical, high, medium, low, info)
        - resolution_status: str (optional) - Filter by status (open, in_progress, resolved, ignored, failed)
        - limit: int (default=100) - Maximum number of results

    Returns:
        {
            "total": int,
            "issues": [...]
        }
    """
    try:
        service = get_integrity_service()

        # Parse query parameters
        position_id = request.args.get('position_id', type=int)
        severity_str = request.args.get('severity')
        resolution_status_str = request.args.get('resolution_status', 'open')
        limit = request.args.get('limit', type=int, default=100)

        # Convert string parameters to enums
        severity = None
        if severity_str:
            try:
                severity = IssueSeverity[severity_str.upper()]
            except KeyError:
                return jsonify({
                    "error": "Invalid severity",
                    "message": f"Severity must be one of: critical, high, medium, low, info"
                }), 400

        resolution_status = None
        if resolution_status_str:
            try:
                resolution_status = ResolutionStatus[resolution_status_str.upper()]
            except KeyError:
                return jsonify({
                    "error": "Invalid resolution status",
                    "message": f"Status must be one of: open, in_progress, resolved, ignored, failed"
                }), 400

        # Get database path from Flask app config (for testing) or global config
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH', str(config.db_path))

        # Get issues from repository
        from repositories.validation_repository import ValidationRepository
        validation_repo = ValidationRepository(db_path)

        issues = validation_repo.get_integrity_issues(
            position_id=position_id,
            resolution_status=resolution_status,
            severity=severity,
            limit=limit
        )

        return jsonify({
            "total": len(issues),
            "issues": [issue.to_dict() for issue in issues]
        }), 200

    except Exception as e:
        logger.error(f"Error getting integrity issues: {e}")
        return jsonify({
            "error": "Failed to get integrity issues",
            "message": str(e)
        }), 500


@validation_bp.route('/issues/<int:issue_id>/resolve', methods=['POST'])
def resolve_issue(issue_id: int):
    """
    Mark an issue as resolved

    POST /api/validation/issues/{id}/resolve

    Request Body:
        {
            "resolution_method": str,
            "resolution_details": dict (optional)
        }

    Returns:
        {
            "success": bool,
            "issue_id": int,
            "message": str
        }
    """
    try:
        service = get_integrity_service()
        data = request.get_json()

        if not data or 'resolution_method' not in data:
            return jsonify({
                "error": "Invalid request",
                "message": "resolution_method required in request body"
            }), 400

        resolution_method = data['resolution_method']
        resolution_details = data.get('resolution_details')

        success = service.resolve_issue(issue_id, resolution_method, resolution_details)

        if success:
            return jsonify({
                "success": True,
                "issue_id": issue_id,
                "message": "Issue resolved successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "issue_id": issue_id,
                "message": "Failed to resolve issue"
            }), 500

    except Exception as e:
        logger.error(f"Error resolving issue {issue_id}: {e}")
        return jsonify({
            "error": "Failed to resolve issue",
            "message": str(e)
        }), 500


@validation_bp.route('/issues/<int:issue_id>/ignore', methods=['POST'])
def ignore_issue(issue_id: int):
    """
    Mark an issue as ignored

    POST /api/validation/issues/{id}/ignore

    Request Body:
        {
            "reason": str
        }

    Returns:
        {
            "success": bool,
            "issue_id": int,
            "message": str
        }
    """
    try:
        service = get_integrity_service()
        data = request.get_json()

        if not data or 'reason' not in data:
            return jsonify({
                "error": "Invalid request",
                "message": "reason required in request body"
            }), 400

        reason = data['reason']
        success = service.ignore_issue(issue_id, reason)

        if success:
            return jsonify({
                "success": True,
                "issue_id": issue_id,
                "message": "Issue ignored successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "issue_id": issue_id,
                "message": "Failed to ignore issue"
            }), 500

    except Exception as e:
        logger.error(f"Error ignoring issue {issue_id}: {e}")
        return jsonify({
            "error": "Failed to ignore issue",
            "message": str(e)
        }), 500


@validation_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Get validation statistics

    GET /api/validation/statistics

    Returns:
        {
            "total_validations": int,
            "status_counts": {
                "passed": int,
                "failed": int,
                "error": int
            },
            "total_issues": int,
            "open_issues": int,
            "severity_counts": {
                "critical": int,
                "high": int,
                "medium": int,
                "low": int,
                "info": int
            },
            "pass_rate": float,
            "resolution_rate": float
        }
    """
    try:
        service = get_integrity_service()
        stats = service.get_validation_statistics()

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error getting validation statistics: {e}")
        return jsonify({
            "error": "Failed to get statistics",
            "message": str(e)
        }), 500


@validation_bp.route('/positions/<int:position_id>/score', methods=['GET'])
def get_position_integrity_score(position_id: int):
    """
    Get integrity score for a position

    GET /api/validation/positions/{id}/score

    Returns:
        {
            "position_id": int,
            "integrity_score": float,
            "last_validated_at": str
        }
    """
    try:
        service = get_integrity_service()
        score = service.get_position_integrity_score(position_id)

        # Get last validation time
        results = service.get_validation_results_for_position(position_id, limit=1)
        last_validated = results[0].timestamp.isoformat() if results else None

        return jsonify({
            "position_id": position_id,
            "integrity_score": score,
            "last_validated_at": last_validated
        }), 200

    except Exception as e:
        logger.error(f"Error getting integrity score for position {position_id}: {e}")
        return jsonify({
            "error": "Failed to get integrity score",
            "message": str(e)
        }), 500


@validation_bp.route('/issues/<int:issue_id>/repair', methods=['POST'])
def repair_issue(issue_id: int):
    """
    Attempt to repair a specific integrity issue

    POST /api/validation/issues/{id}/repair

    Request body:
        {
            "position_id": int,
            "dry_run": bool (optional, default false)
        }

    Returns:
        {
            "issue_id": int,
            "status": str,
            "method": str,
            "changes_made": list,
            "dry_run": bool,
            "error_message": str (if failed)
        }
    """
    try:
        data = request.get_json() or {}
        position_id = data.get('position_id')
        dry_run = data.get('dry_run', False)

        if not position_id:
            return jsonify({
                "error": "Missing required field",
                "message": "position_id is required"
            }), 400

        # Load position and executions from database
        db_path = str(config.db_path)
        position = _load_position_from_db(db_path, position_id)
        if not position:
            return jsonify({
                "error": "Position not found",
                "message": f"Position {position_id} not found"
            }), 404

        executions = _load_executions_from_db(db_path, position_id)

        # Attempt repair
        service = get_integrity_service()
        repair_result = service.repair_issue(
            issue_id,
            position,
            executions,
            dry_run
        )

        # Save position changes if not dry run and repair successful
        if not dry_run and repair_result.is_successful():
            _save_position_to_db(db_path, position)

        return jsonify(repair_result.to_dict()), 200

    except Exception as e:
        logger.error(f"Error repairing issue {issue_id}: {e}")
        return jsonify({
            "error": "Failed to repair issue",
            "message": str(e)
        }), 500


@validation_bp.route('/positions/<int:position_id>/auto-repair', methods=['POST'])
def auto_repair_position(position_id: int):
    """
    Attempt automatic repair of all repairable issues for a position

    POST /api/validation/positions/{id}/auto-repair

    Request body:
        {
            "dry_run": bool (optional, default false)
        }

    Returns:
        {
            "position_id": int,
            "total_issues": int,
            "repaired": int,
            "failed": int,
            "not_repairable": int,
            "results": {
                "issue_id": {repair_result}
            }
        }
    """
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)

        # Load position and executions from database
        db_path = str(config.db_path)
        position = _load_position_from_db(db_path, position_id)
        if not position:
            return jsonify({
                "error": "Position not found",
                "message": f"Position {position_id} not found"
            }), 404

        executions = _load_executions_from_db(db_path, position_id)

        # Attempt auto-repair
        service = get_integrity_service()
        results = service.attempt_auto_repair(
            position_id,
            position,
            executions,
            dry_run
        )

        # Save position changes if not dry run and any repairs successful
        if not dry_run and any(r.is_successful() for r in results.values()):
            _save_position_to_db(db_path, position)

        # Count results by status
        from domain.services.integrity_repair_service import RepairStatus
        repaired = sum(1 for r in results.values() if r.status == RepairStatus.SUCCESS)
        failed = sum(1 for r in results.values() if r.status == RepairStatus.FAILED)
        not_repairable = sum(1 for r in results.values() if r.status == RepairStatus.NOT_REPAIRABLE)

        return jsonify({
            "position_id": position_id,
            "total_issues": len(results),
            "repaired": repaired,
            "failed": failed,
            "not_repairable": not_repairable,
            "results": {issue_id: result.to_dict() for issue_id, result in results.items()}
        }), 200

    except Exception as e:
        logger.error(f"Error auto-repairing position {position_id}: {e}")
        return jsonify({
            "error": "Failed to auto-repair position",
            "message": str(e)
        }), 500


@validation_bp.route('/issues/repairable', methods=['GET'])
def get_repairable_issues():
    """
    Get issues that can be automatically repaired

    GET /api/validation/issues/repairable?position_id={id}&limit={limit}

    Query parameters:
        - position_id (optional): Filter by position ID
        - limit (optional): Maximum results (default 100)

    Returns:
        {
            "total": int,
            "issues": [IntegrityIssue]
        }
    """
    try:
        position_id = request.args.get('position_id', type=int)
        limit = request.args.get('limit', type=int, default=100)

        service = get_integrity_service()
        issues = service.get_repairable_issues(
            position_id=position_id,
            limit=limit
        )

        return jsonify({
            "total": len(issues),
            "issues": [issue.to_dict() for issue in issues]
        }), 200

    except Exception as e:
        logger.error(f"Error getting repairable issues: {e}")
        return jsonify({
            "error": "Failed to get repairable issues",
            "message": str(e)
        }), 500


def _save_position_to_db(db_path: str, position):
    """Save position changes back to database"""
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE positions
        SET quantity = ?,
            entry_price = ?,
            exit_price = ?,
            entry_time = ?,
            exit_time = ?,
            instrument = ?
        WHERE id = ?
    """, (
        position.quantity,
        position.entry_price,
        position.exit_price,
        position.entry_time.isoformat() if position.entry_time else None,
        position.exit_time.isoformat() if position.exit_time else None,
        position.instrument,
        position.id
    ))

    conn.commit()
    conn.close()

# ============================================================================
# Job Management Endpoints
# ============================================================================

@validation_bp.route('/jobs/validate', methods=['POST'])
def trigger_validation_job():
    """
    Trigger a background validation job

    POST /api/validation/jobs/validate

    Request body:
        {
            "position_id": int (optional, validate single position),
            "position_status": str (optional, filter by status),
            "days_back": int (optional, only validate recent positions),
            "auto_repair": bool (optional, default false)
        }

    Returns:
        {
            "job_id": str,
            "status": str,
            "message": str
        }
    """
    try:
        from tasks.validation_tasks import validate_position_task, validate_all_positions_task

        data = request.get_json() or {}
        position_id = data.get('position_id')
        auto_repair = data.get('auto_repair', False)

        if position_id:
            # Validate single position
            task = validate_position_task.delay(position_id, auto_repair)
            message = f"Started validation job for position {position_id}"
        else:
            # Validate batch
            position_status = data.get('position_status')
            days_back = data.get('days_back')
            task = validate_all_positions_task.delay(position_status, days_back, auto_repair)
            message = "Started batch validation job"

        return jsonify({
            "job_id": task.id,
            "status": "submitted",
            "message": message
        }), 202

    except Exception as e:
        logger.error(f"Error triggering validation job: {e}")
        return jsonify({
            "error": "Failed to trigger validation job",
            "message": str(e)
        }), 500


@validation_bp.route('/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id: str):
    """
    Get status of a validation job

    GET /api/validation/jobs/{job_id}/status

    Returns:
        {
            "job_id": str,
            "status": str,
            "result": dict (if completed)
        }
    """
    try:
        from celery.result import AsyncResult
        from celery_app import app as celery_app

        task = AsyncResult(job_id, app=celery_app)

        response = {
            "job_id": job_id,
            "status": task.state
        }

        if task.ready():
            if task.successful():
                response["result"] = task.result
            else:
                response["error"] = str(task.info)

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}")
        return jsonify({
            "error": "Failed to get job status",
            "message": str(e)
        }), 500


@validation_bp.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id: str):
    """
    Cancel a running validation job

    POST /api/validation/jobs/{job_id}/cancel

    Returns:
        {
            "job_id": str,
            "status": str,
            "message": str
        }
    """
    try:
        from celery.result import AsyncResult
        from celery_app import app as celery_app

        task = AsyncResult(job_id, app=celery_app)
        task.revoke(terminate=True)

        return jsonify({
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancellation requested"
        }), 200

    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        return jsonify({
            "error": "Failed to cancel job",
            "message": str(e)
        }), 500


@validation_bp.route('/schedule', methods=['GET'])
def get_validation_schedule():
    """
    Get current validation schedule configuration

    GET /api/validation/schedule

    Returns:
        {
            "schedules": [
                {
                    "name": str,
                    "schedule": str,
                    "enabled": bool
                }
            ]
        }
    """
    try:
        from celery_app import app as celery_app

        schedules = []
        for name, task_config in celery_app.conf.beat_schedule.items():
            if 'validation' in name.lower():
                schedules.append({
                    "name": name,
                    "task": task_config['task'],
                    "schedule": str(task_config['schedule']),
                    "enabled": True
                })

        return jsonify({
            "schedules": schedules
        }), 200

    except Exception as e:
        logger.error(f"Error getting validation schedule: {e}")
        return jsonify({
            "error": "Failed to get schedule",
            "message": str(e)
        }), 500
