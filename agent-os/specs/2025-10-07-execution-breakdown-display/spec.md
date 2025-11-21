# Spec Requirements Document

> Spec: Execution Breakdown Display Fix
> Created: 2025-10-07
> Status: Planning

## Overview

The position detail page (http://localhost:5000/positions/{id}) has two display issues:

1. **Execution Breakdown Display**: The Execution Breakdown section is displaying empty table rows despite the execution data being correctly queried from the database. The position.executions data shows the correct execution_count (e.g., 7 executions for position ID 35), but the table body renders empty rows with only column headers visible.

2. **Redundant Position Metrics**: The position summary shows both "Total Quantity" and "Peak Position Size" which represent the same value in this context, creating visual redundancy and confusion.

This spec addresses both the data display issue and the UI cleanup to provide a clear, accurate position detail view.

## User Stories

**As a** trader reviewing my position history
**I want to** see the detailed execution breakdown for each position
**So that** I can understand the individual trades that comprise my position and verify execution quality

**As a** trader analyzing my trading performance
**I want to** view execution-level details including timestamps, prices, and quantities
**So that** I can identify patterns in my entry/exit timing and execution prices

**As a** system user troubleshooting position data
**I want to** confirmation that execution data is being retrieved and displayed correctly
**So that** I can trust the accuracy of position-level aggregations

**As a** trader viewing position metrics
**I want to** see only relevant, non-redundant position metrics in the summary
**So that** I can quickly understand the key position attributes without confusion

## Spec Scope

**Execution Breakdown Fix:**
- Debug and fix the execution breakdown table rendering in templates/positions/detail.html (lines 332-372)
- Verify the data structure returned from position_service.get_position_executions()
- Ensure the template iteration logic properly accesses execution attributes
- Test the fix with position ID 35 (known to have 7 executions)
- Validate that all execution fields display correctly: timestamp, action, quantity, price, commission
- Ensure execution data is properly passed from routes/positions.py:114 to the template

**Position Metrics Cleanup:**
- Remove "Total Quantity" metric from position summary section in templates/positions/detail.html (lines 207-210)
- Retain "Peak Position Size" as the single quantity metric (displayed only when max_quantity > total_quantity)
- Ensure remaining metrics layout adjusts properly after removal

## Out of Scope

- Modifying the underlying SQL query structure (already working)
- Changes to the position_executions table schema
- Adding new execution fields beyond what's currently queried
- Performance optimization of execution queries
- Execution data filtering or sorting features

## Expected Deliverable

A fully functional position detail page with:

**Execution Breakdown Section:**
1. Displays all executions associated with a position in a readable table format
2. Shows complete execution details: date/time, action (Buy/Sell), quantity, price, commission
3. Correctly iterates through the position.executions data structure
4. Renders consistent with the existing page design and layout
5. Works reliably across all positions with execution data

**Position Summary Section:**
1. Removes the redundant "Total Quantity" metric
2. Displays "Peak Position Size" only when relevant (max_quantity > total_quantity)
3. Maintains clean grid layout with remaining metrics

## Spec Documentation

- Tasks: @.agent-os/specs/2025-10-07-execution-breakdown-display/tasks.md
- Technical Specification: @.agent-os/specs/2025-10-07-execution-breakdown-display/sub-specs/technical-spec.md
