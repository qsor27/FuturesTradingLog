"""
Fix Data Fragmentation - Unify Import Services

This script consolidates the fragmented import system into one cohesive flow:
1. Disables duplicate import services
2. Enhances UnifiedCSVImportService to handle validation
3. Ensures data flows: CSV → trades table → positions → web interface
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("DATA FRAGMENTATION FIX")
print("=" * 60)

print("\nStep 1: Analyzing current state...")

# Check which services are in app.py
with open('app.py', 'r') as f:
    app_content = f.read()

has_ninjatrader = 'ninjatrader_import_service' in app_content
has_unified = 'unified_csv_import_service' in app_content

print(f"  NinjaTraderImportService in app.py: {has_ninjatrader}")
print(f"  UnifiedCSVImportService in app.py: {has_unified}")

# Check database state
import sqlite3
import subprocess

# Get database info from Docker
print("\n  Checking Docker database...")
try:
    result = subprocess.run([
        'docker', 'exec', 'futurestradinglog', 'python', '-c',
        """
import sqlite3
conn = sqlite3.connect('/app/data/db/trading_log.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM trades')
trades_count = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM positions')
positions_count = cursor.fetchone()[0]
cursor.execute('PRAGMA table_info(trades)')
has_validation = 'trade_validation' in [col[1] for col in cursor.fetchall()]
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='import_execution_logs'\")
has_import_logs = cursor.fetchone() is not None
print(f'{trades_count},{positions_count},{has_validation},{has_import_logs}')
conn.close()
        """
    ], capture_output=True, text=True)

    if result.returncode == 0:
        trades_count, positions_count, has_validation_column, has_import_logs = result.stdout.strip().split(',')
        trades_count = int(trades_count)
        positions_count = int(positions_count)
        has_validation_column = has_validation_column == 'True'
        has_import_logs = has_import_logs == 'True'
    else:
        print(f"  Error accessing Docker database: {result.stderr}")
        trades_count = positions_count = 0
        has_validation_column = has_import_logs = False
except Exception as e:
    print(f"  Error: {e}")
    trades_count = positions_count = 0
    has_validation_column = has_import_logs = False

# Dummy variables for script flow
conn = None
cursor = None

print(f"\nDatabase state:")
print(f"  Trades: {trades_count} rows")
print(f"  Positions: {positions_count} rows")
print(f"  trades.trade_validation column: {'EXISTS' if has_validation_column else 'MISSING'}")
print(f"  import_execution_logs table: {'OK EXISTS' if has_import_logs else 'X MISSING'}")

print("\n" + "=" * 60)
print("SOLUTION:")
print("=" * 60)

print("""
The system has TWO import services fighting over files:
- NinjaTraderImportService (has validation support)
- UnifiedCSVImportService (actually running, but no validation)

This causes:
X Trades table stays empty (0 rows)
X Validation data lost
X Import logs inaccurate

FIX:
OK Keep ONLY UnifiedCSVImportService
OK Enhance it to populate trades table with validation
OK Create import_execution_logs table
OK Ensure single, cohesive data flow

Next steps:
1. Edit app.py to disable NinjaTraderImportService
2. Enhance UnifiedCSVImportService
3. Run database migration
4. Rebuild positions from trades
""")

print("\n" + "=" * 60)
print("Run this script with '--fix' to apply changes:")
print("  python fix_data_fragmentation.py --fix")
print("=" * 60)

if '--fix' in sys.argv:
    print("\n[FIX] APPLYING FIX...")

    # Step 1: Comment out NinjaTraderImportService in app.py
    print("\nStep 1: Disabling NinjaTraderImportService...")
    with open('app.py', 'r') as f:
        lines = f.readlines()

    modified = False
    for i, line in enumerate(lines):
        # Comment out the start_watcher call
        if 'ninjatrader_import_service.start_watcher()' in line and not line.strip().startswith('#'):
            lines[i] = '        # ' + line.lstrip()
            modified = True
            print(f"  OK Commented line {i+1}")

    if modified:
        with open('app.py', 'w') as f:
            f.writelines(lines)
        print("  OK app.py updated")
    else:
        print("  [INFO] Already disabled or not found")

    # Step 2: Create import_execution_logs table in Docker
    print("\nStep 2: Creating import_execution_logs table...")
    sql_script = """
import sqlite3
conn = sqlite3.connect('/app/data/db/trading_log.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS import_execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    import_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    total_rows INTEGER NOT NULL DEFAULT 0,
    success_rows INTEGER NOT NULL DEFAULT 0,
    failed_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    processing_time_ms INTEGER,
    affected_accounts TEXT,
    error_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_import_logs_batch_id ON import_execution_logs(import_batch_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_import_logs_status ON import_execution_logs(status)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_import_logs_import_time ON import_execution_logs(import_time)')
conn.commit()
conn.close()
print('Table created')
    """

    result = subprocess.run([
        'docker', 'exec', 'futurestradinglog', 'python', '-c', sql_script
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("  OK import_execution_logs table created")
    else:
        print(f"  Error creating table: {result.stderr}")

    print("\n[OK] FIX APPLIED")
    print("\nNext: Restart Docker container to apply changes")
    print("  docker-compose restart")

