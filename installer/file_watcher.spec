# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log File Watcher service.
Bundles the file watching service for NinjaTrader CSV auto-import.
"""

import sys
from pathlib import Path

block_cipher = None

# Application root directory
app_root = Path('..').resolve()

# Hidden imports for file watcher
hiddenimports = [
    'sqlalchemy',
    'redis',
    'pandas',
    'psutil',
    'schedule',
    'pathlib',
    'time',
    'logging',
    'os',
    'requests',
]

a = Analysis(
    [str(app_root / 'services' / 'background_services.py')],
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
    name='FileWatcher',
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
    name='FileWatcher',
)
