#!/usr/bin/env python3
"""
Custom Fields Migration Script

Creates the custom fields database schema including:
- custom_fields table for field definitions
- position_custom_field_values table for storing field values per position
- custom_field_options table for select field options
- Performance indexes for optimal query performance
- Rollback procedures for safe deployment

This script implements the database schema defined in the custom fields specification.
"""

import os
import sys
import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CustomFieldsMigration:
    """Handle creation of custom fields database schema"""

    def __init__(self):
        self.db_path = config.db_path
        self.backup_created = False

    def create_backup(self) -> str:
        """Create a backup of the database before migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(self.db_path).replace('.db', f'_custom_fields_backup_{timestamp}.db')

        try:
            import shutil
            shutil.copy2(str(self.db_path), backup_path)
            logger.info(f"Database backup created: {backup_path}")
            self.backup_created = True
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    def check_existing_schema(self) -> dict:
        """Check if custom fields tables already exist"""
        logger.info("Checking existing database schema...")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check for existing tables
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (
                    'custom_fields',
                    'position_custom_field_values',
                    'custom_field_options'
                )
            """)

            existing_tables = [row[0] for row in cursor.fetchall()]

            schema_status = {
                'custom_fields': 'custom_fields' in existing_tables,
                'position_custom_field_values': 'position_custom_field_values' in existing_tables,
                'custom_field_options': 'custom_field_options' in existing_tables,
                'migration_needed': len(existing_tables) < 3
            }

            logger.info(f"Schema status: {schema_status}")
            return schema_status

    def create_custom_fields_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the custom_fields table for field definitions"""
        logger.info("Creating custom_fields table...")

        sql = """
        CREATE TABLE IF NOT EXISTS custom_fields (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            field_type TEXT NOT NULL CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select')),
            description TEXT,
            is_required BOOLEAN NOT NULL DEFAULT 0,
            default_value TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            validation_rules TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_by INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        cursor.execute(sql)
        logger.info("✓ custom_fields table created successfully")

    def create_position_custom_field_values_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the position_custom_field_values table for storing field values"""
        logger.info("Creating position_custom_field_values table...")

        sql = """
        CREATE TABLE IF NOT EXISTS position_custom_field_values (
            id INTEGER PRIMARY KEY,
            position_id INTEGER NOT NULL,
            custom_field_id INTEGER NOT NULL,
            field_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (position_id) REFERENCES positions (id) ON DELETE CASCADE,
            FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
            UNIQUE(position_id, custom_field_id)
        )
        """

        cursor.execute(sql)
        logger.info("✓ position_custom_field_values table created successfully")

    def create_custom_field_options_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the custom_field_options table for select field options"""
        logger.info("Creating custom_field_options table...")

        sql = """
        CREATE TABLE IF NOT EXISTS custom_field_options (
            id INTEGER PRIMARY KEY,
            custom_field_id INTEGER NOT NULL,
            option_value TEXT NOT NULL,
            option_label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
            UNIQUE(custom_field_id, option_value)
        )
        """

        cursor.execute(sql)
        logger.info("✓ custom_field_options table created successfully")

    def create_performance_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Create performance-optimized indexes for custom fields tables"""
        logger.info("Creating performance indexes...")

        indexes = [
            # Custom fields indexes
            "CREATE INDEX IF NOT EXISTS idx_custom_fields_name ON custom_fields(name)",
            "CREATE INDEX IF NOT EXISTS idx_custom_fields_sort_order ON custom_fields(sort_order)",
            "CREATE INDEX IF NOT EXISTS idx_custom_fields_is_active ON custom_fields(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_custom_fields_created_by ON custom_fields(created_by)",
            "CREATE INDEX IF NOT EXISTS idx_custom_fields_field_type ON custom_fields(field_type)",

            # Position custom field values indexes
            "CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_position_id ON position_custom_field_values(position_id)",
            "CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_custom_field_id ON position_custom_field_values(custom_field_id)",
            "CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_composite ON position_custom_field_values(position_id, custom_field_id)",

            # Custom field options indexes
            "CREATE INDEX IF NOT EXISTS idx_custom_field_options_custom_field_id ON custom_field_options(custom_field_id)",
            "CREATE INDEX IF NOT EXISTS idx_custom_field_options_sort_order ON custom_field_options(sort_order)",
            "CREATE INDEX IF NOT EXISTS idx_custom_field_options_is_active ON custom_field_options(is_active)"
        ]

        created_count = 0
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                created_count += 1
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        logger.info(f"✓ Created {created_count} performance indexes")

    def insert_default_custom_fields(self, cursor: sqlite3.Cursor) -> None:
        """Insert some default custom fields to demonstrate functionality"""
        logger.info("Inserting default custom fields...")

        default_fields = [
            {
                'name': 'trade_reviewed',
                'label': 'Trade Reviewed',
                'field_type': 'boolean',
                'description': 'Mark if this position has been reviewed',
                'is_required': False,
                'default_value': 'false',
                'sort_order': 1,
                'validation_rules': json.dumps({"required": False}),
                'is_active': True,
                'created_by': 1
            },
            {
                'name': 'risk_rating',
                'label': 'Risk Rating',
                'field_type': 'select',
                'description': 'Risk assessment for this position',
                'is_required': False,
                'default_value': 'medium',
                'sort_order': 2,
                'validation_rules': json.dumps({"options": ["low", "medium", "high"]}),
                'is_active': True,
                'created_by': 1
            }
        ]

        for field in default_fields:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO custom_fields
                    (name, label, field_type, description, is_required, default_value,
                     sort_order, validation_rules, is_active, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    field['name'],
                    field['label'],
                    field['field_type'],
                    field['description'],
                    field['is_required'],
                    field['default_value'],
                    field['sort_order'],
                    field['validation_rules'],
                    field['is_active'],
                    field['created_by']
                ))

                # Insert options for select fields
                if field['field_type'] == 'select':
                    field_id = cursor.execute(
                        "SELECT id FROM custom_fields WHERE name = ?",
                        (field['name'],)
                    ).fetchone()[0]

                    validation_rules = json.loads(field['validation_rules'])
                    if 'options' in validation_rules:
                        for i, option in enumerate(validation_rules['options']):
                            cursor.execute("""
                                INSERT OR IGNORE INTO custom_field_options
                                (custom_field_id, option_value, option_label, sort_order)
                                VALUES (?, ?, ?, ?)
                            """, (field_id, option, option.capitalize(), i))

                logger.info(f"✓ Created default field: {field['name']}")

            except Exception as e:
                logger.warning(f"Could not create default field {field['name']}: {e}")

        logger.info("✓ Default custom fields inserted")

    def verify_schema(self, cursor: sqlite3.Cursor) -> bool:
        """Verify the migration was successful"""
        logger.info("Verifying migration results...")

        try:
            # Check all tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (
                    'custom_fields',
                    'position_custom_field_values',
                    'custom_field_options'
                )
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if len(tables) != 3:
                logger.error(f"Expected 3 tables, found {len(tables)}: {tables}")
                return False

            # Check foreign key constraints
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()
            if fk_violations:
                logger.error(f"Foreign key violations found: {fk_violations}")
                return False

            # Check default data
            cursor.execute("SELECT COUNT(*) FROM custom_fields")
            field_count = cursor.fetchone()[0]
            logger.info(f"Found {field_count} custom fields")

            # Check indexes exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_custom_fields%'
                   OR name LIKE 'idx_position_custom_field%'
            """)
            indexes = cursor.fetchall()
            logger.info(f"Found {len(indexes)} custom field indexes")

            logger.info("✓ Migration verification successful")
            return True

        except Exception as e:
            logger.error(f"Migration verification failed: {e}")
            return False

    def run_migration(self, create_backup: bool = True, insert_defaults: bool = True) -> bool:
        """Execute the complete migration process"""
        logger.info("Starting custom fields migration...")

        try:
            # Create backup if requested
            if create_backup:
                self.create_backup()

            # Check current schema
            schema_status = self.check_existing_schema()
            if not schema_status['migration_needed']:
                logger.info("Custom fields schema already exists, skipping migration")
                return True

            # Connect to database and run migration
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.cursor()

                # Create tables
                self.create_custom_fields_table(cursor)
                self.create_position_custom_field_values_table(cursor)
                self.create_custom_field_options_table(cursor)

                # Create indexes
                self.create_performance_indexes(cursor)

                # Insert default data if requested
                if insert_defaults:
                    self.insert_default_custom_fields(cursor)

                # Verify migration
                if not self.verify_schema(cursor):
                    logger.error("Migration verification failed, rolling back...")
                    conn.rollback()
                    return False

                # Commit changes
                conn.commit()

            logger.info("✓ Custom fields migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def rollback_migration(self) -> bool:
        """Rollback the custom fields migration (remove all tables)"""
        logger.info("Rolling back custom fields migration...")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Drop tables in reverse order due to foreign keys
                rollback_sql = """
                DROP TABLE IF EXISTS custom_field_options;
                DROP TABLE IF EXISTS position_custom_field_values;
                DROP TABLE IF EXISTS custom_fields;
                """

                cursor.executescript(rollback_sql)
                conn.commit()

            logger.info("✓ Custom fields migration rollback completed")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description='Custom Fields Migration Script')
    parser.add_argument('--rollback', action='store_true',
                       help='Rollback the migration (remove custom fields tables)')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip creating database backup')
    parser.add_argument('--no-defaults', action='store_true',
                       help='Skip inserting default custom fields')

    args = parser.parse_args()

    migration = CustomFieldsMigration()

    if args.rollback:
        success = migration.rollback_migration()
    else:
        success = migration.run_migration(
            create_backup=not args.no_backup,
            insert_defaults=not args.no_defaults
        )

    if success:
        logger.info("Operation completed successfully")
        sys.exit(0)
    else:
        logger.error("Operation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()