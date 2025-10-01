# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log Celery worker.
This creates a standalone executable for background task processing.
"""

import sys
from pathlib import Path

# Get the application root directory
root_dir = Path.cwd()

# Hidden imports for Celery worker
hidden_imports = [
    'celery',
    'celery.app',
    'celery.app.task',
    'celery.backends',
    'celery.backends.redis',
    'celery.worker',
    'redis',
    'kombu',
    'kombu.transport.redis',
    'billiard',
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'pandas',
    'numpy',
    'config',
    'config.config',
    'models',
    'services',
    'repositories',
    'tasks',
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
    ['celery_app.py'],
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
    name='FuturesTradingLog-Worker',
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
    name='FuturesTradingLog-Worker',
)
