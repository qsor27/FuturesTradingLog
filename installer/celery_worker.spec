# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log Celery worker.
Bundles the Celery background worker into a standalone executable.
"""

import sys
from pathlib import Path

block_cipher = None

# Application root directory
app_root = Path('..').resolve()

# Hidden imports for Celery
hiddenimports = [
    'celery',
    'celery.app',
    'celery.worker',
    'celery.bin',
    'celery.bin.worker',
    'celery.loaders',
    'celery.backends',
    'celery.backends.redis',
    'kombu',
    'kombu.transport.redis',
    'redis',
    'sqlalchemy',
    'pandas',
    'yfinance',
    'psutil',
    'schedule',
    'requests',
    'urllib3',
    'certifi',
]

a = Analysis(
    [str(app_root / 'celery_app.py')],
    pathex=[str(app_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
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
    name='CeleryWorker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='CeleryWorker',
)
