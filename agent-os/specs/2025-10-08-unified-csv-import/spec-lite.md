# Spec Summary (Lite)

Consolidate all CSV import methods into a single automatic background service that detects file format, processes CSV data, deduplicates, imports to database, rebuilds positions, and archives files without user intervention. Replace multiple confusing UI entry points (manual upload, NT executions processing, rebuild positions, re-import trades) with a unified CSV Manager dashboard showing status and providing a single "Process Now" trigger for manual processing.
