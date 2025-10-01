"""
File Processing Interface - Contract for file processing operations
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class ICSVProcessor(ABC):
    """
    Interface for CSV processing operations
    
    Defines the contract for CSV file processing
    """
    
    @abstractmethod
    def process_uploaded_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Process uploaded CSV file
        
        Args:
            file_path: Path to uploaded file
            filename: Original filename
            
        Returns:
            Dictionary with processing results
        """
        pass
    
    @abstractmethod
    def validate_csv_format(self, file_path: str) -> Dict[str, Any]:
        """
        Validate CSV file format
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dictionary with validation results
        """
        pass
    
    @abstractmethod
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get CSV processing statistics
        
        Returns:
            Dictionary with processing statistics
        """
        pass


class IFileUploadService(ABC):
    """
    Interface for file upload operations
    """
    
    @abstractmethod
    def handle_file_upload(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Handle file upload
        
        Args:
            file_data: Raw file data
            filename: Original filename
            
        Returns:
            Dictionary with upload results
        """
        pass
    
    @abstractmethod
    def validate_upload_request(self, filename: str, file_size: int) -> Dict[str, Any]:
        """
        Validate file upload request
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            
        Returns:
            Dictionary with validation results
        """
        pass
    
    @abstractmethod
    def get_upload_statistics(self) -> Dict[str, Any]:
        """
        Get upload statistics
        
        Returns:
            Dictionary with upload statistics
        """
        pass


class IFileArchiveService(ABC):
    """
    Interface for file archiving operations
    """
    
    @abstractmethod
    def archive_file(self, file_path: str, filename: str) -> str:
        """
        Archive processed file
        
        Args:
            file_path: Path to file to archive
            filename: Original filename
            
        Returns:
            Path to archived file
        """
        pass
    
    @abstractmethod
    def get_archive_statistics(self) -> Dict[str, Any]:
        """
        Get archive statistics
        
        Returns:
            Dictionary with archive statistics
        """
        pass
    
    @abstractmethod
    def cleanup_old_archives(self, days_old: int = 30) -> Dict[str, Any]:
        """
        Clean up old archived files
        
        Args:
            days_old: Remove files older than this many days
            
        Returns:
            Dictionary with cleanup results
        """
        pass