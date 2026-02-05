# Specification: NinjaTrader Trade Feedback Integration

## Goal
Enable traders to mark trades as "Valid" or "Invalid" through a custom NinjaTrader AddOn with interactive chart-based UI and optional order blocking enforcement, automatically exporting feedback data to the FuturesTradingLog application for performance analysis and filtering based on trade quality.

## User Stories
- As a trader, I want to validate closed trades directly on my chart in NinjaTrader so that I can mark trade quality while the context is fresh without leaving my trading view
- As a trader, I want to be required to validate each stopped-out position before placing new orders so that I maintain disciplined post-trade review habits
- As a trader, I want my trade validation feedback to automatically sync to FuturesTradingLog so that I can analyze performance metrics filtered by trade quality without manual CSV editing

## Specific Requirements

**NinjaTrader AddOn Development**
- Create a custom NinjaTrader 8 AddOn using the NinjaTrader.NinjaScript.AddOns namespace for full UI customization capability
- AddOn should be separate from the existing ExecutionExporter indicator to maintain clean separation of concerns
- Use WPF for UI components leveraging NinjaTrader.Gui namespace (already imported in ExecutionExporter)
- AddOn lifecycle should initialize in OnStateChange State.DataLoaded and cleanup in State.Terminated
- Access closed positions via Account.Positions or by subscribing to Account.PositionUpdate events
- Filter for positions where MarketPosition.Flat (closed positions only)
- Store validation state in memory during session and export to CSV on-demand or at end-of-session
- Subscribe to Account.OrderUpdate events to detect stopped-out positions and track validation requirements

**Chart Panel UI - Right Margin Placement**
- Position validation panel in the right margin of the chart window, outside the chart grid but inside the chart control
- Panel should be vertically aligned and fixed to the right edge, similar to NinjaTrader drawing tools or indicator panels
- Panel remains fixed during chart scrolling and panning (does not move with price action)
- Display vertical stack of closed positions awaiting validation, with most recent at top
- Each position entry shows: instrument symbol, entry/exit times (compact HH:mm format), P&L with color coding (green for profit, red for loss)
- Each position entry has two side-by-side buttons: "✓ Valid" (green) and "✗ Invalid" (red)
- Panel auto-scrolls if more than 5-7 positions pending validation (compact scrollable list)
- Panel fades out or collapses to minimal width when no validation is needed
- Panel auto-shows when new position closes and requires validation

**Chart Panel Technical Implementation**
- Use WPF panel (StackPanel or Grid) attached to chart window's ChartControl
- Access chart window via ChartControl property and position panel using custom layout logic or DockPanel.Dock
- Panel should dock to right edge with fixed width (120-180px recommended for compact buttons)
- Ensure panel does not interfere with chart resize handles or scrollbar
- Style panel to match NinjaTrader's dark/light theme using NinjaTrader.Gui.Tools theme resources
- Semi-transparent background for panel container to maintain visual separation from chart
- Use TextBlock for position info and Button controls with Click event handlers for validation actions
- Panel toggleable via chart right-click menu option or keyboard shortcut (Ctrl+Shift+V)

**Order Blocking Until Validation**
- After a position is stopped out, prevent new orders from being placed until trader validates the closed position
- Maintain in-memory list of unvalidated position IDs that require validation before next trade
- Hook into Account.OrderUpdate or order submission pipeline to detect and intercept new order attempts
- When blocked order is attempted, show prominent modal or chart overlay alert explaining validation requirement
- Alert should include quick-access validation buttons to immediately validate and proceed with order
- Provide "Validate and Continue" workflow that allows trader to mark trade and submit pending order in one action
- Add user setting "Require Validation Before Next Trade" (default: enabled, toggleable in AddOn settings)
- Implement emergency override mechanism: hold Ctrl+Shift while placing order to bypass validation requirement for urgent scenarios
- Automated strategies should bypass validation requirement automatically (detect via Order.IsAutomated property or strategy name)
- Grace period option: allow X seconds after position close before blocking activates (configurable, default: 0 seconds)
- Clear validation requirement from list once position is marked Valid or Invalid

