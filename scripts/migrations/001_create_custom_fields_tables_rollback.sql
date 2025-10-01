-- Rollback: 001_create_custom_fields_tables_rollback.sql
-- Description: Rollback custom fields tables creation
-- Date: 2025-09-29
-- Version: 1.0.0

BEGIN TRANSACTION;

-- Drop indexes first
DROP INDEX IF EXISTS idx_custom_field_options_is_active;
DROP INDEX IF EXISTS idx_custom_field_options_sort_order;
DROP INDEX IF EXISTS idx_custom_field_options_custom_field_id;

DROP INDEX IF EXISTS idx_position_custom_field_values_composite;
DROP INDEX IF EXISTS idx_position_custom_field_values_custom_field_id;
DROP INDEX IF EXISTS idx_position_custom_field_values_position_id;

DROP INDEX IF EXISTS idx_custom_fields_created_by;
DROP INDEX IF EXISTS idx_custom_fields_is_active;
DROP INDEX IF EXISTS idx_custom_fields_sort_order;
DROP INDEX IF EXISTS idx_custom_fields_name;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS custom_field_options;
DROP TABLE IF EXISTS position_custom_field_values;
DROP TABLE IF EXISTS custom_fields;

COMMIT;