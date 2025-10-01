# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-09-28-position-custom-fields/spec.md

> Created: 2025-09-28
> Version: 1.0.0

## Schema Changes

### New Tables

#### 1. custom_fields Table

```sql
CREATE TABLE custom_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    field_type VARCHAR(20) NOT NULL CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select')),
    display_label VARCHAR(150) NOT NULL,
    description TEXT,
    is_required BOOLEAN DEFAULT 0,
    default_value TEXT,
    validation_rules TEXT, -- JSON string for validation rules
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);
```

#### 2. position_custom_field_values Table

```sql
CREATE TABLE position_custom_field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    custom_field_id INTEGER NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields(id) ON DELETE CASCADE,
    UNIQUE(position_id, custom_field_id)
);
```

#### 3. custom_field_options Table (for select field types)

```sql
CREATE TABLE custom_field_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    custom_field_id INTEGER NOT NULL,
    option_value VARCHAR(255) NOT NULL,
    option_label VARCHAR(255) NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields(id) ON DELETE CASCADE
);
```

## Migrations

### Migration Script: Create Custom Fields Tables

```sql
-- Migration: 001_create_custom_fields_tables.sql
-- Description: Create tables for position custom fields functionality
-- Date: 2025-09-28

BEGIN TRANSACTION;

-- Create custom_fields table
CREATE TABLE IF NOT EXISTS custom_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    field_type VARCHAR(20) NOT NULL CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select')),
    display_label VARCHAR(150) NOT NULL,
    description TEXT,
    is_required BOOLEAN DEFAULT 0,
    default_value TEXT,
    validation_rules TEXT,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

-- Create position_custom_field_values table
CREATE TABLE IF NOT EXISTS position_custom_field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    custom_field_id INTEGER NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields(id) ON DELETE CASCADE,
    UNIQUE(position_id, custom_field_id)
);

-- Create custom_field_options table
CREATE TABLE IF NOT EXISTS custom_field_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    custom_field_id INTEGER NOT NULL,
    option_value VARCHAR(255) NOT NULL,
    option_label VARCHAR(255) NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (custom_field_id) REFERENCES custom_fields(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_custom_fields_name ON custom_fields(name);
CREATE INDEX IF NOT EXISTS idx_custom_fields_type ON custom_fields(field_type);
CREATE INDEX IF NOT EXISTS idx_custom_fields_active ON custom_fields(is_active);
CREATE INDEX IF NOT EXISTS idx_custom_fields_order ON custom_fields(display_order);

CREATE INDEX IF NOT EXISTS idx_position_custom_values_position ON position_custom_field_values(position_id);
CREATE INDEX IF NOT EXISTS idx_position_custom_values_field ON position_custom_field_values(custom_field_id);
CREATE INDEX IF NOT EXISTS idx_position_custom_values_composite ON position_custom_field_values(position_id, custom_field_id);

CREATE INDEX IF NOT EXISTS idx_custom_field_options_field ON custom_field_options(custom_field_id);
CREATE INDEX IF NOT EXISTS idx_custom_field_options_active ON custom_field_options(is_active);
CREATE INDEX IF NOT EXISTS idx_custom_field_options_order ON custom_field_options(display_order);

-- Insert default custom fields for common trading scenarios
INSERT INTO custom_fields (name, field_type, display_label, description, is_required, display_order, is_active) VALUES
('market_sentiment', 'select', 'Market Sentiment', 'Overall market sentiment at time of trade', 0, 1, 1),
('trade_confidence', 'number', 'Trade Confidence (1-10)', 'Confidence level in this trade setup', 0, 2, 1),
('risk_reward_ratio', 'number', 'Risk/Reward Ratio', 'Expected risk to reward ratio', 0, 3, 1),
('setup_type', 'select', 'Setup Type', 'Type of trading setup used', 0, 4, 1),
('market_session', 'select', 'Market Session', 'Trading session when position was opened', 0, 5, 1),
('news_impact', 'select', 'News Impact', 'Expected impact of news events', 0, 6, 1),
('position_notes', 'text', 'Position Notes', 'Additional notes about this position', 0, 7, 1);

-- Insert options for select fields
INSERT INTO custom_field_options (custom_field_id, option_value, option_label, display_order) VALUES
-- Market Sentiment options
(1, 'bullish', 'Bullish', 1),
(1, 'bearish', 'Bearish', 2),
(1, 'neutral', 'Neutral', 3),
(1, 'uncertain', 'Uncertain', 4),

-- Setup Type options
(4, 'breakout', 'Breakout', 1),
(4, 'pullback', 'Pullback', 2),
(4, 'reversal', 'Reversal', 3),
(4, 'continuation', 'Continuation', 4),
(4, 'scalp', 'Scalp', 5),
(4, 'swing', 'Swing', 6),

-- Market Session options
(5, 'pre_market', 'Pre-Market', 1),
(5, 'open', 'Market Open', 2),
(5, 'morning', 'Morning Session', 3),
(5, 'lunch', 'Lunch Time', 4),
(5, 'afternoon', 'Afternoon Session', 5),
(5, 'close', 'Market Close', 6),
(5, 'after_hours', 'After Hours', 7),

-- News Impact options
(6, 'high_positive', 'High Positive', 1),
(6, 'moderate_positive', 'Moderate Positive', 2),
(6, 'low_positive', 'Low Positive', 3),
(6, 'neutral', 'Neutral', 4),
(6, 'low_negative', 'Low Negative', 5),
(6, 'moderate_negative', 'Moderate Negative', 6),
(6, 'high_negative', 'High Negative', 7);

COMMIT;
```

