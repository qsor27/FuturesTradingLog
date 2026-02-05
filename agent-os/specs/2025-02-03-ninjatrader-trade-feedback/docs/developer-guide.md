# NinjaTrader Trade Feedback - Developer Guide

## Architecture Overview

The Trade Feedback feature spans three components:

1. **NinjaTrader AddOn** (C#): Chart UI and order blocking
2. **ExecutionExporter** (C#): CSV export with validation data
3. **FuturesTradingLog Backend** (Python): Import, aggregation, and API

```
┌─────────────────────────────────────────────────────────────┐
│                    NinjaTrader 8 (C#)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │ TradeFeedbackAddOn   │───>│  ExecutionExporter      │   │
│  │ - Chart Panel UI     │    │  - CSV Export           │   │
│  │ - Order Blocking     │    │  - TradeValidation Col  │   │
│  │ - Validation Tracker │    │  - Shared Dictionary    │   │
│  └──────────────────────┘    └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ CSV File
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              FuturesTradingLog (Python/Flask)               │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │ CSV Import Service   │───>│  Position Service       │   │
│  │ - Parse Validation   │    │  - Aggregate Status     │   │
│  │ - Insert Trades      │    │  - Rebuild Positions    │   │
│  └──────────────────────┘    └─────────────────────────┘   │
│                                        │                     │
│                                        ▼                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SQLite Database                         │   │
│  │  - trades.trade_validation                           │   │
│  │  - positions.validation_status                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                        │                     │
│                                        ▼                     │
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │ API Endpoints        │───>│  Frontend UI            │   │
│  │ - Filter by Status   │    │  - Validation Filters   │   │
│  │ - Update Validation  │    │  - Badge Components     │   │
│  │ - Statistics         │    │  - Statistics View      │   │
│  └──────────────────────┘    └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### trades Table Changes

**New Column**: `trade_validation`

```sql
ALTER TABLE trades ADD COLUMN trade_validation TEXT
  CHECK (trade_validation IS NULL OR trade_validation IN ('Valid', 'Invalid'));
```

- **Type**: TEXT
- **Nullable**: Yes
- **Constraint**: Must be NULL, 'Valid', or 'Invalid'
- **Purpose**: Store per-trade validation status from NinjaTrader

### positions Table Changes

**New Column**: `validation_status`

```sql
ALTER TABLE positions ADD COLUMN validation_status TEXT
  CHECK (validation_status IS NULL OR validation_status IN ('Valid', 'Invalid', 'Mixed'));

CREATE INDEX IF NOT EXISTS idx_positions_validation_status
  ON positions(validation_status);
```

- **Type**: TEXT
- **Nullable**: Yes
- **Constraint**: Must be NULL, 'Valid', 'Invalid', or 'Mixed'
- **Purpose**: Aggregated validation status for position
- **Index**: Created for efficient filtering queries

### Validation Status Aggregation Logic

```
All executions Valid -> Position Valid
All executions Invalid -> Position Invalid
Mix of Valid/Invalid -> Position Mixed
All NULL or no executions -> Position NULL
```

## CSV Format

### TradeValidation Column (Optional)

The ExecutionExporter adds an optional `TradeValidation` column to the CSV:

```csv
Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection,TradeValidation
MNQ 12-25,Buy,2,21500.00,10/31/2025 09:30:00 AM,exec_001,Entry,2 L,ord_001,Test,4.04,0,APEX123,SIM,Valid
MNQ 12-25,Sell,2,21510.00,10/31/2025 09:35:00 AM,exec_002,Exit,0,ord_002,Test,4.04,0,APEX123,SIM,Valid
```

**Column Position**: Last column (after Connection)

**Valid Values**:
- `Valid` - Trade followed rules
- `Invalid` - Trade violated rules
- Empty string - Not yet validated

**Backward Compatibility**: CSVs without TradeValidation column import normally with NULL validation status.

## API Endpoints

### GET /api/positions

**New Query Parameter**: `validation_status`

```http
GET /api/positions?validation_status=valid
GET /api/positions?validation_status=invalid
GET /api/positions?validation_status=mixed
GET /api/positions?validation_status=null
```

**Valid Values**:
- `valid` (case-insensitive)
- `invalid`
- `mixed`
- `null` (for unreviewed positions)

**Response**:
```json
{
  "success": true,
  "positions": [
    {
      "id": 123,
      "instrument": "MNQ",
      "validation_status": "Valid",
      ...
    }
  ]
}
```

**Error Responses**:
- `400 Bad Request` - Invalid validation_status value
- `500 Internal Server Error` - Database error

### PATCH /api/trades/:id

**Purpose**: Update trade validation status

**Request**:
```http
PATCH /api/trades/123
Content-Type: application/json

{
  "trade_validation": "Valid"
}
```

**Valid Values**:
- `"Valid"` (string)
- `"Invalid"` (string)
- `null` (clear validation)

**Response**:
```json
{
  "success": true,
  "trade": {
    "id": 123,
    "trade_validation": "Valid",
    ...
  }
}
```

**Side Effects**:
1. Updates `trades.trade_validation` in database
2. Triggers position rebuild for affected account/instrument
3. Recalculates `positions.validation_status`
4. Invalidates cache for account/instrument

**Error Responses**:
- `400 Bad Request` - Invalid trade_validation value
- `404 Not Found` - Trade ID doesn't exist
- `500 Internal Server Error` - Database error

### GET /api/statistics/by-validation

**Purpose**: Get performance metrics grouped by validation status

**Request**:
```http
GET /api/statistics/by-validation
```

**Response**:
```json
{
  "success": true,
  "statistics": {
    "Valid": {
      "total_trades": 45,
      "win_rate": 65.5,
      "avg_pnl": 125.50,
      "total_pnl": 5647.50
    },
    "Invalid": {
      "total_trades": 12,
      "win_rate": 33.3,
      "avg_pnl": -85.25,
      "total_pnl": -1023.00
    },
    "Mixed": {
      "total_trades": 5,
      "win_rate": 40.0,
      "avg_pnl": 45.20,
      "total_pnl": 226.00
    },
    "Unreviewed": {
      "total_trades": 23,
      "win_rate": 52.2,
      "avg_pnl": 98.75,
      "total_pnl": 2271.25
    }
  }
}
```

**Metrics**:
- `total_trades`: Count of positions in category
- `win_rate`: Percentage of winning positions (0-100)
- `avg_pnl`: Average P&L per position in dollars
- `total_pnl`: Total P&L for category in dollars

## Backend Services

### NinjaTraderImportService

**File**: `services/ninjatrader_import_service.py`

#### Changes

**REQUIRED_COLUMNS**: TradeValidation NOT included (optional column)

**_parse_csv Method**:
```python
def _parse_csv(self, csv_file):
    df = pd.read_csv(csv_file)

    # Check for optional TradeValidation column
    if 'TradeValidation' in df.columns:
        self.logger.info(f"TradeValidation column detected in {csv_file.name}")

    return df
```

**_insert_execution Method**:
```python
def _insert_execution(self, row, source_file, import_batch_id):
    trade_data = {
        # ... existing fields ...
        'trade_validation': row.get('TradeValidation', None) or None
    }

    # Map CSV values to database values
    if trade_data['trade_validation'] == '':
        trade_data['trade_validation'] = None

    if trade_data['trade_validation']:
        self.logger.info(f"Imported trade validation: {trade_data['trade_validation']}")

    # Insert into database
    cursor.execute("""
        INSERT INTO trades (..., trade_validation)
        VALUES (..., ?)
    """, (..., trade_data['trade_validation']))
```

### EnhancedPositionServiceV2

**File**: `services/enhanced_position_service_v2.py`

#### New Method: _aggregate_validation_status

```python
def _aggregate_validation_status(self, executions):
    """
    Aggregate validation status from execution list.

    Args:
        executions: List of execution dicts with 'trade_validation' key

    Returns:
        str: 'Valid', 'Invalid', 'Mixed', or None
    """
    if not executions:
        return None

    validations = [e.get('trade_validation') for e in executions]
    validations = [v for v in validations if v is not None]

    if not validations:
        return None

    unique_validations = set(validations)

    if unique_validations == {'Valid'}:
        return 'Valid'
    elif unique_validations == {'Invalid'}:
        return 'Invalid'
    elif 'Valid' in unique_validations and 'Invalid' in unique_validations:
        return 'Mixed'
    else:
        return None
```

#### Modified Method: rebuild_positions_for_account_instrument

```python
def rebuild_positions_for_account_instrument(self, account, instrument):
    # ... existing position building logic ...

    # After position created, aggregate validation status
    executions = self._get_executions_for_position(position_id)
    validation_status = self._aggregate_validation_status(executions)

    # Update position with validation_status
    cursor.execute("""
        UPDATE positions
        SET validation_status = ?
        WHERE id = ?
    """, (validation_status, position_id))

    self.logger.info(f"Position {position_id} validation_status: {validation_status}")

    # Invalidate cache
    self._invalidate_cache_for_account_instrument(account, instrument)
```

## NinjaTrader AddOn Development

### TradeFeedbackAddOn.cs

**Namespace**: `NinjaTrader.NinjaScript.AddOns`

**Key Components**:

#### PositionValidationTracker Class

```csharp
public class PositionValidationTracker
{
    private Dictionary<string, ValidationRecord> validations;
    private object lockObject = new object();

    public class ValidationRecord
    {
        public string PositionId { get; set; }
        public DateTime CloseTime { get; set; }
        public string Instrument { get; set; }
        public double PnL { get; set; }
        public string ValidationStatus { get; set; }
        public bool RequiresValidation { get; set; }
    }

    public void AddPosition(string positionId, ValidationRecord record)
    {
        lock (lockObject)
        {
            validations[positionId] = record;
        }
    }

    public void MarkValidated(string positionId, string status)
    {
        lock (lockObject)
        {
            if (validations.ContainsKey(positionId))
            {
                validations[positionId].ValidationStatus = status;
                validations[positionId].RequiresValidation = false;
            }
        }
    }

    public List<ValidationRecord> GetUnvalidated()
    {
        lock (lockObject)
        {
            return validations.Values
                .Where(v => v.RequiresValidation)
                .OrderByDescending(v => v.CloseTime)
                .ToList();
        }
    }
}
```

#### State Lifecycle

```csharp
protected override void OnStateChange()
{
    if (State == State.SetDefaults)
    {
        Name = "Trade Feedback AddOn";
        Description = "Track and validate trade quality";
    }
    else if (State == State.DataLoaded)
    {
        // Initialize validation tracker
        tracker = new PositionValidationTracker();

        // Load persisted state
        LoadPersistedState();

        // Subscribe to position updates
        foreach (Account account in Account.All)
        {
            account.PositionUpdate += OnPositionUpdate;
            account.OrderUpdate += OnOrderUpdate;
        }

        // Create chart panel UI
        CreateChartPanel();
    }
    else if (State == State.Terminated)
    {
        // Persist state to file
        PersistState();

        // Unsubscribe from events
        foreach (Account account in Account.All)
        {
            account.PositionUpdate -= OnPositionUpdate;
            account.OrderUpdate -= OnOrderUpdate;
        }

        // Cleanup UI
        CleanupChartPanel();
    }
}
```

#### Order Blocking Logic

```csharp
private void OnOrderUpdate(object sender, OrderEventArgs e)
{
    if (e.OrderState == OrderState.Submitted || e.OrderState == OrderState.Working)
    {
        // Check if order should be blocked
        if (settings.EnableOrderBlocking)
        {
            var unvalidated = tracker.GetUnvalidated();

            // Filter for same instrument
            var blocking = unvalidated
                .Where(v => v.Instrument == e.Order.Instrument.FullName)
                .ToList();

            if (blocking.Any())
            {
                // Check for emergency override (Ctrl+Shift held)
                if (!IsEmergencyOverride())
                {
                    // Cancel order
                    e.Order.Cancel();

                    // Show validation modal
                    ShowValidationModal(blocking);

                    Log($"Order blocked - validation required for {blocking.Count} positions", LogLevel.Information);
                }
                else
                {
                    Log("Emergency override used - order allowed", LogLevel.Warning);
                }
            }
        }
    }
}
```

### ExecutionExporter Integration

**Shared Dictionary**: Communication between AddOn and ExecutionExporter

```csharp
// In TradeFeedbackAddOn.cs
public static class SharedValidationData
{
    private static ConcurrentDictionary<string, string> validations
        = new ConcurrentDictionary<string, string>();

    public static void SetValidation(string positionId, string status)
    {
        validations[positionId] = status;
    }

    public static string GetValidation(string positionId)
    {
        return validations.TryGetValue(positionId, out string status)
            ? status
            : string.Empty;
    }
}
```

**In ExecutionExporter.cs**:

```csharp
private string FormatExecutionAsCSV(Execution execution)
{
    // ... existing fields ...

    // Add TradeValidation column
    string positionId = GetPositionId(execution);
    string validation = SharedValidationData.GetValidation(positionId);

    return $"{existingFields},{validation}";
}

private void WriteCSVHeader()
{
    writer.WriteLine("Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection,TradeValidation");
}
```

## Testing

### Test Structure

```
tests/
├── test_trade_validation_migration.py       # 8 tests - Database migration
├── test_csv_import_trade_validation.py      # 7 tests - CSV import
├── test_position_validation_aggregation.py  # 9 tests - Aggregation logic
├── test_validation_api_endpoints.py         # 13 tests - API endpoints
├── test_frontend_validation_ui.py           # 8 tests - Frontend UI
└── test_trade_feedback_integration.py       # 10 tests - End-to-end workflows
```

**Total**: 55 tests

### Running Tests

```bash
# Run all trade feedback tests
pytest tests/test_trade_validation_migration.py \
       tests/test_csv_import_trade_validation.py \
       tests/test_position_validation_aggregation.py \
       tests/test_validation_api_endpoints.py \
       tests/test_frontend_validation_ui.py \
       tests/test_trade_feedback_integration.py -v

# Run only integration tests
pytest tests/test_trade_feedback_integration.py -v

# Run with coverage
pytest tests/test_trade_feedback_integration.py --cov=services --cov=routes
```

### Integration Test Scenarios

1. **CSV Import to API Query**: End-to-end workflow from CSV import through position rebuild to API filtering
2. **Manual Validation Update**: PATCH API triggers position rebuild and cache invalidation
3. **Backward Compatibility**: Legacy CSVs without TradeValidation column import successfully
4. **Statistics Aggregation**: Statistics endpoint correctly groups by validation status
5. **Mixed Validation**: Positions with partial validation handled correctly
6. **Cache Invalidation**: Validation changes invalidate cached position data
7. **Multi-Account**: Validation isolated per account
8. **Index Performance**: Validation filter queries use database index
9. **Edge Cases**: Empty positions handle validation gracefully

## Migration

### Running Migration

```bash
# Apply migration
python scripts/migrations/migration_004_add_trade_validation_fields.py \
  --db-path data/db/trading_log.db

# Rollback migration
python scripts/migrations/migration_004_add_trade_validation_fields.py \
  --rollback --db-path data/db/trading_log.db
```

### Migration Script

**File**: `scripts/migrations/migration_004_add_trade_validation_fields.py`

**Key Features**:
- Idempotent (safe to re-run)
- Checks for existing columns before adding
- Creates index on validation_status
- Rollback uses SQLite table recreation pattern
- Preserves existing data

## Backward Compatibility

### Database

- New columns are **nullable** - existing data unaffected
- Positions without validation_status display as "Unreviewed"
- Queries without validation_status filter work unchanged

### CSV Import

- CSVs **without** TradeValidation column import normally
- TradeValidation column is **not required**
- Empty TradeValidation values treated as NULL
- Existing import logic unchanged

### API

- API endpoints work with NULL validation_status
- Filters handle NULL gracefully
- Statistics include "Unreviewed" category for NULL values

## Performance Considerations

### Database Index

Index on `positions.validation_status` improves filter query performance:

```sql
EXPLAIN QUERY PLAN SELECT * FROM positions WHERE validation_status = 'Valid';
-- Uses: idx_positions_validation_status
```

Expected improvement: 10-100x for large datasets (1000+ positions)

### Cache Invalidation

Validation changes trigger cache invalidation for affected account/instrument:

```python
self._invalidate_cache_for_account_instrument(account, instrument)
```

Ensures UI reflects updated validation without full cache flush.

### Position Rebuild

PATCH /api/trades/:id triggers position rebuild for affected account/instrument only, not all positions.

## Security Considerations

1. **Input Validation**: All API endpoints validate trade_validation values
2. **SQL Injection**: Parameterized queries used throughout
3. **Authorization**: API endpoints should add authentication (not implemented in v1.0)
4. **Audit Trail**: Order blocking and overrides logged to NinjaTrader output

## Future Enhancements

Potential features for future versions:

1. Bulk validation API endpoint
2. Validation notes/comments field
3. Validation categories beyond Valid/Invalid (e.g., "Partial", "Review")
4. Email/Discord notifications for unvalidated trades
5. Validation reminders after X hours
6. Historical validation trends chart
7. Validation-based P&L attribution
8. Multi-user validation workflows

## Debugging

### NinjaTrader

Check **Output** window for:
- Order blocking events
- Validation state changes
- CSV export logs
- AddOn errors

### FuturesTradingLog

Check logs in `data/logs/`:
- `app.log` - General application logs
- `flask.log` - API request logs

### Database

Verify schema:
```sql
PRAGMA table_info(trades);
PRAGMA table_info(positions);
SELECT * FROM sqlite_master WHERE type='index' AND name LIKE '%validation%';
```

Verify data:
```sql
SELECT trade_validation, COUNT(*) FROM trades GROUP BY trade_validation;
SELECT validation_status, COUNT(*) FROM positions GROUP BY validation_status;
```

## Code References

**Backend**:
- `services/ninjatrader_import_service.py` - CSV import
- `services/enhanced_position_service_v2.py` - Position aggregation
- `routes/positions.py` - API endpoints
- `scripts/migrations/migration_004_add_trade_validation_fields.py` - Migration

**NinjaTrader**:
- `ninjascript/TradeFeedbackAddOn.cs` - AddOn implementation
- `ninjascript/ExecutionExporter.cs` - CSV export with validation

**Tests**:
- `tests/test_trade_feedback_integration.py` - Integration tests
- `tests/test_validation_api_endpoints.py` - API tests
- `tests/test_position_validation_aggregation.py` - Aggregation tests

## Version Control

This feature was developed in spec: `agent-os/specs/2025-02-03-ninjatrader-trade-feedback/`

Key commits should reference spec and task group numbers for traceability.