**Technical Feasibility: Order Interception**
- Use Account.OrderUpdate event to monitor all order submissions and position changes
- Check OnOrderUpdate event for OrderState.Working or OrderState.Submitted to detect new order attempts
- Maintain HashSet of unvalidated position IDs requiring validation before next trade
- When new order detected and unvalidated positions exist, attempt to cancel order using IOrder.Cancel() method
- Alternative approach: Override or hook into OnOrderUpdate before order reaches exchange (research if pre-submission hook exists)
- Track stopped-out positions by monitoring Position.MarketPosition changing to Flat with unrealized P&L going to zero
- Use Order.OrderAction (Buy/Sell) and Order.Instrument to match orders against validation requirements for same instrument
- Display validation enforcement modal using NinjaTrader.Gui.Tools.NTMessageBoxSimple or custom WPF window
- Modal should be blocking but dismissible with validation buttons directly in dialog
- Log all order blocking events to NinjaTrader output window for audit trail

**Validation State Tracking**
- Maintain dictionary mapping position IDs to validation status (Valid/Invalid/None) in AddOn memory
- Create PositionValidationTracker class to manage validation state with thread-safe operations
- Track position close timestamp, instrument, P&L, and validation requirement status
- On position close event, add position to tracker with "requires validation" flag if stop loss was hit
- Check tracker on every order submission: if unvalidated positions exist for that instrument, block order
- Clear position from "requires validation" list once marked Valid or Invalid
- Persist validation tracker state to temporary file on AddOn shutdown and reload on startup to survive restarts
- Include position identifier (entry time + instrument + account) to uniquely identify positions across sessions

**AddOn Configuration Settings**
- Add settings panel accessible via Tools > Options > NinjaTrader AddOns > Trade Feedback
- Setting: "Enable Order Blocking Until Validation" (checkbox, default: true)
- Setting: "Validation Grace Period" (numeric, 0-300 seconds, default: 0)
- Setting: "Auto-Show Panel on Position Close" (checkbox, default: true)
- Setting: "Bypass Validation for Automated Strategies" (checkbox, default: true)
- Setting: "Enable Emergency Override Shortcut" (checkbox, default: true)
- Setting: "Maximum Unvalidated Positions to Display" (numeric, 1-10, default: 5)
- Save settings to NinjaTrader XML settings infrastructure for persistence across sessions

**Data Export Integration with ExecutionExporter**
- Extend existing ExecutionExporter CSV format to add optional "TradeValidation" column after existing columns
- TradeValidation column values: "Valid", "Invalid", or empty for unvalidated trades
- Export validation data at position close time if validation already exists, otherwise export empty value
- AddOn should maintain in-memory mapping of position IDs to validation status (Valid/Invalid/None)
- When ExecutionExporter writes exit execution rows, check AddOn's validation mapping and include status in CSV
- Implement communication between AddOn and ExecutionExporter via shared static dictionary or NinjaTrader custom event
- Preserve backward compatibility - CSVs without TradeValidation column should import normally

**Database Schema Updates**
- Add "trade_validation" column to trades table: TEXT with CHECK constraint (NULL, 'Valid', 'Invalid')
- Add "validation_status" column to positions table: TEXT with CHECK constraint (NULL, 'Valid', 'Invalid', 'Mixed')
- Create database migration script using existing migration infrastructure in scripts/migrations/
- Add index on positions.validation_status for efficient filtering queries
- Ensure columns are nullable to support existing data and unvalidated new trades

**CSV Import Service Enhancement**
- Modify NinjaTraderImportService._parse_csv to handle optional TradeValidation column without breaking on missing column
- Update NinjaTraderImportService._insert_execution to map TradeValidation CSV value to trade_validation database field
- Add trade_data['trade_validation'] field with validation logic to handle empty/null/missing values
- Log INFO message when validation data is imported for each execution for audit trail
- Validation status should be preserved during incremental processing and Redis deduplication logic

