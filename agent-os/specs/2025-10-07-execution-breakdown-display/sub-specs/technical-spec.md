# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-10-07-execution-breakdown-display/spec.md

> Created: 2025-10-07
> Version: 1.0.0

## Technical Requirements

### 1. Execution Breakdown Display Fix

### Data Flow Analysis

1. **Backend Data Retrieval** (routes/positions.py:114)
   - Calls `pos_service.get_position_executions(position_id)`
   - Adds result to `position['executions']` dictionary key
   - Must verify: data type returned (list vs dict), structure of each execution object

2. **Service Layer** (position_service.py)
   - Method: `get_position_executions()`
   - Queries: position_executions table JOIN trades table
   - Returns: execution records with fields needed by template
   - Must verify: column names, data serialization, NULL handling

3. **Template Rendering** (templates/positions/detail.html:332-372)
   - Iterates: `{% for execution in position.executions %}`
   - Accesses: execution.timestamp, execution.action, execution.quantity, execution.price, execution.commission
   - Must verify: attribute access pattern (dict vs object), Jinja2 context availability

### Debugging Steps

1. **Verify Data Structure**
   ```python
   # In routes/positions.py after line 114
   executions = pos_service.get_position_executions(position_id)
   print(f"DEBUG: Executions type: {type(executions)}")
   print(f"DEBUG: Executions content: {executions}")
   print(f"DEBUG: First execution: {executions[0] if executions else 'EMPTY'}")
   ```

2. **Check Service Return Format**
   - Inspect `get_position_executions()` return statement
   - Verify if returning list of dicts vs list of Row objects
   - Check if column names match template expectations

3. **Template Data Access**
   - Add debug output in template: `{{ position.executions|length }}`
   - Test attribute access: `{{ position.executions[0].timestamp if position.executions }}`
   - Verify iteration: `{% for exec in position.executions %}{{ loop.index }}{% endfor %}`

### Likely Root Causes

**Hypothesis 1: Dictionary Key Access**
- Template expects: `execution.timestamp`
- Data provides: `execution['timestamp']` (dict access)
- Fix: Convert to object notation or use dict access in template

**Hypothesis 2: Empty List Assignment**
- Service returns data but route assigns empty list/dict
- Fix: Verify position['executions'] = executions line executes correctly

**Hypothesis 3: Jinja2 Context Issue**
- Executions not properly passed to template context
- Fix: Ensure render_template includes position dict with executions key

**Hypothesis 4: SQL Column Naming**
- Query uses aliases that don't match template expectations
- Fix: Add explicit column aliases in SQL query

## Approach

### Phase 1: Diagnostic Logging
1. Add print statements to routes/positions.py before template render
2. Log execution count, type, and sample data
3. Add template debug output to verify data received
4. Test with position ID 35

### Phase 2: Data Structure Fix
1. Based on diagnostic output, identify mismatch
2. Options:
   - **Option A**: Convert Row objects to dicts in service layer
   - **Option B**: Update template to use dict-style access
   - **Option C**: Use SQLAlchemy model objects for proper attribute access
3. Implement chosen solution
4. Test rendering with multiple positions

### Phase 3: Validation
1. Verify all execution fields display correctly
2. Test with positions having varying execution counts (1, 7, 20+)
3. Check edge cases: positions with no executions, NULL commission values
4. Validate formatting: dates, currency, decimal precision

### Code Changes Required

**File: position_service.py** (get_position_executions method)
```python
# Ensure return format supports attribute access
# Example fix:
def get_position_executions(self, position_id):
    query = """
        SELECT
            pe.timestamp,
            pe.action,
            pe.quantity,
            pe.price,
            pe.commission
        FROM position_executions pe
        JOIN trades t ON pe.trade_id = t.id
        WHERE pe.position_id = ?
        ORDER BY pe.timestamp
    """
    rows = db.execute(query, (position_id,)).fetchall()

    # Convert Row objects to dicts for template compatibility
    return [dict(row) for row in rows]
```

**File: templates/positions/detail.html** (lines 332-372)
```html
<!-- Ensure proper dict access if needed -->
{% for execution in position.executions %}
<tr>
    <td>{{ execution['timestamp'] or execution.timestamp }}</td>
    <td>{{ execution['action'] or execution.action }}</td>
    <td>{{ execution['quantity'] or execution.quantity }}</td>
    <td>${{ execution['price'] or execution.price }}</td>
    <td>${{ execution['commission'] or execution.commission or 0 }}</td>
</tr>
{% endfor %}
```

## External Dependencies

- **Flask/Jinja2**: Template rendering engine behavior with dict vs object access
- **SQLite**: Row object format from database queries
- **Existing Database Schema**: position_executions and trades tables must have expected columns

### Testing Data
- Position ID 35: Known to have 7 executions
- Use this as primary test case for validation
- Verify execution_count matches rendered row count

---

### 2. Position Metrics Cleanup

#### Current Implementation

**File: templates/positions/detail.html (lines 207-254)**

The position summary currently displays:
- Total Quantity (lines 207-210)
- Average Entry Price (lines 212-215)
- Average Exit Price (lines 217-222, conditional)
- Points P&L (lines 224-229)
- Gross P&L (lines 231-236)
- Commission (lines 238-241)
- Net P&L (lines 243-248)
- Total Executions (lines 250-253)
- Peak Position Size (lines 273-278, conditional when max_quantity > total_quantity)

#### Problem Analysis

"Total Quantity" and "Peak Position Size" represent the same metric in most cases:
- `total_quantity`: The position size in contracts
- `max_quantity`: The maximum position size reached (only different during scaling)

For positions without scaling (most cases), these values are identical, creating visual redundancy.

#### Solution

Remove the "Total Quantity" metric card entirely:

**Change in templates/positions/detail.html:**
```html
<!-- DELETE lines 207-210 -->
<div class="summary-card">
    <div class="summary-label">Total Quantity</div>
    <div class="summary-value">{{ position.total_quantity }} contracts</div>
</div>
```

Keep "Peak Position Size" display in the Additional Metrics section (lines 273-278):
```html
{% if position.max_quantity > position.total_quantity %}
<div class="summary-card">
    <div class="summary-label">Peak Position Size</div>
    <div class="summary-value">{{ position.max_quantity }} contracts</div>
</div>
{% endif %}
```

#### Impact Analysis

- **Grid Layout**: CSS grid with `grid-template-columns: repeat(auto-fit, minmax(250px, 1fr))` will automatically adjust to 7 metrics instead of 8
- **Visual Balance**: Cleaner metric display without redundant information
- **Backward Compatibility**: No backend changes required, template-only modification
- **User Experience**: Eliminates confusion between total_quantity and max_quantity

#### Testing Requirements

1. View positions with `max_quantity == total_quantity` (no scaling)
   - Should show 7 main metrics, no Peak Position Size
2. View positions with `max_quantity > total_quantity` (scaled positions)
   - Should show 7 main metrics + Peak Position Size in additional section
3. Verify grid layout maintains proper spacing and alignment
