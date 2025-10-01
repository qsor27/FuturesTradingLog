# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-09-28-position-execution-integrity/spec.md

> Created: 2025-09-28
> Version: 1.0.0

## Schema Changes

### New Tables

#### position_execution_validation
```sql
CREATE TABLE position_execution_validation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    validation_type VARCHAR(50) NOT NULL,
    validation_status VARCHAR(20) NOT NULL CHECK (validation_status IN ('VALID', 'INVALID', 'PENDING', 'ERROR')),
    validation_result TEXT,
    validation_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
);
```

#### Enhanced position_executions table
```sql
-- Add integrity metadata columns to existing position_executions table
ALTER TABLE position_executions ADD COLUMN integrity_hash VARCHAR(64);
ALTER TABLE position_executions ADD COLUMN validation_status VARCHAR(20) DEFAULT 'PENDING' CHECK (validation_status IN ('VALID', 'INVALID', 'PENDING', 'ERROR'));
ALTER TABLE position_executions ADD COLUMN last_validated_at DATETIME;
ALTER TABLE position_executions ADD COLUMN validation_error_count INTEGER DEFAULT 0;
```

### New Columns

#### Position Model Enhancements
```sql
-- Add validation tracking fields to positions table
ALTER TABLE positions ADD COLUMN execution_integrity_status VARCHAR(20) DEFAULT 'UNCHECKED' CHECK (execution_integrity_status IN ('VALID', 'INVALID', 'PARTIAL', 'UNCHECKED', 'ERROR'));
ALTER TABLE positions ADD COLUMN last_integrity_check DATETIME;
ALTER TABLE positions ADD COLUMN execution_count INTEGER DEFAULT 0;
ALTER TABLE positions ADD COLUMN validated_execution_count INTEGER DEFAULT 0;
ALTER TABLE positions ADD COLUMN integrity_score DECIMAL(5,2) DEFAULT 0.0 CHECK (integrity_score >= 0.0 AND integrity_score <= 100.0);
```

### Modifications

#### Enhanced Foreign Key Constraints
```sql
-- Drop and recreate position_executions table with enhanced constraints
CREATE TABLE position_executions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    execution_time DATETIME NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20),
    commission DECIMAL(10,4) DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    integrity_hash VARCHAR(64),
    validation_status VARCHAR(20) DEFAULT 'PENDING' CHECK (validation_status IN ('VALID', 'INVALID', 'PENDING', 'ERROR')),
    last_validated_at DATETIME,
    validation_error_count INTEGER DEFAULT 0,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT unique_execution_per_position UNIQUE (position_id, execution_time, quantity, price)
);

-- Copy data from old table
INSERT INTO position_executions_new (id, position_id, execution_time, quantity, price, side, order_type, commission, created_at, updated_at)
SELECT id, position_id, execution_time, quantity, price, side, order_type, commission, created_at, updated_at
FROM position_executions;

-- Drop old table and rename new one
DROP TABLE position_executions;
ALTER TABLE position_executions_new RENAME TO position_executions;
```

#### New Indexes for Performance Optimization
```sql
-- Indexes for validation queries
CREATE INDEX idx_position_executions_validation_status ON position_executions(validation_status);
CREATE INDEX idx_position_executions_position_validation ON position_executions(position_id, validation_status);
CREATE INDEX idx_position_executions_last_validated ON position_executions(last_validated_at);

-- Indexes for position integrity tracking
CREATE INDEX idx_positions_integrity_status ON positions(execution_integrity_status);
CREATE INDEX idx_positions_last_integrity_check ON positions(last_integrity_check);
CREATE INDEX idx_positions_integrity_score ON positions(integrity_score);

-- Indexes for validation tracking table
CREATE INDEX idx_validation_position_id ON position_execution_validation(position_id);
CREATE INDEX idx_validation_status ON position_execution_validation(validation_status);
CREATE INDEX idx_validation_timestamp ON position_execution_validation(validation_timestamp);
CREATE INDEX idx_validation_type_status ON position_execution_validation(validation_type, validation_status);
```

