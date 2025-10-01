# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log main Flask application.
Bundles the Flask web server with all dependencies into a standalone executable.
"""

import sys
from pathlib import Path

block_cipher = None

# Application root directory
app_root = Path('..').resolve()

# Data files to include
datas = [
    (str(app_root / 'templates'), 'templates'),
    (str(app_root / 'static'), 'static'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'flask',
    'flask_cors',
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'redis',
    'celery',
    'pandas',
    'yfinance',
    'psutil',
    'schedule',
    'prometheus_client',
    'werkzeug',
    'jinja2',
    'click',
    'itsdangerous',
    'markupsafe',
    'pydantic',
    'pydantic_settings',
    'email_validator',
    'bcrypt',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'apscheduler',
    'tzlocal',
    'pytz',
]

a = Analysis(
    [str(app_root / 'app.py')],
    pathex=[str(app_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',  # Only exclude if not needed
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
    name='FuturesTradingLog',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False for production to hide console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_root / 'static' / 'favicon.ico') if (app_root / 'static' / 'favicon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FuturesTradingLog',
)
