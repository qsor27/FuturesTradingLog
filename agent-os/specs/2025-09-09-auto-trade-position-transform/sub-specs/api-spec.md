# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-09-auto-trade-position-transform/spec.md

> Created: 2025-09-09
> Version: 1.0.0

## Endpoints

### POST /upload

**Purpose:** Enhanced trade upload endpoint with automatic position building
**Parameters:** 
- file: CSV file containing trade data
- account_id: Target account identifier
- auto_build_positions: Boolean flag (default: true)
**Response:** JSON with upload status and position building task ID
**Errors:** 400 (invalid file), 500 (processing error), 422 (validation failed)

**Enhanced Behavior:** After successful trade import, automatically triggers position building task for the affected account/instrument combinations using existing Celery infrastructure.

### POST /trades

**Purpose:** Enhanced individual trade creation with automatic position updates
**Parameters:**
- trade_data: JSON object with trade details
- auto_update_positions: Boolean flag (default: true)
**Response:** JSON with created trade and position update status
**Errors:** 400 (invalid data), 409 (validation conflict), 500 (server error)

**Enhanced Behavior:** After trade creation, immediately updates positions for the affected account/instrument using synchronous position service calls.

### PUT /trades/{trade_id}

**Purpose:** Enhanced trade modification with automatic position recalculation
**Parameters:**
- trade_id: Trade identifier to modify
- trade_data: Updated trade information
- auto_update_positions: Boolean flag (default: true)
**Response:** JSON with updated trade and position recalculation status
**Errors:** 404 (not found), 400 (invalid data), 409 (validation conflict)

**Enhanced Behavior:** After trade modification, triggers incremental position rebuild for affected account/instrument combination to maintain data consistency.

### GET /positions/build-status/{task_id}

**Purpose:** Monitor automatic position building task progress
**Parameters:**
- task_id: Celery task identifier from upload/trade operations
**Response:** JSON with task status, progress, and completion details
**Errors:** 404 (task not found), 500 (task system error)

**New Endpoint:** Provides visibility into background position building triggered by automatic processes, allowing frontend to display build progress and completion status.

## Controllers

### Enhanced Upload Controller
**Actions:** 
- process_trade_file(): Extended to trigger automatic position building
- validate_and_queue_positions(): New method for queuing position updates
**Business Logic:** Maintains existing file validation while adding position building coordination
**Error Handling:** Preserves upload success even if position building encounters issues

### Enhanced Trade Controller  
**Actions:**
- create_trade(): Extended with immediate position update logic
- update_trade(): Enhanced with position recalculation triggers
- validate_position_impact(): New method for assessing position update requirements
**Business Logic:** Balances immediate user feedback with background processing efficiency
**Error Handling:** Ensures trade operations succeed independently of position building status

### New Position Build Status Controller
**Actions:**
- get_build_status(): Retrieve Celery task status and progress
- cancel_build_task(): Allow cancellation of long-running position builds
**Business Logic:** Provides transparency into automatic position building processes
**Error Handling:** Graceful handling of task system connectivity issues