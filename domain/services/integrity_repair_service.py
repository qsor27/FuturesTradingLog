"""
IntegrityRepairService Domain Service

Provides automated repair capabilities for common position-execution integrity issues.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple
from enum import Enum

from domain.integrity_issue import IntegrityIssue, IssueType, ResolutionStatus
from domain.models.position import Position
from domain.models.execution import Execution


class RepairMethod(Enum):
    """Methods used for repairing integrity issues"""
    AUTO_RECALCULATE = "auto_recalculate"
    FIFO_RECONCILIATION = "fifo_reconciliation"
    TIMESTAMP_CORRECTION = "timestamp_correction"
    DATA_COMPLETION = "data_completion"
    MANUAL = "manual"
    SYSTEM_CORRECTION = "system_correction"


class RepairStatus(Enum):
    """Status of repair operation"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_REPAIRABLE = "not_repairable"


@dataclass
class RepairResult:
    """
    Result of a repair operation.

    Attributes:
        issue_id: ID of the issue being repaired
        status: Status of the repair operation
        method: Method used for repair
        changes_made: Description of changes made
        dry_run: Whether this was a dry run
        timestamp: When the repair was attempted
        error_message: Error message if repair failed
        metadata: Additional repair-specific data
    """
    issue_id: int
    status: RepairStatus
    method: RepairMethod
    changes_made: List[str] = field(default_factory=list)
    dry_run: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def is_successful(self) -> bool:
        """Check if repair was successful"""
        return self.status == RepairStatus.SUCCESS

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'issue_id': self.issue_id,
            'status': self.status.value,
            'method': self.method.value,
            'changes_made': self.changes_made,
            'dry_run': self.dry_run,
            'timestamp': self.timestamp.isoformat(),
            'error_message': self.error_message,
            'metadata': self.metadata
        }


