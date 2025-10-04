"""
ImportedExecution domain model - Tracks imported execution IDs for deduplication
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class ImportedExecution:
    """Pure domain model for tracking imported execution IDs"""

    # Primary key
    execution_id: str

    # Audit fields
    csv_filename: Optional[str] = None
    import_timestamp: Optional[datetime] = None
    import_source: str = "CSV_IMPORT"
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate imported execution data after initialization"""
        if not self.execution_id or len(self.execution_id.strip()) == 0:
            raise ValueError("Execution ID cannot be empty")

        # Set import_timestamp to now if not provided
        if self.import_timestamp is None:
            self.import_timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert imported execution to dictionary for serialization"""
        return {
            'execution_id': self.execution_id,
            'csv_filename': self.csv_filename,
            'import_timestamp': self.import_timestamp.isoformat() if self.import_timestamp else None,
            'import_source': self.import_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImportedExecution':
        """Create imported execution from dictionary"""
        return cls(
            execution_id=data.get('execution_id', ''),
            csv_filename=data.get('csv_filename'),
            import_timestamp=datetime.fromisoformat(data['import_timestamp']) if data.get('import_timestamp') else None,
            import_source=data.get('import_source', 'CSV_IMPORT'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
        )
