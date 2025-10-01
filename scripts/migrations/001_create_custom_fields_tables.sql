-- Migration: 001_create_custom_fields_tables.sql
-- Description: Create tables for position custom fields functionality
-- Date: 2025-09-29
-- Version: 1.0.0

BEGIN TRANSACTION;

-- Create custom_fields table
CREATE TABLE IF NOT EXISTS custom_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
);

-- Create position_custom_field_values table
CREATE TABLE IF NOT EXISTS position_custom_field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    custom_field_id INTEGER NOT NULL,
    field_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions (id) ON DELETE CASCADE,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
    UNIQUE(position_id, custom_field_id)
);

-- Create custom_field_options table
CREATE TABLE IF NOT EXISTS custom_field_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    custom_field_id INTEGER NOT NULL,
    option_value TEXT NOT NULL,
    option_label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields (id) ON DELETE CASCADE,
    UNIQUE(custom_field_id, option_value)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_custom_fields_name ON custom_fields(name);
CREATE INDEX IF NOT EXISTS idx_custom_fields_sort_order ON custom_fields(sort_order);
CREATE INDEX IF NOT EXISTS idx_custom_fields_is_active ON custom_fields(is_active);
CREATE INDEX IF NOT EXISTS idx_custom_fields_created_by ON custom_fields(created_by);

CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_position_id
    ON position_custom_field_values(position_id);
CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_custom_field_id
    ON position_custom_field_values(custom_field_id);
CREATE INDEX IF NOT EXISTS idx_position_custom_field_values_composite
    ON position_custom_field_values(position_id, custom_field_id);

CREATE INDEX IF NOT EXISTS idx_custom_field_options_custom_field_id
    ON custom_field_options(custom_field_id);
CREATE INDEX IF NOT EXISTS idx_custom_field_options_sort_order
    ON custom_field_options(sort_order);
CREATE INDEX IF NOT EXISTS idx_custom_field_options_is_active
    ON custom_field_options(is_active);

COMMIT;