class IntegrityRepairService:
    """
    Domain service for repairing position-execution integrity issues.

    Provides automated repair capabilities for common issue types with
    support for dry-run mode and repair audit logging.
    """

    def can_auto_repair(self, issue: IntegrityIssue) -> bool:
        """
        Determine if an issue can be automatically repaired.

        Args:
            issue: The integrity issue to check

        Returns:
            True if the issue can be auto-repaired, False otherwise
        """
        # Don't attempt to repair already resolved/ignored issues
        if issue.resolution_status in (ResolutionStatus.RESOLVED, ResolutionStatus.IGNORED):
            return False

        # Define which issue types are auto-repairable
        auto_repairable_types = {
            IssueType.QUANTITY_MISMATCH,
            IssueType.TIMESTAMP_ANOMALY,
            IssueType.INCOMPLETE_DATA,
        }

        return issue.issue_type in auto_repairable_types

    def repair_quantity_mismatch(
        self,
        issue: IntegrityIssue,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> RepairResult:
        """
        Repair quantity mismatch by recalculating with FIFO logic.

        Args:
            issue: The quantity mismatch issue
            position: The affected position
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            RepairResult indicating success or failure
        """
        result = RepairResult(
            issue_id=issue.issue_id,
            status=RepairStatus.FAILED,
            method=RepairMethod.FIFO_RECONCILIATION,
            dry_run=dry_run
        )

        try:
            # Validate inputs
            if not executions:
                result.error_message = "No executions available for recalculation"
                return result

            # Sort executions by timestamp (FIFO)
            sorted_execs = sorted(executions, key=lambda e: e.execution_time or datetime.min)

            # Calculate quantities using FIFO
            total_quantity = 0
            buy_quantity = 0
            sell_quantity = 0

            for execution in sorted_execs:
                if execution.is_buy_action():
                    buy_quantity += execution.quantity
                    total_quantity += execution.quantity
                else:
                    sell_quantity += execution.quantity
                    total_quantity -= execution.quantity

            # Calculate what the position quantity should be
            expected_quantity = buy_quantity - sell_quantity

            # Check if recalculation matches expectations
            if expected_quantity == position.total_quantity:
                result.status = RepairStatus.SUCCESS
                result.changes_made.append(
                    f"Verified quantity calculation: {expected_quantity} units"
                )
                result.metadata['verified_quantity'] = expected_quantity
            else:
                # Position quantity needs correction
                old_quantity = position.total_quantity

                if not dry_run:
                    position.total_quantity = expected_quantity

                result.status = RepairStatus.SUCCESS
                result.changes_made.append(
                    f"Updated position quantity from {old_quantity} to {expected_quantity}"
                )
                result.metadata['old_quantity'] = old_quantity
                result.metadata['new_quantity'] = expected_quantity

            result.metadata['buy_quantity'] = buy_quantity
            result.metadata['sell_quantity'] = sell_quantity
            result.metadata['execution_count'] = len(executions)

        except Exception as e:
            result.status = RepairStatus.FAILED
            result.error_message = f"Repair failed: {str(e)}"

        return result

    def repair_timestamp_anomaly(
        self,
        issue: IntegrityIssue,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> RepairResult:
        """
        Repair timestamp anomalies by correcting inconsistent timestamps.

        Args:
            issue: The timestamp anomaly issue
            position: The affected position
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            RepairResult indicating success or failure
        """
        result = RepairResult(
            issue_id=issue.issue_id,
            status=RepairStatus.FAILED,
            method=RepairMethod.TIMESTAMP_CORRECTION,
            dry_run=dry_run
        )

        try:
            if not executions:
                result.error_message = "No executions available for timestamp correction"
                return result

            # Sort executions by timestamp
            sorted_execs = sorted(executions, key=lambda e: e.execution_time or datetime.min)

            # Check if position timestamps need adjustment
            first_exec_time = sorted_execs[0].execution_time
            last_exec_time = sorted_execs[-1].execution_time

            changes = []

            # Correct entry time if needed
            if position.entry_time and position.entry_time > first_exec_time:
                old_entry = position.entry_time
                if not dry_run:
                    position.entry_time = first_exec_time
                changes.append(f"Corrected entry_time from {old_entry} to {first_exec_time}")
                result.metadata['old_entry_time'] = old_entry.isoformat()
                result.metadata['new_entry_time'] = first_exec_time.isoformat()

            # Correct exit time if needed (only for closed positions)
            if position.exit_time:
                if position.exit_time < last_exec_time:
                    old_exit = position.exit_time
                    if not dry_run:
                        position.exit_time = last_exec_time
                    changes.append(f"Corrected exit_time from {old_exit} to {last_exec_time}")
                    result.metadata['old_exit_time'] = old_exit.isoformat()
                    result.metadata['new_exit_time'] = last_exec_time.isoformat()

            if changes:
                result.status = RepairStatus.SUCCESS
                result.changes_made = changes
            else:
                result.status = RepairStatus.SUCCESS
                result.changes_made.append("No timestamp corrections needed")

            result.metadata['execution_count'] = len(executions)
            result.metadata['first_execution'] = first_exec_time.isoformat()
            result.metadata['last_execution'] = last_exec_time.isoformat()

        except Exception as e:
            result.status = RepairStatus.FAILED
            result.error_message = f"Repair failed: {str(e)}"

        return result

    def repair_incomplete_data(
        self,
        issue: IntegrityIssue,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> RepairResult:
        """
        Repair incomplete data by filling in missing fields from executions.

        Args:
            issue: The incomplete data issue
            position: The affected position
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            RepairResult indicating success or failure
        """
        result = RepairResult(
            issue_id=issue.issue_id,
            status=RepairStatus.FAILED,
            method=RepairMethod.DATA_COMPLETION,
            dry_run=dry_run
        )

        try:
            if not executions:
                result.error_message = "No executions available for data completion"
                return result

            changes = []

            # Sort executions by timestamp
            sorted_execs = sorted(executions, key=lambda e: e.execution_time or datetime.min)
            first_exec = sorted_execs[0]
            last_exec = sorted_execs[-1]

            # Fill in missing instrument
            if not position.instrument and first_exec.instrument:
                if not dry_run:
                    position.instrument = first_exec.instrument
                changes.append(f"Set instrument to {first_exec.instrument}")
                result.metadata['instrument'] = first_exec.instrument

            # Fill in missing entry price
            if not position.average_entry_price and first_exec.price:
                if not dry_run:
                    position.average_entry_price = first_exec.price
                changes.append(f"Set entry_price to {first_exec.price}")
                result.metadata['entry_price'] = first_exec.price

            # Fill in missing exit price (for closed positions)
            if position.exit_time and not position.average_exit_price and last_exec.price:
                if not dry_run:
                    position.average_exit_price = last_exec.price
                changes.append(f"Set exit_price to {last_exec.price}")
                result.metadata['exit_price'] = last_exec.price

            # Fill in missing entry time
            if not position.entry_time:
                if not dry_run:
                    position.entry_time = first_exec.execution_time
                changes.append(f"Set entry_time to {first_exec.execution_time}")
                result.metadata['entry_time'] = first_exec.execution_time.isoformat() if first_exec.execution_time else None

            if changes:
                result.status = RepairStatus.SUCCESS
                result.changes_made = changes
            else:
                result.status = RepairStatus.SUCCESS
                result.changes_made.append("No data completion needed")

        except Exception as e:
            result.status = RepairStatus.FAILED
            result.error_message = f"Repair failed: {str(e)}"

        return result

    def repair_issue(
        self,
        issue: IntegrityIssue,
        position: Position,
        executions: List[Execution],
        dry_run: bool = False
    ) -> RepairResult:
        """
        Attempt to repair an integrity issue using the appropriate method.

        Args:
            issue: The integrity issue to repair
            position: The affected position
            executions: List of executions for the position
            dry_run: If True, don't actually make changes

        Returns:
            RepairResult indicating success or failure
        """
        # Check if issue can be auto-repaired
        if not self.can_auto_repair(issue):
            return RepairResult(
                issue_id=issue.issue_id,
                status=RepairStatus.NOT_REPAIRABLE,
                method=RepairMethod.MANUAL,
                error_message=f"Issue type {issue.issue_type.value} requires manual repair"
            )

        # Route to appropriate repair method based on issue type
        if issue.issue_type == IssueType.QUANTITY_MISMATCH:
            return self.repair_quantity_mismatch(issue, position, executions, dry_run)
        elif issue.issue_type == IssueType.TIMESTAMP_ANOMALY:
            return self.repair_timestamp_anomaly(issue, position, executions, dry_run)
        elif issue.issue_type == IssueType.INCOMPLETE_DATA:
            return self.repair_incomplete_data(issue, position, executions, dry_run)
        else:
            return RepairResult(
                issue_id=issue.issue_id,
                status=RepairStatus.NOT_REPAIRABLE,
                method=RepairMethod.MANUAL,
                error_message=f"No repair method available for {issue.issue_type.value}"
            )

    def get_repairable_issues(self, issues: List[IntegrityIssue]) -> List[IntegrityIssue]:
        """
        Filter a list of issues to only those that can be auto-repaired.

        Args:
            issues: List of integrity issues

        Returns:
            List of issues that can be auto-repaired
        """
        return [issue for issue in issues if self.can_auto_repair(issue)]