**Position Validation Aggregation**
- After EnhancedPositionServiceV2 rebuilds positions from executions, aggregate validation status from all entry executions
- Logic: If all entry executions are Valid, position is Valid; if all Invalid, position is Invalid; if mixed, position is Mixed; if none, position is NULL
- Update EnhancedPositionServiceV2.rebuild_positions_for_account_instrument to calculate and store validation_status
- Add _aggregate_validation_status helper method to implement aggregation logic
- Validation_status should be recalculated each time positions are rebuilt from trades

**UI Filter and Display**
- Add validation status filter to positions view: dropdown with options [All, Valid, Invalid, Mixed, Unreviewed]
- Display validation badge in positions table row using existing badge component pattern
- Color coding: green badge for Valid, red for Invalid, yellow for Mixed, gray for Unreviewed
- Add validation status row to position detail view showing aggregated status
- Show individual execution validation in position executions breakdown table with per-execution badges
- Use existing frontend component patterns from custom fields or tags for consistency

**API Endpoints**
- Add validation_status query parameter to GET /api/positions: ?validation_status=valid|invalid|mixed|null
- Add PATCH /api/trades/:id endpoint with request body {"trade_validation": "Valid"|"Invalid"|null} for manual validation updates
- Add GET /api/statistics/by-validation endpoint returning performance metrics grouped by validation status (win rate, avg P&L, total trades per status)
- Ensure endpoints follow existing API patterns in routes/positions.py and routes/api.py
- Return appropriate HTTP status codes (200 OK, 400 Bad Request, 404 Not Found)

## Visual Design
No mockups provided. Chart panel should be positioned in the right margin of the chart window (outside chart grid, inside chart control) with vertical stacking of pending positions. Each position shows compact info (symbol, time, P&L) with side-by-side Valid/Invalid buttons. Panel uses semi-transparent background matching NinjaTrader theme. Follow existing FuturesTradingLog UI patterns for filters, badges, and status indicators in web application.

## Existing Code to Leverage

**C:\Projects\FuturesTradingLog\ninjascript\ExecutionExporter.cs**
- Existing indicator with NinjaTrader.Gui namespace imported (line 12) demonstrating NinjaTrader UI capability access
- Account.ExecutionUpdate event subscription pattern (lines 86-94) shows how to monitor account activity
- CSV file writing infrastructure with headers, data formatting, and file management (lines 472-680)
- Can be extended with new TradeValidation column in WriteCSVHeader and FormatExecutionAsCSV methods
- Existing deduplication tracking with HashSet<string> exportedExecutions pattern can inform validation state storage
- Logging infrastructure and error handling patterns to replicate in AddOn

**C:\Projects\FuturesTradingLog\services\ninjatrader_import_service.py**
- CSV parsing with pandas handling optional columns (lines 323-351)
- REQUIRED_COLUMNS list can be extended or made more flexible for optional columns (line 53-57)
- _insert_execution method (lines 1179-1307) maps CSV columns to database fields - extend with trade_validation mapping
- File validation logic in _validate_csv can be updated to allow TradeValidation as optional column
- Position rebuilding integration via _rebuild_positions_for_account_instrument (lines 678-712) shows where validation aggregation fits

**C:\Projects\FuturesTradingLog\services\enhanced_position_service_v2.py**
- rebuild_positions_for_account_instrument is the entry point for position rebuilding after execution import
- Position building logic aggregates executions into positions - add validation aggregation step here
- Database transaction patterns and error handling to follow for validation_status updates
- Cache invalidation pattern via _invalidate_cache_for_account_instrument to replicate for validation changes

**C:\Projects\FuturesTradingLog\models\custom_field.py**
- Pattern for adding optional user-defined fields to positions with validation and type safety
- CustomFieldType enum shows how to define constrained value sets (similar to Valid/Invalid/Mixed)
- Pydantic model patterns for type validation to apply to validation status API request/response models
- Storage and retrieval patterns for optional position metadata

