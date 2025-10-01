"""
CSV Processor Service - Business logic for CSV file processing

Extracted from routes/upload.py to separate business logic from HTTP handling
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
import csv
import os
from datetime import datetime
import tempfile
import shutil

from ...domain.interfaces.file_processing_interface import ICSVProcessor

logger = logging.getLogger('csv_processor')


class CSVProcessor(ICSVProcessor):
    """
    Application service for CSV file processing
    
    Handles CSV validation, parsing, and processing for trade data
    """
    
    def __init__(self, db_service=None, upload_dir: str = 'data/uploads'):
        self.db_service = db_service
        self.upload_dir = upload_dir
        self.supported_formats = ['.csv']
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def process_uploaded_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Process uploaded CSV file
        
        Args:
            file_path: Path to uploaded file
            filename: Original filename
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Validate file
            validation_result = self._validate_file(file_path, filename)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors'],
                    'filename': filename
                }
            
            # Parse CSV file
            parse_result = self._parse_csv_file(file_path)
            if not parse_result['success']:
                return {
                    'success': False,
                    'error': parse_result['error'],
                    'filename': filename
                }
            
            # Validate data format
            validation_result = self._validate_csv_data(parse_result['data'])
            if not validation_result['valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors'],
                    'filename': filename,
                    'rows_parsed': len(parse_result['data'])
                }
            
            # Process data
            processing_result = self._process_csv_data(parse_result['data'])
            
            # Archive file
            archive_path = self._archive_file(file_path, filename)
            
            return {
                'success': True,
                'filename': filename,
                'rows_processed': processing_result['rows_processed'],
                'trades_created': processing_result['trades_created'],
                'errors': processing_result['errors'],
                'warnings': processing_result['warnings'],
                'archive_path': archive_path,
                'processing_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing uploaded file {filename}: {e}")
            return {
                'success': False,
                'error': str(e),
                'filename': filename
            }
    
    def validate_csv_format(self, file_path: str) -> Dict[str, Any]:
        """
        Validate CSV file format without processing
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Parse sample of CSV
            sample_result = self._parse_csv_sample(file_path, sample_size=10)
            
            if not sample_result['success']:
                return {
                    'valid': False,
                    'error': sample_result['error']
                }
            
            # Validate sample data
            validation_result = self._validate_csv_data(sample_result['data'])
            
            return {
                'valid': validation_result['valid'],
                'errors': validation_result['errors'],
                'warnings': validation_result['warnings'],
                'sample_rows': len(sample_result['data']),
                'detected_columns': sample_result['columns']
            }
            
        except Exception as e:
            logger.error(f"Error validating CSV format: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get CSV processing statistics
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get archive directory statistics
            archive_stats = self._get_archive_statistics()
            
            # Get recent processing history
            recent_files = self._get_recent_processed_files()
            
            return {
                'success': True,
                'archive_statistics': archive_stats,
                'recent_files': recent_files,
                'supported_formats': self.supported_formats,
                'max_file_size_mb': self.max_file_size / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Validate uploaded file
        
        Args:
            file_path: Path to file
            filename: Original filename
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        
        # Check file extension
        _, ext = os.path.splitext(filename.lower())
        if ext not in self.supported_formats:
            errors.append(f"Unsupported file format: {ext}. Supported: {self.supported_formats}")
        
        # Check file size
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                errors.append(f"File too large: {file_size} bytes. Maximum: {self.max_file_size} bytes")
            elif file_size == 0:
                errors.append("File is empty")
        else:
            errors.append("File not found")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _parse_csv_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse CSV file
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dictionary with parsed data
        """
        try:
            data = []
            columns = []
            
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                columns = reader.fieldnames or []
                
                for row_num, row in enumerate(reader, 1):
                    # Clean and validate row
                    cleaned_row = {k: v.strip() if isinstance(v, str) else v 
                                 for k, v in row.items()}
                    cleaned_row['_row_number'] = row_num
                    data.append(cleaned_row)
            
            return {
                'success': True,
                'data': data,
                'columns': columns,
                'row_count': len(data)
            }
            
        except Exception as e:
            logger.error(f"Error parsing CSV file {file_path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_csv_sample(self, file_path: str, sample_size: int = 10) -> Dict[str, Any]:
        """
        Parse sample of CSV file for validation
        
        Args:
            file_path: Path to CSV file
            sample_size: Number of rows to sample
            
        Returns:
            Dictionary with sample data
        """
        try:
            data = []
            columns = []
            
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                columns = reader.fieldnames or []
                
                for row_num, row in enumerate(reader, 1):
                    if row_num > sample_size:
                        break
                    
                    cleaned_row = {k: v.strip() if isinstance(v, str) else v 
                                 for k, v in row.items()}
                    cleaned_row['_row_number'] = row_num
                    data.append(cleaned_row)
            
            return {
                'success': True,
                'data': data,
                'columns': columns,
                'row_count': len(data)
            }
            
        except Exception as e:
            logger.error(f"Error parsing CSV sample {file_path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_csv_data(self, data: List[Dict]) -> Dict[str, Any]:
        """
        Validate parsed CSV data
        
        Args:
            data: List of parsed CSV rows
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        if not data:
            errors.append("No data found in CSV file")
            return {
                'valid': False,
                'errors': errors,
                'warnings': warnings
            }
        
        # Check for required columns
        required_columns = ['instrument', 'side_of_market', 'quantity', 'entry_price', 'entry_time']
        first_row = data[0]
        
        for col in required_columns:
            if col not in first_row:
                errors.append(f"Missing required column: {col}")
        
        # Validate data types and ranges
        for i, row in enumerate(data[:10]):  # Validate first 10 rows
            row_num = row.get('_row_number', i + 1)
            
            # Validate quantity
            try:
                quantity = float(row.get('quantity', 0))
                if quantity <= 0:
                    errors.append(f"Row {row_num}: Invalid quantity {quantity}")
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Quantity must be a number")
            
            # Validate entry_price
            try:
                entry_price = float(row.get('entry_price', 0))
                if entry_price <= 0:
                    errors.append(f"Row {row_num}: Invalid entry price {entry_price}")
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Entry price must be a number")
            
            # Validate side_of_market
            side = row.get('side_of_market', '').strip()
            valid_sides = ['Buy', 'Sell', 'Long', 'Short', 'BuyToCover', 'SellShort']
            if side not in valid_sides:
                warnings.append(f"Row {row_num}: Unknown side of market '{side}'")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _process_csv_data(self, data: List[Dict]) -> Dict[str, Any]:
        """
        Process validated CSV data
        
        Args:
            data: List of validated CSV rows
            
        Returns:
            Dictionary with processing results
        """
        try:
            if not self.db_service:
                raise ValueError("Database service not available")
            
            rows_processed = 0
            trades_created = 0
            errors = []
            warnings = []
            
            for row in data:
                try:
                    # Transform row to trade format
                    trade_data = self._transform_row_to_trade(row)
                    
                    # Insert into database
                    trade_id = self.db_service.insert_trade(trade_data)
                    
                    if trade_id:
                        trades_created += 1
                    
                    rows_processed += 1
                    
                except Exception as e:
                    row_num = row.get('_row_number', 'unknown')
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return {
                'rows_processed': rows_processed,
                'trades_created': trades_created,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error processing CSV data: {e}")
            return {
                'rows_processed': 0,
                'trades_created': 0,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _transform_row_to_trade(self, row: Dict) -> Dict:
        """
        Transform CSV row to trade data format
        
        Args:
            row: CSV row dictionary
            
        Returns:
            Trade data dictionary
        """
        return {
            'instrument': row.get('instrument', ''),
            'account': row.get('account', ''),
            'side_of_market': row.get('side_of_market', ''),
            'quantity': int(float(row.get('quantity', 0))),
            'entry_price': float(row.get('entry_price', 0)),
            'exit_price': float(row.get('exit_price', 0)) if row.get('exit_price') else None,
            'entry_time': row.get('entry_time', ''),
            'exit_time': row.get('exit_time', '') if row.get('exit_time') else None,
            'entry_execution_id': row.get('entry_execution_id', ''),
            'exit_execution_id': row.get('exit_execution_id', '') if row.get('exit_execution_id') else None,
            'points_gain_loss': float(row.get('points_gain_loss', 0)),
            'dollars_gain_loss': float(row.get('dollars_gain_loss', 0)),
            'commission': float(row.get('commission', 0)),
            'link_group_id': row.get('link_group_id', '') if row.get('link_group_id') else None,
        }
    
    def _archive_file(self, file_path: str, filename: str) -> str:
        """
        Archive processed file
        
        Args:
            file_path: Path to original file
            filename: Original filename
            
        Returns:
            Path to archived file
        """
        try:
            # Create archive directory
            archive_dir = os.path.join(self.upload_dir, 'archive')
            os.makedirs(archive_dir, exist_ok=True)
            
            # Create timestamped filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name, ext = os.path.splitext(filename)
            archived_filename = f"{name}_{timestamp}{ext}"
            
            archive_path = os.path.join(archive_dir, archived_filename)
            
            # Copy file to archive
            shutil.copy2(file_path, archive_path)
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Error archiving file {filename}: {e}")
            return file_path
    
    def _get_archive_statistics(self) -> Dict[str, Any]:
        """
        Get archive directory statistics
        
        Returns:
            Dictionary with archive statistics
        """
        try:
            archive_dir = os.path.join(self.upload_dir, 'archive')
            
            if not os.path.exists(archive_dir):
                return {
                    'total_files': 0,
                    'total_size_mb': 0
                }
            
            total_files = 0
            total_size = 0
            
            for filename in os.listdir(archive_dir):
                file_path = os.path.join(archive_dir, filename)
                if os.path.isfile(file_path):
                    total_files += 1
                    total_size += os.path.getsize(file_path)
            
            return {
                'total_files': total_files,
                'total_size_mb': total_size / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Error getting archive statistics: {e}")
            return {
                'total_files': 0,
                'total_size_mb': 0
            }
    
    def _get_recent_processed_files(self, limit: int = 10) -> List[Dict]:
        """
        Get recently processed files
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of recent file information
        """
        try:
            archive_dir = os.path.join(self.upload_dir, 'archive')
            
            if not os.path.exists(archive_dir):
                return []
            
            files = []
            for filename in os.listdir(archive_dir):
                file_path = os.path.join(archive_dir, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append({
                        'filename': filename,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'processed_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x['processed_at'], reverse=True)
            
            return files[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent processed files: {e}")
            return []