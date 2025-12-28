"""
Repository for persisting validation results and integrity issues
"""
import sqlite3
import json
from typing import List, Optional, Dict
from datetime import datetime, timezone

from domain.validation_result import ValidationResult, ValidationStatus
from domain.integrity_issue import (
    IntegrityIssue,
    IssueType,
    IssueSeverity,
    ResolutionStatus
)
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ValidationRepository:
    """Repository for validation results and integrity issues"""

    def __init__(self, db_path: str):
        """
        Initialize repository

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def save_validation_result(self, result: ValidationResult) -> int:
        """
        Save a validation result to the database

        Args:
            result: ValidationResult to save

        Returns:
            The validation_id of the saved result
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Serialize details as JSON
                details_json = json.dumps(result.details) if result.details else None

                cursor.execute("""
                    INSERT INTO validation_results (
                        position_id, status, timestamp, issue_count,
                        validation_type, details, completed_at, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.position_id,
                    result.status.value,
                    result.timestamp.isoformat(),
                    result.issue_count,
                    result.validation_type,
                    details_json,
                    result.completed_at.isoformat() if result.completed_at else None,
                    result.error_message
                ))

                validation_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Saved validation result {validation_id} for position {result.position_id}")
                return validation_id

        except sqlite3.Error as e:
            logger.error(f"Error saving validation result: {e}")
            raise

    def save_integrity_issue(self, issue: IntegrityIssue) -> int:
        """
        Save an integrity issue to the database

        Args:
            issue: IntegrityIssue to save

        Returns:
            The issue_id of the saved issue
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Serialize resolution_details and metadata as JSON
                resolution_details_json = json.dumps(issue.resolution_details) if issue.resolution_details else None
                metadata_json = json.dumps(issue.metadata) if issue.metadata else None

                cursor.execute("""
                    INSERT INTO integrity_issues (
                        validation_id, issue_type, severity, description,
                        resolution_status, position_id, execution_id,
                        detected_at, resolved_at, resolution_method,
                        resolution_details, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    issue.validation_id,
                    issue.issue_type.value,
                    issue.severity.value,
                    issue.description,
                    issue.resolution_status.value,
                    issue.position_id,
                    issue.execution_id,
                    issue.detected_at.isoformat(),
                    issue.resolved_at.isoformat() if issue.resolved_at else None,
                    issue.resolution_method,
                    resolution_details_json,
                    metadata_json
                ))

                issue_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Saved integrity issue {issue_id} for validation {issue.validation_id}")
                return issue_id

        except sqlite3.Error as e:
            logger.error(f"Error saving integrity issue: {e}")
            raise

    def save_validation_with_issues(
        self,
        result: ValidationResult,
        issues: List[IntegrityIssue]
    ) -> int:
        """
        Save a validation result and all its associated issues

        Args:
            result: ValidationResult to save
            issues: List of IntegrityIssue objects

        Returns:
            The validation_id of the saved result
        """
        try:
            # Save validation result
            validation_id = self.save_validation_result(result)

            # Create new issues with the validation_id
            for issue in issues:
                # Create a new issue with the correct validation_id
                new_issue = IntegrityIssue(
                    validation_id=validation_id,
                    issue_type=issue.issue_type,
                    severity=issue.severity,
                    description=issue.description,
                    resolution_status=issue.resolution_status,
                    position_id=issue.position_id,
                    execution_id=issue.execution_id,
                    detected_at=issue.detected_at,
                    resolved_at=issue.resolved_at,
                    resolution_method=issue.resolution_method,
                    resolution_details=issue.resolution_details,
                    metadata=issue.metadata
                )
                self.save_integrity_issue(new_issue)

            logger.info(f"Saved validation {validation_id} with {len(issues)} issues")
            return validation_id

        except Exception as e:
            logger.error(f"Error saving validation with issues: {e}")
            raise

    def get_validation_result(self, validation_id: int) -> Optional[ValidationResult]:
        """
        Retrieve a validation result by ID

        Args:
            validation_id: ID of the validation result

        Returns:
            ValidationResult or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT validation_id, position_id, status, timestamp,
                           issue_count, validation_type, details,
                           completed_at, error_message
                    FROM validation_results
                    WHERE validation_id = ?
                """, (validation_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_validation_result(row)

        except sqlite3.Error as e:
            logger.error(f"Error retrieving validation result: {e}")
            return None

    def get_validation_results_for_position(
        self,
        position_id: int,
        limit: int = 10
    ) -> List[ValidationResult]:
        """
        Get validation results for a specific position

        Args:
            position_id: ID of the position
            limit: Maximum number of results to return

        Returns:
            List of ValidationResult objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT validation_id, position_id, status, timestamp,
                           issue_count, validation_type, details,
                           completed_at, error_message
                    FROM validation_results
                    WHERE position_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (position_id, limit))

                return [self._row_to_validation_result(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error retrieving validation results for position: {e}")
            return []

    def get_integrity_issues(
        self,
        validation_id: Optional[int] = None,
        position_id: Optional[int] = None,
        resolution_status: Optional[ResolutionStatus] = None,
        severity: Optional[IssueSeverity] = None,
        limit: int = 100
    ) -> List[IntegrityIssue]:
        """
        Get integrity issues with optional filters

        Args:
            validation_id: Filter by validation ID
            position_id: Filter by position ID
            resolution_status: Filter by resolution status
            severity: Filter by severity level
            limit: Maximum number of results

        Returns:
            List of IntegrityIssue objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT issue_id, validation_id, issue_type, severity,
                           description, resolution_status, position_id,
                           execution_id, detected_at, resolved_at,
                           resolution_method, resolution_details, metadata
                    FROM integrity_issues
                    WHERE 1=1
                """
                params = []

                if validation_id is not None:
                    query += " AND validation_id = ?"
                    params.append(validation_id)

                if position_id is not None:
                    query += " AND position_id = ?"
                    params.append(position_id)

                if resolution_status is not None:
                    query += " AND resolution_status = ?"
                    params.append(resolution_status.value)

                if severity is not None:
                    query += " AND severity = ?"
                    params.append(severity.value)

                query += " ORDER BY detected_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)

                return [self._row_to_integrity_issue(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error retrieving integrity issues: {e}")
            return []

    def update_issue_resolution(
        self,
        issue_id: int,
        resolution_status: ResolutionStatus,
        resolution_method: Optional[str] = None,
        resolution_details: Optional[Dict] = None
    ) -> bool:
        """
        Update the resolution status of an issue

        Args:
            issue_id: ID of the issue to update
            resolution_status: New resolution status
            resolution_method: How the issue was resolved
            resolution_details: Additional resolution details

        Returns:
            True if update successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                resolved_at = datetime.now(timezone.utc).isoformat() if resolution_status in (
                    ResolutionStatus.RESOLVED, ResolutionStatus.IGNORED
                ) else None

                resolution_details_json = json.dumps(resolution_details) if resolution_details else None

                cursor.execute("""
                    UPDATE integrity_issues
                    SET resolution_status = ?,
                        resolved_at = ?,
                        resolution_method = ?,
                        resolution_details = ?
                    WHERE issue_id = ?
                """, (
                    resolution_status.value,
                    resolved_at,
                    resolution_method,
                    resolution_details_json,
                    issue_id
                ))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated issue {issue_id} resolution status to {resolution_status.value}")
                    return True
                else:
                    logger.warning(f"Issue {issue_id} not found for update")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Error updating issue resolution: {e}")
            return False

    def get_validation_statistics(self) -> Dict:
        """
        Get overall validation statistics

        Returns:
            Dictionary with validation statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total validations
                cursor.execute("SELECT COUNT(*) FROM validation_results")
                total_validations = cursor.fetchone()[0]

                # Validations by status
                cursor.execute("""
                    SELECT status, COUNT(*)
                    FROM validation_results
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())

                # Total issues
                cursor.execute("SELECT COUNT(*) FROM integrity_issues")
                total_issues = cursor.fetchone()[0]

                # Issues by severity
                cursor.execute("""
                    SELECT severity, COUNT(*)
                    FROM integrity_issues
                    GROUP BY severity
                """)
                severity_counts = dict(cursor.fetchall())

                # Open issues
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM integrity_issues
                    WHERE resolution_status = 'open'
                """)
                open_issues = cursor.fetchone()[0]

                return {
                    'total_validations': total_validations,
                    'status_counts': status_counts,
                    'total_issues': total_issues,
                    'severity_counts': severity_counts,
                    'open_issues': open_issues
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting validation statistics: {e}")
            return {}

    def get_integrity_issue(self, issue_id: int) -> Optional[IntegrityIssue]:
        """
        Get a single integrity issue by ID

        Args:
            issue_id: ID of the issue to retrieve

        Returns:
            IntegrityIssue object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT issue_id, validation_id, issue_type, severity,
                           description, resolution_status, position_id,
                           execution_id, detected_at, resolved_at,
                           resolution_method, resolution_details, metadata,
                           repair_attempted, repair_method, repair_successful,
                           repair_timestamp, repair_details
                    FROM integrity_issues
                    WHERE issue_id = ?
                """, (issue_id,))

                row = cursor.fetchone()
                if row:
                    return self._row_to_integrity_issue(row)
                return None

        except sqlite3.Error as e:
            logger.error(f"Error retrieving integrity issue {issue_id}: {e}")
            return None

    def update_issue_repair_info(self, issue: IntegrityIssue) -> bool:
        """
        Update repair information for an issue

        Args:
            issue: IntegrityIssue with updated repair information

        Returns:
            True if update successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                resolution_details_json = json.dumps(issue.resolution_details) if issue.resolution_details else None
                repair_details_json = json.dumps(issue.repair_details) if issue.repair_details else None

                cursor.execute("""
                    UPDATE integrity_issues
                    SET repair_attempted = ?,
                        repair_method = ?,
                        repair_successful = ?,
                        repair_timestamp = ?,
                        repair_details = ?,
                        resolution_status = ?,
                        resolved_at = ?,
                        resolution_method = ?,
                        resolution_details = ?
                    WHERE issue_id = ?
                """, (
                    1 if issue.repair_attempted else 0,
                    issue.repair_method,
                    1 if issue.repair_successful else (0 if issue.repair_successful is False else None),
                    issue.repair_timestamp.isoformat() if issue.repair_timestamp else None,
                    repair_details_json,
                    issue.resolution_status.value,
                    issue.resolved_at.isoformat() if issue.resolved_at else None,
                    issue.resolution_method,
                    resolution_details_json,
                    issue.issue_id
                ))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated repair info for issue {issue.issue_id}")
                    return True
                else:
                    logger.warning(f"Issue {issue.issue_id} not found for repair info update")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Error updating issue repair info: {e}")
            return False

    # Private helper methods

    def _row_to_validation_result(self, row: tuple) -> ValidationResult:
        """Convert database row to ValidationResult"""
        details = json.loads(row[6]) if row[6] else {}

        return ValidationResult(
            validation_id=row[0],
            position_id=row[1],
            status=ValidationStatus(row[2]),
            timestamp=datetime.fromisoformat(row[3]),
            issue_count=row[4],
            validation_type=row[5],
            details=details,
            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
            error_message=row[8]
        )

    def _row_to_integrity_issue(self, row: tuple) -> IntegrityIssue:
        """Convert database row to IntegrityIssue"""
        resolution_details = json.loads(row[11]) if row[11] else {}
        metadata = json.loads(row[12]) if row[12] else {}

        # Handle repair fields if present (for backward compatibility)
        repair_attempted = bool(row[13]) if len(row) > 13 else False
        repair_method = row[14] if len(row) > 14 else None
        repair_successful = bool(row[15]) if len(row) > 15 and row[15] is not None else None
        repair_timestamp = datetime.fromisoformat(row[16]) if len(row) > 16 and row[16] else None
        repair_details = json.loads(row[17]) if len(row) > 17 and row[17] else {}

        return IntegrityIssue(
            issue_id=row[0],
            validation_id=row[1],
            issue_type=IssueType(row[2]),
            severity=IssueSeverity(row[3]),
            description=row[4],
            resolution_status=ResolutionStatus(row[5]),
            position_id=row[6],
            execution_id=row[7],
            detected_at=datetime.fromisoformat(row[8]),
            resolved_at=datetime.fromisoformat(row[9]) if row[9] else None,
            resolution_method=row[10],
            resolution_details=resolution_details,
            metadata=metadata,
            repair_attempted=repair_attempted,
            repair_method=repair_method,
            repair_successful=repair_successful,
            repair_timestamp=repair_timestamp,
            repair_details=repair_details
        )