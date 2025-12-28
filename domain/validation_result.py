"""
ValidationResult Domain Model

Represents the result of a position-execution integrity validation check.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class ValidationStatus(Enum):
    """Status of a validation check"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class ValidationResult:
    """
    Domain model for position-execution integrity validation results.

    Attributes:
        validation_id: Unique identifier for this validation
        position_id: ID of the position being validated
        status: Current status of the validation
        timestamp: When the validation was performed
        issue_count: Number of integrity issues found
        validation_type: Type of validation performed (e.g., 'completeness', 'consistency')
        details: Additional validation details and metadata
        completed_at: When the validation completed (if finished)
        error_message: Error message if validation failed with error
    """
    position_id: int
    status: ValidationStatus
    timestamp: datetime
    issue_count: int = 0
    validation_id: Optional[int] = None
    validation_type: str = "full"
    details: dict = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        """Validate the validation result data"""
        if self.position_id <= 0:
            raise ValueError("position_id must be positive")

        if self.issue_count < 0:
            raise ValueError("issue_count cannot be negative")

        if isinstance(self.status, str):
            self.status = ValidationStatus(self.status)

        if not isinstance(self.status, ValidationStatus):
            raise ValueError(f"status must be ValidationStatus enum, got {type(self.status)}")

        if self.completed_at and self.completed_at < self.timestamp:
            raise ValueError("completed_at cannot be before timestamp")

    def mark_passed(self) -> None:
        """Mark validation as passed"""
        self.status = ValidationStatus.PASSED
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, issue_count: int) -> None:
        """Mark validation as failed with issue count"""
        if issue_count <= 0:
            raise ValueError("issue_count must be positive when marking failed")
        self.status = ValidationStatus.FAILED
        self.issue_count = issue_count
        self.completed_at = datetime.now(timezone.utc)

    def mark_error(self, error_message: str) -> None:
        """Mark validation as errored"""
        if not error_message:
            raise ValueError("error_message required when marking error")
        self.status = ValidationStatus.ERROR
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)

    def is_completed(self) -> bool:
        """Check if validation is completed"""
        return self.status in (ValidationStatus.PASSED, ValidationStatus.FAILED, ValidationStatus.ERROR)

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            'validation_id': self.validation_id,
            'position_id': self.position_id,
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'issue_count': self.issue_count,
            'validation_type': self.validation_type,
            'details': self.details,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ValidationResult':
        """Create ValidationResult from dictionary"""
        return cls(
            validation_id=data.get('validation_id'),
            position_id=data['position_id'],
            status=ValidationStatus(data['status']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            issue_count=data.get('issue_count', 0),
            validation_type=data.get('validation_type', 'full'),
            details=data.get('details', {}),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            error_message=data.get('error_message')
        )