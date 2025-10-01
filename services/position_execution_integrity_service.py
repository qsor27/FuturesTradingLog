"""
Position-Execution Integrity Service

Application service layer for orchestrating position-execution validation workflows,
managing validation results, and coordinating automated repairs.
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from domain.models.position import Position
from domain.models.execution import Execution
from domain.services.position_execution_integrity_validator import PositionExecutionIntegrityValidator
from domain.services.integrity_repair_service import IntegrityRepairService, RepairResult, RepairStatus
from domain.validation_result import ValidationResult, ValidationStatus
from domain.integrity_issue import IntegrityIssue, IssueSeverity, ResolutionStatus
from repositories.validation_repository import ValidationRepository
from utils.logging_config import get_logger

logger = get_logger(__name__)


class PositionExecutionIntegrityService:
    """
    Application service for position-execution integrity validation.

    Orchestrates validation workflows, manages results persistence,
    and coordinates repair operations.
    """

    def __init__(
        self,
        validator: PositionExecutionIntegrityValidator,
        validation_repository: ValidationRepository,
        repair_service: Optional[IntegrityRepairService] = None
    ):
        """
        Initialize the integrity service

        Args:
            validator: Domain validator for position-execution integrity
            validation_repository: Repository for persisting validation results
            repair_service: Optional service for automated repairs
        """
        self.validator = validator
        self.validation_repository = validation_repository
        self.repair_service = repair_service or IntegrityRepairService()

    def validate_position(
        self,
        position: Position,
        executions: List[Execution],
        save_results: bool = True
    ) -> Tuple[ValidationResult, List[IntegrityIssue]]:
        """
        Validate a single position against its executions

        Args:
            position: Position to validate
            executions: List of executions for this position
            save_results: Whether to save validation results to database

        Returns:
            Tuple of (ValidationResult, List of IntegrityIssue)
        """
        logger.info(f"Validating position {position.id} with {len(executions)} executions")

        try:
            # Run validation (without validation_id initially)
            result = self.validator.validate_position(position, executions, validation_id=None)
            issues = self.validator.get_issues()

            # Save results if requested
            if save_results and position.id:
                validation_id = self.validation_repository.save_validation_with_issues(
                    result, issues
                )
                result.validation_id = validation_id
                logger.info(f"Saved validation {validation_id} for position {position.id}")

            # Update position with validation status
            if position.id:
                self._update_position_validation_status(position, result, issues)

            return result, issues

        except Exception as e:
            logger.error(f"Error validating position {position.id}: {e}")
            # Create error result
            error_result = ValidationResult(
                position_id=position.id or 0,
                status=ValidationStatus.ERROR,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )
            error_result.mark_error(str(e))

            if save_results and position.id:
                self.validation_repository.save_validation_result(error_result)

            return error_result, []

    def validate_positions_batch(
        self,
        positions: List[Position],
        executions_by_position: Dict[int, List[Execution]],
        save_results: bool = True
    ) -> Dict[int, Tuple[ValidationResult, List[IntegrityIssue]]]:
        """
        Validate multiple positions in batch

        Args:
            positions: List of positions to validate
            executions_by_position: Map of position_id to executions list
            save_results: Whether to save validation results

        Returns:
            Dictionary mapping position_id to (ValidationResult, issues)
        """
        logger.info(f"Batch validating {len(positions)} positions")

        results = {}
        for position in positions:
            position_id = position.id or 0
            executions = executions_by_position.get(position_id, [])

            result, issues = self.validate_position(
                position,
                executions,
                save_results=save_results
            )
            results[position_id] = (result, issues)

        logger.info(f"Batch validation completed: {len(results)} positions processed")
        return results

    def get_validation_results_for_position(
        self,
        position_id: int,
        limit: int = 10
    ) -> List[ValidationResult]:
        """
        Get validation history for a position

        Args:
            position_id: ID of the position
            limit: Maximum number of results to return

        Returns:
            List of ValidationResult objects
        """
        return self.validation_repository.get_validation_results_for_position(
            position_id, limit
        )

    def get_open_issues(
        self,
        position_id: Optional[int] = None,
        severity: Optional[IssueSeverity] = None,
        limit: int = 100
    ) -> List[IntegrityIssue]:
        """
        Get open (unresolved) integrity issues

        Args:
            position_id: Optional filter by position ID
            severity: Optional filter by severity
            limit: Maximum number of results

        Returns:
            List of open IntegrityIssue objects
        """
        return self.validation_repository.get_integrity_issues(
            position_id=position_id,
            resolution_status=ResolutionStatus.OPEN,
            severity=severity,
            limit=limit
        )

    def get_critical_issues(self, limit: int = 50) -> List[IntegrityIssue]:
        """
        Get critical severity issues that need immediate attention

        Args:
            limit: Maximum number of results

        Returns:
            List of critical IntegrityIssue objects
        """
        return self.validation_repository.get_integrity_issues(
            resolution_status=ResolutionStatus.OPEN,
            severity=IssueSeverity.CRITICAL,
            limit=limit
        )

    def resolve_issue(
        self,
        issue_id: int,
        resolution_method: str,
        resolution_details: Optional[Dict] = None
    ) -> bool:
        """
        Mark an issue as resolved

        Args:
            issue_id: ID of the issue to resolve
            resolution_method: How the issue was resolved
            resolution_details: Additional resolution details

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Resolving issue {issue_id} via {resolution_method}")

        success = self.validation_repository.update_issue_resolution(
            issue_id,
            ResolutionStatus.RESOLVED,
            resolution_method,
            resolution_details
        )

        if success:
            logger.info(f"Issue {issue_id} resolved successfully")
        else:
            logger.warning(f"Failed to resolve issue {issue_id}")

        return success

    def ignore_issue(self, issue_id: int, reason: str) -> bool:
        """
        Mark an issue as ignored

        Args:
            issue_id: ID of the issue to ignore
            reason: Reason for ignoring

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Ignoring issue {issue_id}: {reason}")

        return self.validation_repository.update_issue_resolution(
            issue_id,
            ResolutionStatus.IGNORED,
            "manual_ignore",
            {"reason": reason}
        )

    def get_validation_statistics(self) -> Dict:
        """
        Get overall validation statistics

        Returns:
            Dictionary with validation statistics
        """
        stats = self.validation_repository.get_validation_statistics()

        # Add derived metrics
        if stats.get('total_validations', 0) > 0:
            passed = stats.get('status_counts', {}).get('passed', 0)
            stats['pass_rate'] = (passed / stats['total_validations']) * 100

        if stats.get('total_issues', 0) > 0:
            open_issues = stats.get('open_issues', 0)
            stats['resolution_rate'] = ((stats['total_issues'] - open_issues) / stats['total_issues']) * 100

        return stats

    def get_position_integrity_score(self, position_id: int) -> float:
        """
        Calculate integrity score for a position based on validation history

        Args:
            position_id: ID of the position

        Returns:
            Integrity score from 0.0 to 100.0
        """
        # Get most recent validation
        results = self.validation_repository.get_validation_results_for_position(
            position_id, limit=1
        )

        if not results:
            return 0.0  # No validation performed

        result = results[0]

        if result.status == ValidationStatus.PASSED:
            return 100.0

        if result.status == ValidationStatus.ERROR:
            return 0.0

        # Calculate score based on issues
        if result.issue_count == 0:
            return 100.0

        # Get issues for this validation
        issues = self.validation_repository.get_integrity_issues(
            validation_id=result.validation_id
        )

        if not issues:
            return 50.0  # Issues reported but not found

        # Weight by severity
        severity_weights = {
            IssueSeverity.CRITICAL: 25.0,
            IssueSeverity.HIGH: 15.0,
            IssueSeverity.MEDIUM: 7.0,
            IssueSeverity.LOW: 3.0,
            IssueSeverity.INFO: 1.0
        }

        total_penalty = sum(
            severity_weights.get(issue.severity, 5.0)
            for issue in issues
        )

        # Cap penalty at 100
        score = max(0.0, 100.0 - total_penalty)

        return score

    def detect_orphaned_executions(
        self,
        all_executions: List[Execution],
        all_positions: List[Position],
        save_results: bool = True
    ) -> List[IntegrityIssue]:
        """
        Detect executions not linked to any position

        Args:
            all_executions: All executions in the system
            all_positions: All positions in the system
            save_results: Whether to save results

        Returns:
            List of IntegrityIssue objects for orphaned executions
        """
        logger.info(f"Checking {len(all_executions)} executions for orphans")

        issues = self.validator.detect_orphaned_executions(
            all_executions,
            all_positions,
            validation_id=None
        )

        logger.info(f"Found {len(issues)} orphaned executions")

        # Save as a system-level validation if requested
        if save_results and issues:
            # Use position_id=1 instead of 0 to avoid validation error
            system_result = ValidationResult(
                position_id=1,  # Placeholder for system-level validation
                status=ValidationStatus.FAILED,
                timestamp=datetime.utcnow(),
                issue_count=len(issues),
                validation_type="orphan_detection"
            )
            system_result.mark_failed(len(issues))

            try:
                validation_id = self.validation_repository.save_validation_with_issues(
                    system_result, issues
                )
                logger.info(f"Saved orphan detection validation {validation_id}")
            except Exception as e:
                logger.error(f"Error saving orphan detection results: {e}")

        return issues

    def detect_positions_without_executions(
        self,
        all_positions: List[Position],
        executions_by_position: Dict[int, List[Execution]],
        save_results: bool = True
    ) -> List[IntegrityIssue]:
        """
        Detect positions that have no executions

        Args:
            all_positions: All positions in the system
            executions_by_position: Map of position_id to executions
            save_results: Whether to save results

        Returns:
            List of IntegrityIssue objects
        """
        logger.info(f"Checking {len(all_positions)} positions for missing executions")

        issues = self.validator.detect_positions_without_executions(
            all_positions,
            executions_by_position,
            validation_id=None
        )

        logger.info(f"Found {len(issues)} positions without executions")

        # Save as a system-level validation if requested
        if save_results and issues:
            # Use position_id=1 instead of 0 to avoid validation error
            system_result = ValidationResult(
                position_id=1,  # Placeholder for system-level validation
                status=ValidationStatus.FAILED,
                timestamp=datetime.utcnow(),
                issue_count=len(issues),
                validation_type="missing_executions_detection"
            )
            system_result.mark_failed(len(issues))

            try:
                validation_id = self.validation_repository.save_validation_with_issues(
                    system_result, issues
                )
                logger.info(f"Saved missing executions validation {validation_id}")
            except Exception as e:
                logger.error(f"Error saving missing executions results: {e}")

        return issues

    def repair_issue(
        self,
        issue_id: int,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> RepairResult:
        """
        Attempt to repair a specific integrity issue

        Args:
            issue_id: ID of the issue to repair
            position: The affected position
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            RepairResult indicating success or failure
        """
        logger.info(f"Attempting repair for issue {issue_id}, dry_run={dry_run}")

        # Get the issue
        issue = self.validation_repository.get_integrity_issue(issue_id)
        if not issue:
            return RepairResult(
                issue_id=issue_id,
                status=RepairStatus.FAILED,
                method=None,
                error_message="Issue not found"
            )

        # Check if issue is already resolved
        if issue.is_resolved():
            return RepairResult(
                issue_id=issue_id,
                status=RepairStatus.NOT_REPAIRABLE,
                method=None,
                error_message="Issue is already resolved"
            )

        # Attempt repair using repair service
        repair_result = self.repair_service.repair_issue(
            issue,
            position,
            executions,
            dry_run
        )

        # Update issue with repair information if not dry run
        if not dry_run:
            issue.repair_attempted = True
            issue.repair_method = repair_result.method.value
            issue.repair_successful = repair_result.is_successful()
            issue.repair_timestamp = datetime.utcnow()
            issue.repair_details = repair_result.metadata

            # If repair was successful, mark issue as resolved
            if repair_result.is_successful():
                issue.mark_resolved(
                    method=f"auto_repair_{repair_result.method.value}",
                    details=repair_result.metadata
                )
            else:
                issue.mark_failed(repair_result.error_message or "Repair failed")

            # Save updated issue
            self.validation_repository.update_issue_repair_info(issue)

        logger.info(
            f"Repair result for issue {issue_id}: "
            f"{repair_result.status.value}, changes: {len(repair_result.changes_made)}"
        )

        return repair_result

    def attempt_auto_repair(
        self,
        position_id: int,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> Dict[int, RepairResult]:
        """
        Attempt automatic repair of all repairable issues for a position

        Args:
            position_id: ID of the position
            position: The position object
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            Dictionary mapping issue_id to RepairResult
        """
        logger.info(f"Attempting auto-repair for position {position_id}, dry_run={dry_run}")

        # Get open issues for this position
        issues = self.get_open_issues(position_id=position_id)

        # Filter to repairable issues
        repairable_issues = self.repair_service.get_repairable_issues(issues)

        logger.info(f"Found {len(repairable_issues)} repairable issues for position {position_id}")

        results = {}
        for issue in repairable_issues:
            repair_result = self.repair_issue(
                issue.issue_id,
                position,
                executions,
                dry_run
            )
            results[issue.issue_id] = repair_result

        success_count = sum(1 for r in results.values() if r.is_successful())
        logger.info(
            f"Auto-repair completed for position {position_id}: "
            f"{success_count}/{len(results)} successful"
        )

        return results

    def get_repairable_issues(
        self,
        position_id: Optional[int] = None,
        limit: int = 100
    ) -> List[IntegrityIssue]:
        """
        Get issues that can be automatically repaired

        Args:
            position_id: Optional filter by position ID
            limit: Maximum number of results

        Returns:
            List of repairable IntegrityIssue objects
        """
        # Get all open issues
        open_issues = self.get_open_issues(position_id=position_id, limit=limit)

        # Filter to repairable ones
        return self.repair_service.get_repairable_issues(open_issues)

    # Private helper methods

    def _update_position_validation_status(
        self,
        position: Position,
        result: ValidationResult,
        issues: List[IntegrityIssue]
    ) -> None:
        """Update position model with validation status"""
        position.last_validated_at = datetime.utcnow()
        position.validation_status = result.status.value
        position.integrity_score = self.get_position_integrity_score(position.id or 0)

        logger.debug(
            f"Updated position {position.id} validation status: "
            f"{position.validation_status}, score: {position.integrity_score}"
        )