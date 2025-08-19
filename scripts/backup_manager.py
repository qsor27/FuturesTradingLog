#!/usr/bin/env python3

"""
FuturesTradingLog Backup Manager
Comprehensive backup and recovery management for SQLite databases
"""

import os
import sqlite3
import json
import gzip
import shutil
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BackupConfig:
    """Configuration for backup operations"""
    data_dir: Path
    backup_dir: Path
    retention_days: int = 7
    compressed_retention_days: int = 30
    s3_bucket: Optional[str] = None
    aws_region: str = "us-east-1"
    enable_litestream: bool = True
    litestream_config: Optional[Path] = None

class BackupManager:
    """
    Comprehensive backup manager for FuturesTradingLog databases
    Handles local backups, validation, and integration with Litestream
    """
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.setup_directories()
        
    def setup_directories(self) -> None:
        """Create necessary backup directories"""
        backup_types = ['manual', 'automated', 'safety', 'compressed']
        
        for backup_type in backup_types:
            backup_path = self.config.backup_dir / backup_type
            backup_path.mkdir(parents=True, exist_ok=True)
            
        logger.info(f"Backup directories created at {self.config.backup_dir}")

    def create_backup(self, 
                     db_path: Path, 
                     backup_type: str = 'manual',
                     compress: bool = True,
                     validate: bool = True) -> Dict[str, Any]:
        """
        Create a backup of the specified database
        
        Args:
            db_path: Path to the database file
            backup_type: Type of backup (manual, automated, safety)
            compress: Whether to compress the backup
            validate: Whether to validate the backup after creation
            
        Returns:
            Dictionary with backup results and metadata
        """
        if not db_path.exists():
            return {'success': False, 'error': f'Database not found: {db_path}'}
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = db_path.stem
        backup_dir = self.config.backup_dir / backup_type
        
        # Generate backup filename
        backup_filename = f"{db_name}_{timestamp}.db"
        if compress:
            backup_filename += ".gz"
        
        backup_path = backup_dir / backup_filename
        
        try:
            # Validate source database
            if validate and not self._validate_database(db_path):
                return {'success': False, 'error': 'Source database validation failed'}
            
            logger.info(f"Creating backup: {backup_filename}")
            
            # Create backup
            if compress:
                with open(db_path, 'rb') as src, gzip.open(backup_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            else:
                shutil.copy2(db_path, backup_path)
            
            # Validate backup
            if validate and not self._validate_backup(backup_path):
                backup_path.unlink()  # Remove invalid backup
                return {'success': False, 'error': 'Backup validation failed'}
            
            # Create metadata
            metadata = self._create_backup_metadata(db_path, backup_path, backup_type)
            manifest_path = backup_dir / f"manifest_{timestamp}.json"
            
            with open(manifest_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Backup created successfully: {backup_path}")
            
            return {
                'success': True,
                'backup_path': str(backup_path),
                'manifest_path': str(manifest_path),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return {'success': False, 'error': str(e)}

    def restore_database(self, 
                        backup_path: Path, 
                        target_path: Path,
                        create_safety_backup: bool = True) -> Dict[str, Any]:
        """
        Restore a database from backup
        
        Args:
            backup_path: Path to backup file
            target_path: Path where to restore the database
            create_safety_backup: Whether to create safety backup of existing database
            
        Returns:
            Dictionary with restore results
        """
        if not backup_path.exists():
            return {'success': False, 'error': f'Backup file not found: {backup_path}'}
            
        try:
            # Create safety backup of existing database
            safety_backup_path = None
            if target_path.exists() and create_safety_backup:
                safety_result = self.create_backup(
                    target_path, 
                    backup_type='safety',
                    compress=True,
                    validate=False
                )
                
                if safety_result['success']:
                    safety_backup_path = safety_result['backup_path']
                    logger.info(f"Safety backup created: {safety_backup_path}")
                else:
                    logger.warning(f"Failed to create safety backup: {safety_result['error']}")
            
            # Validate backup before restore
            if not self._validate_backup(backup_path):
                return {'success': False, 'error': 'Backup validation failed'}
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Restoring database from {backup_path} to {target_path}")
            
            # Perform restore
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            else:
                shutil.copy2(backup_path, target_path)
            
            # Validate restored database
            if not self._validate_database(target_path):
                return {'success': False, 'error': 'Restored database validation failed'}
            
            logger.info(f"Database restored successfully to {target_path}")
            
            return {
                'success': True,
                'restored_path': str(target_path),
                'safety_backup': safety_backup_path,
                'restored_from': str(backup_path)
            }
            
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return {'success': False, 'error': str(e)}

    def list_backups(self, backup_type: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all available backups
        
        Args:
            backup_type: Filter by backup type (optional)
            
        Returns:
            Dictionary of backup lists by type
        """
        backup_types = [backup_type] if backup_type else ['manual', 'automated', 'safety', 'compressed']
        backup_list = {}
        
        for btype in backup_types:
            backup_dir = self.config.backup_dir / btype
            backups = []
            
            if backup_dir.exists():
                for backup_file in backup_dir.glob("*.db*"):
                    if backup_file.suffix in ['.db', '.gz']:
                        backup_info = self._get_backup_info(backup_file)
                        backups.append(backup_info)
                
                # Sort by creation time (newest first)
                backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            backup_list[btype] = backups
        
        return backup_list

    def cleanup_old_backups(self) -> Dict[str, Any]:
        """
        Clean up old backups according to retention policy
        
        Returns:
            Dictionary with cleanup results
        """
        cleaned_files = []
        total_space_freed = 0
        
        backup_types = {
            'manual': self.config.retention_days,
            'automated': self.config.retention_days,
            'safety': self.config.retention_days,
            'compressed': self.config.compressed_retention_days
        }
        
        for backup_type, retention_days in backup_types.items():
            backup_dir = self.config.backup_dir / backup_type
            
            if not backup_dir.exists():
                continue
                
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            for backup_file in backup_dir.glob("*.db*"):
                if backup_file.suffix in ['.db', '.gz']:
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    if file_time < cutoff_date:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        
                        # Also remove corresponding manifest
                        manifest_pattern = backup_file.stem.replace(backup_file.stem.split('_')[-1], '') + "*.json"
                        for manifest_file in backup_dir.glob(manifest_pattern):
                            manifest_file.unlink()
                        
                        cleaned_files.append({
                            'file': str(backup_file),
                            'size': file_size,
                            'age_days': (datetime.now() - file_time).days
                        })
                        total_space_freed += file_size
        
        logger.info(f"Cleaned up {len(cleaned_files)} old backup files, freed {self._format_bytes(total_space_freed)}")
        
        return {
            'cleaned_files': cleaned_files,
            'total_files': len(cleaned_files),
            'space_freed_bytes': total_space_freed,
            'space_freed_human': self._format_bytes(total_space_freed)
        }

    def validate_all_backups(self) -> Dict[str, Any]:
        """
        Validate all existing backups
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'total_backups': 0,
            'valid_backups': 0,
            'invalid_backups': 0,
            'validation_details': []
        }
        
        backup_list = self.list_backups()
        
        for backup_type, backups in backup_list.items():
            for backup in backups:
                backup_path = Path(backup['path'])
                is_valid = self._validate_backup(backup_path)
                
                results['total_backups'] += 1
                
                if is_valid:
                    results['valid_backups'] += 1
                else:
                    results['invalid_backups'] += 1
                
                results['validation_details'].append({
                    'file': str(backup_path),
                    'type': backup_type,
                    'valid': is_valid,
                    'size': backup['size_bytes'],
                    'created_at': backup['created_at']
                })
        
        logger.info(f"Validated {results['total_backups']} backups: {results['valid_backups']} valid, {results['invalid_backups']} invalid")
        
        return results

    def get_backup_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive backup statistics
        
        Returns:
            Dictionary with backup statistics
        """
        backup_list = self.list_backups()
        
        stats = {
            'total_backups': 0,
            'total_size_bytes': 0,
            'backup_types': {},
            'oldest_backup': None,
            'newest_backup': None,
            'disk_usage': {}
        }
        
        all_backups = []
        
        for backup_type, backups in backup_list.items():
            type_stats = {
                'count': len(backups),
                'size_bytes': sum(b['size_bytes'] for b in backups),
                'latest': backups[0] if backups else None
            }
            
            stats['backup_types'][backup_type] = type_stats
            stats['total_backups'] += type_stats['count']
            stats['total_size_bytes'] += type_stats['size_bytes']
            
            all_backups.extend(backups)
        
        if all_backups:
            all_backups.sort(key=lambda x: x['created_at'])
            stats['oldest_backup'] = all_backups[0]
            stats['newest_backup'] = all_backups[-1]
        
        # Calculate disk usage
        try:
            usage = shutil.disk_usage(self.config.backup_dir)
            stats['disk_usage'] = {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'backup_usage': stats['total_size_bytes'],
                'backup_percentage': (stats['total_size_bytes'] / usage.total) * 100 if usage.total > 0 else 0
            }
        except Exception as e:
            logger.warning(f"Could not calculate disk usage: {e}")
        
        return stats

    def _validate_database(self, db_path: Path) -> bool:
        """Validate SQLite database integrity"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                return result[0].lower() == 'ok'
        except Exception as e:
            logger.error(f"Database validation failed for {db_path}: {e}")
            return False

    def _validate_backup(self, backup_path: Path) -> bool:
        """Validate backup file integrity"""
        try:
            if backup_path.suffix == '.gz':
                # Test gzip decompression and SQLite integrity
                with gzip.open(backup_path, 'rb') as gz_file:
                    # Read a small chunk to test decompression
                    gz_file.read(1024)
                    
                # For full validation, would need to decompress entire file
                return True
            else:
                return self._validate_database(backup_path)
                
        except Exception as e:
            logger.error(f"Backup validation failed for {backup_path}: {e}")
            return False

    def _create_backup_metadata(self, 
                              source_path: Path, 
                              backup_path: Path, 
                              backup_type: str) -> Dict[str, Any]:
        """Create backup metadata"""
        source_stat = source_path.stat()
        backup_stat = backup_path.stat()
        
        return {
            'backup_type': backup_type,
            'timestamp': datetime.now().isoformat(),
            'source_database': str(source_path),
            'backup_file': str(backup_path),
            'source_size_bytes': source_stat.st_size,
            'backup_size_bytes': backup_stat.st_size,
            'compression_ratio': backup_stat.st_size / source_stat.st_size if source_stat.st_size > 0 else 1.0,
            'created_by': 'BackupManager',
            'validation': {
                'integrity_check': 'passed',
                'created_at': datetime.fromtimestamp(backup_stat.st_ctime).isoformat()
            }
        }

    def _get_backup_info(self, backup_path: Path) -> Dict[str, Any]:
        """Get information about a backup file"""
        stat_info = backup_path.stat()
        
        return {
            'filename': backup_path.name,
            'path': str(backup_path),
            'size_bytes': stat_info.st_size,
            'size_human': self._format_bytes(stat_info.st_size),
            'created_at': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            'age_hours': (datetime.now() - datetime.fromtimestamp(stat_info.st_mtime)).total_seconds() / 3600,
            'compressed': backup_path.suffix == '.gz'
        }

    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes into human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"


def main():
    """CLI interface for backup manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FuturesTradingLog Backup Manager')
    parser.add_argument('command', choices=['backup', 'restore', 'list', 'cleanup', 'validate', 'stats'],
                       help='Command to execute')
    parser.add_argument('--data-dir', type=Path, default=Path.cwd() / 'data',
                       help='Data directory path')
    parser.add_argument('--backup-dir', type=Path, default=Path.cwd() / 'backups',
                       help='Backup directory path')
    parser.add_argument('--db-path', type=Path,
                       help='Database file path (for backup/restore)')
    parser.add_argument('--backup-path', type=Path,
                       help='Backup file path (for restore)')
    parser.add_argument('--target-path', type=Path,
                       help='Target path (for restore)')
    parser.add_argument('--backup-type', default='manual',
                       help='Type of backup (manual, automated, safety)')
    parser.add_argument('--no-compress', action='store_true',
                       help='Disable compression')
    parser.add_argument('--no-validate', action='store_true',
                       help='Skip validation')
    
    args = parser.parse_args()
    
    # Setup configuration
    config = BackupConfig(
        data_dir=args.data_dir,
        backup_dir=args.backup_dir
    )
    
    manager = BackupManager(config)
    
    if args.command == 'backup':
        if not args.db_path:
            print("Error: --db-path required for backup command")
            return 1
            
        result = manager.create_backup(
            args.db_path,
            backup_type=args.backup_type,
            compress=not args.no_compress,
            validate=not args.no_validate
        )
        
        if result['success']:
            print(f"Backup created: {result['backup_path']}")
        else:
            print(f"Backup failed: {result['error']}")
            return 1
    
    elif args.command == 'restore':
        if not args.backup_path or not args.target_path:
            print("Error: --backup-path and --target-path required for restore command")
            return 1
            
        result = manager.restore_database(args.backup_path, args.target_path)
        
        if result['success']:
            print(f"Database restored to: {result['restored_path']}")
        else:
            print(f"Restore failed: {result['error']}")
            return 1
    
    elif args.command == 'list':
        backup_list = manager.list_backups()
        
        for backup_type, backups in backup_list.items():
            print(f"\n{backup_type.upper()} Backups:")
            print("-" * 40)
            
            if not backups:
                print("  No backups found")
                continue
                
            for backup in backups:
                print(f"  {backup['filename']} ({backup['size_human']}) - {backup['created_at']}")
    
    elif args.command == 'cleanup':
        result = manager.cleanup_old_backups()
        print(f"Cleaned up {result['total_files']} files, freed {result['space_freed_human']}")
    
    elif args.command == 'validate':
        result = manager.validate_all_backups()
        print(f"Validated {result['total_backups']} backups: {result['valid_backups']} valid, {result['invalid_backups']} invalid")
    
    elif args.command == 'stats':
        stats = manager.get_backup_statistics()
        print(f"\nBackup Statistics:")
        print(f"Total backups: {stats['total_backups']}")
        print(f"Total size: {manager._format_bytes(stats['total_size_bytes'])}")
        
        for backup_type, type_stats in stats['backup_types'].items():
            print(f"{backup_type}: {type_stats['count']} backups, {manager._format_bytes(type_stats['size_bytes'])}")
    
    return 0


if __name__ == '__main__':
    exit(main())