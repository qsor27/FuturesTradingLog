# Spec Summary (Lite)

Enhance the position builder to detect open positions by tracking running quantity balance (non-zero quantity = OPEN position) and deduplicate executions by `entry_execution_id` instead of timestamp/price. Update all documentation to comprehensively explain the quantity-based (0 → +/- → 0) position building methodology, including deduplication logic, position lifecycle, and FIFO P&L calculations.
