# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Futures Trading Log main Flask application.
This creates a standalone executable bundle with all dependencies.
"""

import sys
from pathlib import Path

# Get the application root directory
root_dir = Path.cwd()

# Hidden imports that PyInstaller might miss
hidden_imports = [
    'flask',
    'flask_cors',
    'werkzeug',
    'werkzeug.security',
    'jinja2',
    'jinja2.ext',
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'celery',
    'redis',
    'pandas',
    'numpy',
    'plotly',
    'plotly.graph_objs',
    'gunicorn',
    'config',
    'config.config',
    'config.settings_manager',
    'models',
    'routes',
    'services',
    'repositories',
    'middleware',
    'utils',
]

# Data files to include
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('.env.example', '.'),
]

# Binaries - exclude unnecessary libraries
excludes = [
    'tkinter',
    'matplotlib',
    'PIL',
    'PyQt5',
    'PyQt6',
]

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[str(root_dir)],
    binaries=[],
    datas=datas,
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
    name='FuturesTradingLog',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/images/icon.ico' if Path('static/images/icon.ico').exists() else None,
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
