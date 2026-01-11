"""
IntegrityIssue Domain Model

Represents a specific integrity issue found during position-execution validation.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class IssueType(Enum):
    """Types of integrity issues"""
    MISSING_EXECUTION = "missing_execution"
    ORPHANED_EXECUTION = "orphaned_execution"
    PRICE_MISMATCH = "price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    TIMESTAMP_ANOMALY = "timestamp_anomaly"
    INCOMPLETE_DATA = "incomplete_data"
    DUPLICATE_EXECUTION = "duplicate_execution"
    POSITION_WITHOUT_EXECUTIONS = "position_without_executions"
    POSITION_NOT_FLAT = "position_not_flat"  # Running quantity != 0 at end of day
    ORPHAN_SOURCE_FILE = "orphan_source_file"  # Trade's source CSV file is missing
    OTHER = "other"


class IssueSeverity(Enum):
    """Severity levels for integrity issues"""
    CRITICAL = "critical"  # Data is corrupt or unusable
    HIGH = "high"          # Significant data accuracy concerns
    MEDIUM = "medium"      # Moderate data quality issues
    LOW = "low"            # Minor inconsistencies
    INFO = "info"          # Informational only


class ResolutionStatus(Enum):
    """Status of issue resolution"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    FAILED = "failed"


@dataclass
class IntegrityIssue:
    """
    Domain model for position-execution integrity issues.

    Attributes:
        validation_id: ID of the validation that found this issue
        issue_type: Type of integrity issue
        severity: Severity level of the issue
        description: Human-readable description of the issue
        resolution_status: Current resolution status
        issue_id: Unique identifier for this issue
        position_id: ID of affected position (if applicable)
        execution_id: ID of affected execution (if applicable)
        detected_at: When the issue was detected
        resolved_at: When the issue was resolved (if resolved)
        resolution_method: How the issue was resolved
        resolution_details: Additional details about the resolution
        metadata: Additional issue-specific metadata
        repair_attempted: Whether automatic repair was attempted
        repair_method: Method used for repair attempt
        repair_successful: Whether repair was successful
        repair_timestamp: When repair was attempted
        repair_details: Details about the repair operation
    """
    validation_id: int
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    resolution_status: ResolutionStatus = ResolutionStatus.OPEN
    issue_id: Optional[int] = None
    position_id: Optional[int] = None
    execution_id: Optional[int] = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None
    resolution_details: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    repair_attempted: bool = False
    repair_method: Optional[str] = None
    repair_successful: Optional[bool] = None
    repair_timestamp: Optional[datetime] = None
    repair_details: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate the integrity issue data"""
        if self.validation_id <= 0:
            raise ValueError("validation_id must be positive")

        if not self.description or not self.description.strip():
            raise ValueError("description is required")

        if isinstance(self.issue_type, str):
            self.issue_type = IssueType(self.issue_type)

        if isinstance(self.severity, str):
            self.severity = IssueSeverity(self.severity)

        if isinstance(self.resolution_status, str):
            self.resolution_status = ResolutionStatus(self.resolution_status)

        if not isinstance(self.issue_type, IssueType):
            raise ValueError(f"issue_type must be IssueType enum, got {type(self.issue_type)}")

        if not isinstance(self.severity, IssueSeverity):
            raise ValueError(f"severity must be IssueSeverity enum, got {type(self.severity)}")

        if not isinstance(self.resolution_status, ResolutionStatus):
            raise ValueError(f"resolution_status must be ResolutionStatus enum, got {type(self.resolution_status)}")

        if self.resolved_at and self.resolved_at < self.detected_at:
            raise ValueError("resolved_at cannot be before detected_at")

    def mark_in_progress(self) -> None:
        """Mark issue resolution as in progress"""
        self.resolution_status = ResolutionStatus.IN_PROGRESS

    def mark_resolved(self, method: str, details: Optional[dict] = None) -> None:
        """Mark issue as resolved"""
        if not method or not method.strip():
            raise ValueError("resolution method is required")

        self.resolution_status = ResolutionStatus.RESOLVED
        self.resolution_method = method
        self.resolved_at = datetime.now(timezone.utc)

        if details:
            self.resolution_details.update(details)

    def mark_ignored(self, reason: str) -> None:
        """Mark issue as ignored"""
        if not reason or not reason.strip():
            raise ValueError("reason is required when ignoring an issue")

        self.resolution_status = ResolutionStatus.IGNORED
        self.resolved_at = datetime.now(timezone.utc)
        self.resolution_details['ignore_reason'] = reason

    def mark_failed(self, error: str) -> None:
        """Mark resolution attempt as failed"""
        if not error or not error.strip():
            raise ValueError("error message is required when marking failed")

        self.resolution_status = ResolutionStatus.FAILED
        self.resolution_details['error'] = error

    def is_resolved(self) -> bool:
        """Check if issue is resolved"""
        return self.resolution_status in (ResolutionStatus.RESOLVED, ResolutionStatus.IGNORED)

    def is_critical(self) -> bool:
        """Check if issue is critical severity"""
        return self.severity == IssueSeverity.CRITICAL

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            'issue_id': self.issue_id,
            'validation_id': self.validation_id,
            'issue_type': self.issue_type.value,
            'severity': self.severity.value,
            'description': self.description,
            'resolution_status': self.resolution_status.value,
            'position_id': self.position_id,
            'execution_id': self.execution_id,
            'detected_at': self.detected_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_method': self.resolution_method,
            'resolution_details': self.resolution_details,
            'metadata': self.metadata,
            'repair_attempted': self.repair_attempted,
            'repair_method': self.repair_method,
            'repair_successful': self.repair_successful,
            'repair_timestamp': self.repair_timestamp.isoformat() if self.repair_timestamp else None,
            'repair_details': self.repair_details
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IntegrityIssue':
        """Create IntegrityIssue from dictionary"""
        return cls(
            issue_id=data.get('issue_id'),
            validation_id=data['validation_id'],
            issue_type=IssueType(data['issue_type']),
            severity=IssueSeverity(data['severity']),
            description=data['description'],
            resolution_status=ResolutionStatus(data.get('resolution_status', 'open')),
            position_id=data.get('position_id'),
            execution_id=data.get('execution_id'),
            detected_at=datetime.fromisoformat(data['detected_at']),
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            resolution_method=data.get('resolution_method'),
            resolution_details=data.get('resolution_details', {}),
            metadata=data.get('metadata', {}),
            repair_attempted=data.get('repair_attempted', False),
            repair_method=data.get('repair_method'),
            repair_successful=data.get('repair_successful'),
            repair_timestamp=datetime.fromisoformat(data['repair_timestamp']) if data.get('repair_timestamp') else None,
            repair_details=data.get('repair_details', {})
        )