#### Integrity Check Constraints
```sql
-- Add check constraints for data integrity
ALTER TABLE position_executions ADD CONSTRAINT chk_execution_quantity_positive CHECK (quantity > 0);
ALTER TABLE position_executions ADD CONSTRAINT chk_execution_price_positive CHECK (price > 0);
ALTER TABLE position_executions ADD CONSTRAINT chk_commission_non_negative CHECK (commission >= 0);

-- Add triggers for automatic integrity hash calculation
CREATE TRIGGER tr_position_executions_integrity_hash
AFTER INSERT ON position_executions
FOR EACH ROW
BEGIN
    UPDATE position_executions
    SET integrity_hash = hex(
        substr(
            lower(
                hex(
                    printf('%s|%s|%s|%s|%s',
                        NEW.position_id,
                        NEW.execution_time,
                        NEW.quantity,
                        NEW.price,
                        NEW.side
                    )
                )
            ), 1, 16
        )
    )
    WHERE id = NEW.id;
END;

-- Trigger to update position execution counts
CREATE TRIGGER tr_update_position_execution_count
AFTER INSERT ON position_executions
FOR EACH ROW
BEGIN
    UPDATE positions
    SET execution_count = (
        SELECT COUNT(*)
        FROM position_executions
        WHERE position_id = NEW.position_id
    ),
    validated_execution_count = (
        SELECT COUNT(*)
        FROM position_executions
        WHERE position_id = NEW.position_id AND validation_status = 'VALID'
    )
    WHERE id = NEW.position_id;
END;
```

## Migrations

