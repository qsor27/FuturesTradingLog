# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log file watcher.
This creates a standalone executable for monitoring NinjaTrader CSV exports.
"""

import sys
from pathlib import Path

# Get the application root directory
root_dir = Path.cwd()

# Hidden imports for file watcher
hidden_imports = [
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'pandas',
    'numpy',
    'config',
    'config.config',
    'models',
    'services',
    'services.unified_csv_import_service',
    'repositories',
]

# Exclude unnecessary modules
excludes = [
    'tkinter',
    'matplotlib',
    'PIL',
    'PyQt5',
    'PyQt6',
]

block_cipher = None

a = Analysis(
    ['scripts/file_watcher.py'],
    pathex=[str(root_dir)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FuturesTradingLog-FileWatcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console window for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FuturesTradingLog-FileWatcher',
)
