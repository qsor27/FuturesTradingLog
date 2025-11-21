# Windows Native Installer - Lite Summary

Create a professional Windows installer that bundles Python runtime, Redis, and all dependencies into a single-click installation experience with Windows Service integration using NSSM, and provides complete uninstallation that cleanly removes all services, files, and registry entries.

## Key Points
- Single .exe installer packages entire application stack (Python 3.13.5, Redis, Flask app, all dependencies)
- Four Windows Services managed via NSSM for web app, Redis, Celery workers, and file watcher
- Complete uninstaller with service removal, file cleanup, and optional data preservation
