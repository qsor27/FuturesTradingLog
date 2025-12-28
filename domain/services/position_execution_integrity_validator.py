"""
Position-Execution Integrity Validator Domain Service

Validates the integrity between positions and their constituent executions,
detecting missing data, orphans, and consistency issues.
"""
from typing import List, Optional, Set, Dict
from datetime import datetime, timedelta, timezone
from domain.models.position import Position
from domain.models.execution import Execution
from domain.validation_result import ValidationResult, ValidationStatus
from domain.integrity_issue import (
    IntegrityIssue,
    IssueType,
    IssueSeverity,
    ResolutionStatus
)


class PositionExecutionIntegrityValidator:
    """
    Domain service for validating position-execution integrity.

    Performs comprehensive validation including:
    - Completeness checks (missing executions, incomplete data)
    - Orphan detection (unlinked executions and positions)
    - Data consistency (price/quantity mismatches, timestamp anomalies)
    """

    def __init__(self):
        """Initialize the validator"""
        self.issues: List[IntegrityIssue] = []
        self.validation_id: Optional[int] = None

    def validate_position(
        self,
        position: Position,
        executions: List[Execution],
        validation_id: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate a single position against its executions.

        Args:
            position: The position to validate
            executions: List of executions that should comprise this position
            validation_id: Optional validation ID for tracking

        Returns:
            ValidationResult with all detected issues
        """
        self.issues = []
        self.validation_id = validation_id or 0

        timestamp = datetime.now(timezone.utc)

        # Run all validation checks
        self._check_completeness(position, executions)
        self._check_data_consistency(position, executions)
        self._check_timestamp_consistency(position, executions)

        # Create validation result
        if len(self.issues) == 0:
            result = ValidationResult(
                validation_id=validation_id,
                position_id=position.id or 0,
                status=ValidationStatus.PASSED,
                timestamp=timestamp,
                issue_count=0
            )
            result.mark_passed()
        else:
            result = ValidationResult(
                validation_id=validation_id,
                position_id=position.id or 0,
                status=ValidationStatus.FAILED,
                timestamp=timestamp,
                issue_count=len(self.issues)
            )
            result.mark_failed(len(self.issues))

        return result

    def validate_positions_batch(
        self,
        positions: List[Position],
        executions_by_position: Dict[int, List[Execution]],
        validation_id: Optional[int] = None
    ) -> List[ValidationResult]:
        """
        Validate multiple positions in batch.

        Args:
            positions: List of positions to validate
            executions_by_position: Dictionary mapping position IDs to their executions
            validation_id: Optional validation ID for tracking

        Returns:
            List of ValidationResult objects, one per position
        """
        results = []
        for position in positions:
            position_id = position.id or 0
            executions = executions_by_position.get(position_id, [])
            result = self.validate_position(position, executions, validation_id)
            results.append(result)

        return results

    def detect_orphaned_executions(
        self,
        all_executions: List[Execution],
        all_positions: List[Position],
        validation_id: Optional[int] = None
    ) -> List[IntegrityIssue]:
        """
        Detect executions that are not linked to any position.

        Args:
            all_executions: All executions in the system
            all_positions: All positions in the system
            validation_id: Optional validation ID for tracking

        Returns:
            List of IntegrityIssue objects for orphaned executions
        """
        self.issues = []
        self.validation_id = validation_id or 0

        # Get all position IDs
        position_ids = {p.id for p in all_positions if p.id is not None}

        # Find executions without a valid position link
        for execution in all_executions:
            # Check if execution has trade_id linking to a position
            # For now, we'll check if execution is processed but not linked
            if execution.processed and execution.trade_id is None:
                self._add_issue(
                    issue_type=IssueType.ORPHANED_EXECUTION,
                    severity=IssueSeverity.HIGH,
                    description=f"Execution {execution.execution_id} marked as processed but not linked to any trade/position",
                    execution_id=execution.id
                )

        return self.issues

    def detect_positions_without_executions(
        self,
        all_positions: List[Position],
        executions_by_position: Dict[int, List[Execution]],
        validation_id: Optional[int] = None
    ) -> List[IntegrityIssue]:
        """
        Detect positions that have no associated executions.

        Args:
            all_positions: All positions in the system
            executions_by_position: Dictionary mapping position IDs to their executions
            validation_id: Optional validation ID for tracking

        Returns:
            List of IntegrityIssue objects for positions without executions
        """
        self.issues = []
        self.validation_id = validation_id or 0

        for position in all_positions:
            position_id = position.id or 0
            executions = executions_by_position.get(position_id, [])

            if len(executions) == 0:
                self._add_issue(
                    issue_type=IssueType.POSITION_WITHOUT_EXECUTIONS,
                    severity=IssueSeverity.CRITICAL,
                    description=f"Position {position_id} ({position.instrument}) has no associated executions",
                    position_id=position_id
                )

        return self.issues

    def get_issues(self) -> List[IntegrityIssue]:
        """Get all issues detected in the last validation"""
        return self.issues

    # Private validation methods

    def _check_completeness(self, position: Position, executions: List[Execution]) -> None:
        """Check for missing or incomplete execution data"""
        position_id = position.id or 0

        # Check if position has no executions
        if len(executions) == 0:
            self._add_issue(
                issue_type=IssueType.MISSING_EXECUTION,
                severity=IssueSeverity.CRITICAL,
                description=f"Position {position_id} has no executions",
                position_id=position_id
            )
            return

        # Check if execution count matches
        if position.execution_count > 0 and position.execution_count != len(executions):
            self._add_issue(
                issue_type=IssueType.INCOMPLETE_DATA,
                severity=IssueSeverity.HIGH,
                description=f"Position {position_id} reports {position.execution_count} executions but {len(executions)} found",
                position_id=position_id,
                metadata={'expected': position.execution_count, 'actual': len(executions)}
            )

        # Check for incomplete execution data
        for execution in executions:
            missing_fields = []

            if not execution.execution_time:
                missing_fields.append('execution_time')
            if not execution.price or execution.price <= 0:
                missing_fields.append('price')
            if not execution.quantity or execution.quantity <= 0:
                missing_fields.append('quantity')
            if not execution.instrument:
                missing_fields.append('instrument')

            if missing_fields:
                self._add_issue(
                    issue_type=IssueType.INCOMPLETE_DATA,
                    severity=IssueSeverity.HIGH,
                    description=f"Execution {execution.execution_id} has missing fields: {', '.join(missing_fields)}",
                    position_id=position_id,
                    execution_id=execution.id,
                    metadata={'missing_fields': missing_fields}
                )

    def _check_data_consistency(self, position: Position, executions: List[Execution]) -> None:
        """Check for price and quantity mismatches"""
        if len(executions) == 0:
            return

        position_id = position.id or 0

        # Calculate expected values from executions
        total_buy_qty = 0
        total_sell_qty = 0
        total_buy_value = 0.0
        total_sell_value = 0.0

        for execution in executions:
            if execution.is_buy_action():
                total_buy_qty += execution.quantity
                total_buy_value += execution.quantity * execution.price
            elif execution.is_sell_action():
                total_sell_qty += execution.quantity
                total_sell_value += execution.quantity * execution.price

        # Check quantity consistency
        expected_qty = abs(total_buy_qty - total_sell_qty)
        if position.total_quantity > 0 and expected_qty != position.total_quantity:
            self._add_issue(
                issue_type=IssueType.QUANTITY_MISMATCH,
                severity=IssueSeverity.HIGH,
                description=f"Position {position_id} quantity mismatch: expected {expected_qty}, got {position.total_quantity}",
                position_id=position_id,
                metadata={
                    'expected_quantity': expected_qty,
                    'actual_quantity': position.total_quantity,
                    'buy_qty': total_buy_qty,
                    'sell_qty': total_sell_qty
                }
            )

        # Check average entry price consistency (for closed positions)
        if total_buy_qty > 0 and position.is_closed():
            expected_avg_entry = total_buy_value / total_buy_qty
            price_diff = abs(expected_avg_entry - position.average_entry_price)

            # Allow small floating point differences (0.01)
            if price_diff > 0.01:
                self._add_issue(
                    issue_type=IssueType.PRICE_MISMATCH,
                    severity=IssueSeverity.MEDIUM,
                    description=f"Position {position_id} average entry price mismatch: expected {expected_avg_entry:.2f}, got {position.average_entry_price:.2f}",
                    position_id=position_id,
                    metadata={
                        'expected_price': expected_avg_entry,
                        'actual_price': position.average_entry_price,
                        'difference': price_diff
                    }
                )

        # Check for duplicate executions
        execution_ids = [e.execution_id for e in executions]
        if len(execution_ids) != len(set(execution_ids)):
            duplicates = [eid for eid in execution_ids if execution_ids.count(eid) > 1]
            self._add_issue(
                issue_type=IssueType.DUPLICATE_EXECUTION,
                severity=IssueSeverity.HIGH,
                description=f"Position {position_id} has duplicate executions: {', '.join(set(duplicates))}",
                position_id=position_id,
                metadata={'duplicate_ids': list(set(duplicates))}
            )

    def _check_timestamp_consistency(self, position: Position, executions: List[Execution]) -> None:
        """Check for timestamp anomalies"""
        if len(executions) == 0:
            return

        position_id = position.id or 0

        # Sort executions by time
        sorted_executions = sorted(
            [e for e in executions if e.execution_time],
            key=lambda e: e.execution_time
        )

        if len(sorted_executions) == 0:
            return

        first_execution_time = sorted_executions[0].execution_time
        last_execution_time = sorted_executions[-1].execution_time

        # Check if position entry time matches first execution
        if position.entry_time and first_execution_time:
            time_diff = abs((position.entry_time - first_execution_time).total_seconds())

            # Allow 1 second difference for timing precision
            if time_diff > 1:
                self._add_issue(
                    issue_type=IssueType.TIMESTAMP_ANOMALY,
                    severity=IssueSeverity.LOW,
                    description=f"Position {position_id} entry time ({position.entry_time}) differs from first execution time ({first_execution_time})",
                    position_id=position_id,
                    metadata={
                        'position_entry_time': position.entry_time.isoformat(),
                        'first_execution_time': first_execution_time.isoformat(),
                        'difference_seconds': time_diff
                    }
                )

        # Check if position exit time matches last execution (for closed positions)
        if position.is_closed() and position.exit_time and last_execution_time:
            time_diff = abs((position.exit_time - last_execution_time).total_seconds())

            # Allow 1 second difference
            if time_diff > 1:
                self._add_issue(
                    issue_type=IssueType.TIMESTAMP_ANOMALY,
                    severity=IssueSeverity.LOW,
                    description=f"Position {position_id} exit time ({position.exit_time}) differs from last execution time ({last_execution_time})",
                    position_id=position_id,
                    metadata={
                        'position_exit_time': position.exit_time.isoformat(),
                        'last_execution_time': last_execution_time.isoformat(),
                        'difference_seconds': time_diff
                    }
                )

        # Check for executions with timestamps out of reasonable range
        for execution in sorted_executions:
            if not execution.execution_time:
                continue

            # Check if execution is too far in the future
            if execution.execution_time > datetime.now(timezone.utc) + timedelta(hours=1):
                self._add_issue(
                    issue_type=IssueType.TIMESTAMP_ANOMALY,
                    severity=IssueSeverity.MEDIUM,
                    description=f"Execution {execution.execution_id} has timestamp in the future: {execution.execution_time}",
                    position_id=position_id,
                    execution_id=execution.id,
                    metadata={'execution_time': execution.execution_time.isoformat()}
                )

    def _add_issue(
        self,
        issue_type: IssueType,
        severity: IssueSeverity,
        description: str,
        position_id: Optional[int] = None,
        execution_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add an integrity issue to the issues list"""
        issue = IntegrityIssue(
            validation_id=self.validation_id if self.validation_id and self.validation_id > 0 else 999,  # Placeholder, will be replaced when saving
            issue_type=issue_type,
            severity=severity,
            description=description,
            position_id=position_id,
            execution_id=execution_id,
            metadata=metadata or {}
        )
        self.issues.append(issue)