### Migration Script: 001_add_position_execution_integrity.sql
```sql
-- Migration to add position-execution integrity validation support
-- Version: 1.0.0
-- Date: 2025-09-28

BEGIN TRANSACTION;

-- Step 1: Create position_execution_validation table
CREATE TABLE position_execution_validation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    validation_type VARCHAR(50) NOT NULL,
    validation_status VARCHAR(20) NOT NULL CHECK (validation_status IN ('VALID', 'INVALID', 'PENDING', 'ERROR')),
    validation_result TEXT,
    validation_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
);

-- Step 2: Add new columns to positions table
ALTER TABLE positions ADD COLUMN execution_integrity_status VARCHAR(20) DEFAULT 'UNCHECKED' CHECK (execution_integrity_status IN ('VALID', 'INVALID', 'PARTIAL', 'UNCHECKED', 'ERROR'));
ALTER TABLE positions ADD COLUMN last_integrity_check DATETIME;
ALTER TABLE positions ADD COLUMN execution_count INTEGER DEFAULT 0;
ALTER TABLE positions ADD COLUMN validated_execution_count INTEGER DEFAULT 0;
ALTER TABLE positions ADD COLUMN integrity_score DECIMAL(5,2) DEFAULT 0.0 CHECK (integrity_score >= 0.0 AND integrity_score <= 100.0);

-- Step 3: Backup and recreate position_executions table with integrity fields
CREATE TABLE position_executions_backup AS SELECT * FROM position_executions;

CREATE TABLE position_executions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    execution_time DATETIME NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20),
    commission DECIMAL(10,4) DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    integrity_hash VARCHAR(64),
    validation_status VARCHAR(20) DEFAULT 'PENDING' CHECK (validation_status IN ('VALID', 'INVALID', 'PENDING', 'ERROR')),
    last_validated_at DATETIME,
    validation_error_count INTEGER DEFAULT 0,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT unique_execution_per_position UNIQUE (position_id, execution_time, quantity, price),
    CONSTRAINT chk_execution_quantity_positive CHECK (quantity > 0),
    CONSTRAINT chk_execution_price_positive CHECK (price > 0),
    CONSTRAINT chk_commission_non_negative CHECK (commission >= 0)
);

-- Step 4: Migrate existing data
INSERT INTO position_executions_new (id, position_id, execution_time, quantity, price, side, order_type, commission, created_at, updated_at)
SELECT id, position_id, execution_time, quantity, price, side, order_type, commission, created_at, updated_at
FROM position_executions_backup;

-- Step 5: Replace old table
DROP TABLE position_executions;
ALTER TABLE position_executions_new RENAME TO position_executions;

-- Step 6: Create indexes
CREATE INDEX idx_position_executions_validation_status ON position_executions(validation_status);
CREATE INDEX idx_position_executions_position_validation ON position_executions(position_id, validation_status);
CREATE INDEX idx_position_executions_last_validated ON position_executions(last_validated_at);
CREATE INDEX idx_positions_integrity_status ON positions(execution_integrity_status);
CREATE INDEX idx_positions_last_integrity_check ON positions(last_integrity_check);
CREATE INDEX idx_positions_integrity_score ON positions(integrity_score);
CREATE INDEX idx_validation_position_id ON position_execution_validation(position_id);
CREATE INDEX idx_validation_status ON position_execution_validation(validation_status);
CREATE INDEX idx_validation_timestamp ON position_execution_validation(validation_timestamp);
CREATE INDEX idx_validation_type_status ON position_execution_validation(validation_type, validation_status);

-- Step 7: Create triggers
CREATE TRIGGER tr_position_executions_integrity_hash
AFTER INSERT ON position_executions
FOR EACH ROW
BEGIN
    UPDATE position_executions
    SET integrity_hash = hex(
        substr(
            lower(
                hex(
                    printf('%s|%s|%s|%s|%s',
                        NEW.position_id,
                        NEW.execution_time,
                        NEW.quantity,
                        NEW.price,
                        NEW.side
                    )
                )
            ), 1, 16
        )
    )
    WHERE id = NEW.id;
END;

CREATE TRIGGER tr_update_position_execution_count
AFTER INSERT ON position_executions
FOR EACH ROW
BEGIN
    UPDATE positions
    SET execution_count = (
        SELECT COUNT(*)
        FROM position_executions
        WHERE position_id = NEW.position_id
    ),
    validated_execution_count = (
        SELECT COUNT(*)
        FROM position_executions
        WHERE position_id = NEW.position_id AND validation_status = 'VALID'
    )
    WHERE id = NEW.position_id;
END;

-- Step 8: Initialize execution counts for existing positions
UPDATE positions
SET execution_count = (
    SELECT COUNT(*)
    FROM position_executions
    WHERE position_id = positions.id
);

-- Step 9: Generate integrity hashes for existing executions
UPDATE position_executions
SET integrity_hash = hex(
    substr(
        lower(
            hex(
                printf('%s|%s|%s|%s|%s',
                    position_id,
                    execution_time,
                    quantity,
                    price,
                    side
                )
            )
        ), 1, 16
    )
);

-- Step 10: Clean up backup table
DROP TABLE position_executions_backup;

COMMIT;
```

### Data Migration Requirements

1. **Existing Position Executions**: All existing position_executions records will be migrated with integrity_hash generation
2. **Position Counts**: execution_count fields will be populated for all existing positions
3. **Validation Status**: All migrated executions will start with 'PENDING' validation status
4. **Integrity Scores**: All positions will start with 0.0 integrity score until first validation run

### Performance Considerations

- Indexes are optimized for common validation queries
- Triggers automatically maintain data consistency
- Hash generation uses efficient SQLite functions
- Batch validation operations supported through indexed queries

### Rollback Plan

The migration includes a backup table creation that can be used for rollback if needed:
```sql
-- Rollback migration (if needed)
DROP TABLE position_executions;
ALTER TABLE position_executions_backup RENAME TO position_executions;
-- Remove added columns from positions table
-- (Note: SQLite doesn't support DROP COLUMN, so table recreation would be needed)
```