**C:\Projects\FuturesTradingLog\scripts\database_manager.py and migrations**
- Migration script infrastructure in scripts/migrations/ directory with versioning and rollback
- Schema update patterns for adding new columns with ALTER TABLE and indexes
- SQLite-specific syntax and pragma optimizations to follow
- Migration testing patterns and rollback procedures

## Risks and Considerations

**Order Blocking Disrupting Trading Flow**
- Risk: Mandatory validation could slow down fast-paced trading or frustrate traders during volatile markets
- Mitigation: Make blocking optional via settings, provide emergency override shortcut, allow grace period configuration
- Mitigation: Ensure validation UI is fast and accessible (one-click from chart panel or modal)
- Consideration: Some traders may disable blocking entirely and rely on voluntary validation

**Emergency Trading Scenarios**
- Risk: Trader needs to quickly hedge or exit position but is blocked by validation requirement
- Mitigation: Implement Ctrl+Shift override bypass for urgent situations
- Mitigation: Consider "Validate Later + Emergency Trade" button that acknowledges need and permits order
- Consideration: Log all override usage to track if feature is being abused or causing friction

**Automated Strategy Interference**
- Risk: Automated strategies could be blocked if validation logic doesn't detect automation correctly
- Mitigation: Check Order.IsAutomated property and strategy name to bypass validation for automated orders
- Mitigation: Add explicit setting to disable blocking for automated strategies (default: enabled bypass)
- Testing: Verify automated strategies continue to function normally with AddOn enabled

**Position Identification Across Sessions**
- Risk: Position IDs may not persist correctly across NinjaTrader restarts, causing validation requirements to be lost
- Mitigation: Use composite key (entry time + instrument + account) for position identification
- Mitigation: Persist validation tracker state to file on shutdown and reload on startup
- Consideration: Define clear retention policy (e.g., clear validation requirements older than 24 hours)

**Order Cancellation Timing**
- Risk: Order may reach exchange before AddOn can cancel it, resulting in unwanted fill
- Mitigation: Hook into earliest possible order event (OnOrderUpdate with OrderState.Submitted)
- Mitigation: Test cancellation timing extensively in simulation mode before live trading
- Fallback: If order cannot be cancelled, show post-fill alert and add position to validation queue
- Consideration: Document that blocking is "best effort" and not guaranteed for all order types

**User Experience and Adoption**
- Risk: Feature feels too restrictive or "nanny-like" and traders disable it immediately
- Mitigation: Make feature optional and clearly communicate benefits in documentation
- Mitigation: Provide graduated enforcement options (alert only, optional blocking, required blocking)
- Mitigation: Ensure validation UI is fast, intuitive, and doesn't require leaving chart context
- Consideration: Add analytics to track feature usage and validation compliance rates over time

## Out of Scope
- Standalone validation window separate from chart (Option A) - using chart panel overlay exclusively (Option B)
- Context menu integration for validation (Option C) - chart panel is primary interface
- Real-time validation prompts during trade execution before exit (validation happens after position close)
- Automated validation assignment based on trade rules or AI analysis (all validation must be manual trader input)
- Bulk validation tools for historical trades in NinjaTrader (use FuturesTradingLog UI for historical updates via PATCH endpoint)
- Integration with NinjaTrader Strategy Analyzer or backtesting results
- Mobile app or standalone web interface for validation entry (NinjaTrader AddOn only)
- Multi-user validation workflows or validation approval chains
- Email/Discord notifications when trades lack validation status
- Scheduled validation reminder alerts or nag screens in NinjaTrader
- Export validation data to formats other than CSV (no JSON/XML export from AddOn)
- Order blocking based on daily loss limits or other trading rules (blocking only for validation enforcement)
- Validation requirement for profitable trades (blocking only applies to stopped-out positions, configurable)
