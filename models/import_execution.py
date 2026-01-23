"""
Import Execution Data Models

Type-safe representations of import execution logs and row-level logs.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator


class ImportStatus(str, Enum):
    """Valid import execution statuses"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class RowStatus(str, Enum):
    """Valid row-level statuses"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorCategory(str, Enum):
    """Valid error categories for row-level errors"""
    VALIDATION_ERROR = "validation_error"
    PARSING_ERROR = "parsing_error"
    DUPLICATE_ERROR = "duplicate_error"
    DATABASE_ERROR = "database_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"


class ImportExecutionLog(BaseModel):
    """
    Validated import execution log record.

    Represents a complete import operation with summary statistics.
    """

    # Core fields
    id: Optional[int] = Field(None, description="Auto-generated ID")
    import_batch_id: str = Field(..., min_length=1, description="Unique batch identifier")
    file_name: str = Field(..., min_length=1, description="Name of imported file")
    file_path: str = Field(..., min_length=1, description="Full path to file")
    file_hash: str = Field(..., min_length=1, description="SHA256 hash of file")
    import_time: datetime = Field(default_factory=datetime.now, description="When import started")
    status: ImportStatus = Field(..., description="Overall import status")

    # Summary statistics
    total_rows: int = Field(0, ge=0, description="Total rows in file")
    success_rows: int = Field(0, ge=0, description="Successfully imported rows")
    failed_rows: int = Field(0, ge=0, description="Failed rows")
    skipped_rows: int = Field(0, ge=0, description="Skipped rows")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time in milliseconds")

    # Additional metadata
    affected_accounts: Optional[str] = Field(None, description="JSON array of affected account names")
    error_summary: Optional[str] = Field(None, description="High-level error description")
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation time")

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "import_batch_id": "batch_20240115_093000_abc123",
                "file_name": "executions.csv",
                "file_path": "/data/executions.csv",
                "file_hash": "sha256_hash_here",
                "status": "success",
                "total_rows": 100,
                "success_rows": 98,
                "failed_rows": 2,
                "skipped_rows": 0,
                "processing_time_ms": 1234,
                "affected_accounts": '["Sim101", "Live202"]'
            }
        }

    @validator('status', pre=True)
    def validate_status(cls, v):
        """Validate and normalize status value"""
        if isinstance(v, str):
            return ImportStatus(v.lower())
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'import_batch_id': self.import_batch_id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_hash': self.file_hash,
            'import_time': self.import_time,
            'status': self.status.value,
            'total_rows': self.total_rows,
            'success_rows': self.success_rows,
            'failed_rows': self.failed_rows,
            'skipped_rows': self.skipped_rows,
            'processing_time_ms': self.processing_time_ms,
            'affected_accounts': self.affected_accounts,
            'error_summary': self.error_summary,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ImportExecutionLog':
        """Create ImportExecutionLog from dictionary"""
        return cls(**data)


class ImportExecutionRowLog(BaseModel):
    """
    Validated row-level import log record.

    Represents processing result for a single CSV row.
    """

    # Core fields
    id: Optional[int] = Field(None, description="Auto-generated ID")
    import_batch_id: str = Field(..., min_length=1, description="Reference to parent batch")
    row_number: int = Field(..., ge=1, description="Row number in CSV (1-based)")
    status: RowStatus = Field(..., description="Row processing status")

    # Error details
    error_message: Optional[str] = Field(None, description="Human-readable error message")
    error_category: Optional[ErrorCategory] = Field(None, description="Error classification")

    # Row data
    raw_row_data: Optional[str] = Field(None, description="JSON representation of CSV row")
    validation_errors: Optional[str] = Field(None, description="JSON array of validation errors")

    # Result
    created_trade_id: Optional[int] = Field(None, description="ID of created trade if successful")
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation time")

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "import_batch_id": "batch_20240115_093000_abc123",
                "row_number": 5,
                "status": "failed",
                "error_message": "Invalid price format",
                "error_category": "validation_error",
                "raw_row_data": '{"ID": "12345", "Price": "invalid"}',
                "validation_errors": '[{"field": "price", "error": "must be numeric"}]'
            }
        }

    @validator('status', pre=True)
    def validate_status(cls, v):
        """Validate and normalize status value"""
        if isinstance(v, str):
            return RowStatus(v.lower())
        return v

    @validator('error_category', pre=True)
    def validate_error_category(cls, v):
        """Validate and normalize error category"""
        if v is None:
            return None
        if isinstance(v, str):
            return ErrorCategory(v.lower())
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'import_batch_id': self.import_batch_id,
            'row_number': self.row_number,
            'status': self.status.value,
            'error_message': self.error_message,
            'error_category': self.error_category.value if self.error_category else None,
            'raw_row_data': self.raw_row_data,
            'validation_errors': self.validation_errors,
            'created_trade_id': self.created_trade_id,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ImportExecutionRowLog':
        """Create ImportExecutionRowLog from dictionary"""
        return cls(**data)


class ImportExecutionSummary(BaseModel):
    """
    Summary view for import execution logs page.

    Combines import_execution_logs data with additional computed fields.
    """

    # From import_execution_logs
    id: int
    import_batch_id: str
    file_name: str
    file_path: str
    import_time: datetime
    status: ImportStatus
    total_rows: int
    success_rows: int
    failed_rows: int
    skipped_rows: int
    processing_time_ms: Optional[int]
    affected_accounts: Optional[List[str]]
    error_summary: Optional[str]

    # Computed fields
    success_rate: float = Field(description="Success percentage (0-100)")
    has_errors: bool = Field(description="Whether import had any errors")

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('affected_accounts', pre=True)
    def parse_affected_accounts(cls, v):
        """Parse JSON string to list"""
        if v is None:
            return None
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'ImportExecutionSummary':
        """Create summary from database row"""
        import json

        total = row.get('total_rows', 0)
        success = row.get('success_rows', 0)
        failed = row.get('failed_rows', 0)

        # Calculate success rate
        success_rate = (success / total * 100) if total > 0 else 0

        # Parse affected accounts if JSON string
        affected_accounts = row.get('affected_accounts')
        if isinstance(affected_accounts, str):
            try:
                affected_accounts = json.loads(affected_accounts)
            except:
                affected_accounts = None

        return cls(
            id=row.get('id'),
            import_batch_id=row.get('import_batch_id'),
            file_name=row.get('file_name'),
            file_path=row.get('file_path'),
            import_time=row.get('import_time'),
            status=row.get('status'),
            total_rows=total,
            success_rows=success,
            failed_rows=failed,
            skipped_rows=row.get('skipped_rows', 0),
            processing_time_ms=row.get('processing_time_ms'),
            affected_accounts=affected_accounts,
            error_summary=row.get('error_summary'),
            success_rate=success_rate,
            has_errors=(failed > 0)
        )