### Rollback Script

```sql
-- Rollback: 001_create_custom_fields_tables_rollback.sql
-- Description: Rollback custom fields tables creation
-- Date: 2025-09-28

BEGIN TRANSACTION;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS custom_field_options;
DROP TABLE IF EXISTS position_custom_field_values;
DROP TABLE IF EXISTS custom_fields;

COMMIT;
```

## Indexes and Constraints

### Performance Indexes

```sql
-- Primary lookup indexes
CREATE INDEX idx_custom_fields_name ON custom_fields(name);
CREATE INDEX idx_custom_fields_type ON custom_fields(field_type);
CREATE INDEX idx_custom_fields_active ON custom_fields(is_active);
CREATE INDEX idx_custom_fields_order ON custom_fields(display_order);

-- Position value lookup indexes
CREATE INDEX idx_position_custom_values_position ON position_custom_field_values(position_id);
CREATE INDEX idx_position_custom_values_field ON position_custom_field_values(custom_field_id);
CREATE INDEX idx_position_custom_values_composite ON position_custom_field_values(position_id, custom_field_id);

-- Options lookup indexes
CREATE INDEX idx_custom_field_options_field ON custom_field_options(custom_field_id);
CREATE INDEX idx_custom_field_options_active ON custom_field_options(is_active);
CREATE INDEX idx_custom_field_options_order ON custom_field_options(display_order);
```

### Data Integrity Constraints

```sql
-- Field type validation
ALTER TABLE custom_fields ADD CONSTRAINT chk_field_type
CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select'));

-- Boolean constraints
ALTER TABLE custom_fields ADD CONSTRAINT chk_is_required
CHECK (is_required IN (0, 1));

ALTER TABLE custom_fields ADD CONSTRAINT chk_is_active
CHECK (is_active IN (0, 1));

ALTER TABLE custom_field_options ADD CONSTRAINT chk_option_is_active
CHECK (is_active IN (0, 1));

-- Ensure position and field combination is unique
ALTER TABLE position_custom_field_values ADD CONSTRAINT uk_position_field
UNIQUE (position_id, custom_field_id);
```

## Design Rationale

### 1. Table Structure Decisions

**custom_fields Table:**
- Uses `name` as a unique identifier for programmatic access
- Separate `display_label` for user-friendly presentation
- `field_type` enum constrains to supported types
- `validation_rules` stored as JSON for flexibility
- `display_order` enables custom field ordering
- Soft delete with `is_active` flag

**position_custom_field_values Table:**
- Generic `value` field stored as TEXT for flexibility
- Type casting handled at application level
- Unique constraint prevents duplicate field values per position
- CASCADE deletes maintain referential integrity

**custom_field_options Table:**
- Separate table for select field options
- Supports option ordering and soft deletes
- Normalized design for clean option management

### 2. Performance Considerations

**Indexing Strategy:**
- Composite index on (position_id, custom_field_id) for fast value lookups
- Individual indexes on frequently queried columns
- Order-based indexes for display sorting

**Query Optimization:**
- Single query to fetch all custom fields for a position
- Efficient filtering by field type and active status
- Optimized option loading for select fields

### 3. Scalability Decisions

**Storage Efficiency:**
- TEXT storage for all values with application-level typing
- Minimal overhead with optional field population
- Efficient NULL handling for unused fields

**Extensibility:**
- JSON validation rules support complex field requirements
- Field type system allows easy addition of new types
- Option system supports dynamic select field values

### 4. Data Integrity

**Referential Integrity:**
- Foreign key constraints with CASCADE deletes
- Unique constraints prevent data duplication
- Check constraints enforce valid field types

**Audit Trail:**
- Created/updated timestamps on all tables
- User tracking for field definitions
- Version control through updated_at timestamps

### 5. Migration Safety

**Incremental Deployment:**
- Self-contained migration with rollback script
- IF NOT EXISTS clauses prevent duplicate creation
- Transaction wrapper ensures atomic deployment
- Default data population for immediate usability