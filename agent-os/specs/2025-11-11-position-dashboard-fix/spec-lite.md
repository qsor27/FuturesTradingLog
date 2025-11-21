# Spec Summary (Lite)

Fix critical position building algorithm failures and dashboard calculation errors causing incorrect P&L calculations (showing negative $154M), missing execution prices (0.00 values), and contradictory position states (Open positions with exit times). Restore data integrity by fixing the quantity flow analyzer, P&L calculation engine, and dashboard statistics aggregation. Provide database cleanup utility to delete all broken data and enable clean re-import after fixes are applied.
