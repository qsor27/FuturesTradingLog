# Spec Tasks

These are the tasks to be completed for the spec detailed in @.agent-os/specs/2025-09-30-windows-native-installer/spec.md

> Created: 2025-09-30
> Status: Ready for Implementation

## Tasks

### Phase 1: Development Environment Setup

- [ ] **Task 1.1**: Install PyInstaller 6.0+ in development environment
  - Install via pip: `pip install pyinstaller`
  - Verify installation: `pyinstaller --version`

- [ ] **Task 1.2**: Install Inno Setup 6.0+ for Windows
  - Download from https://jrsoftware.org/isdl.php
  - Install to default location: `C:\Program Files (x86)\Inno Setup 6\`
  - Verify ISCC.exe is available

- [ ] **Task 1.3**: Download Redis for Windows binaries
  - Download Redis 5.0.14+ for Windows (Microsoft fork or Memurai)
  - Extract to `vendor/redis/` directory
  - Verify redis-server.exe and redis-cli.exe are present
  - Test Redis startup locally

- [ ] **Task 1.4**: Download NSSM (Non-Sucking Service Manager)
  - Download NSSM 2.24+ from https://nssm.cc/download
  - Extract x64 binaries to `vendor/nssm/win64/`
  - Verify nssm.exe is present

- [ ] **Task 1.5**: Create application icon file
  - Design or source icon image
  - Convert to .ico format (256x256, 128x128, 64x64, 32x32, 16x16)
  - Save as `static/images/icon.ico`

### Phase 2: PyInstaller Configuration

- [ ] **Task 2.1**: Create PyInstaller spec file for main Flask application
  - Create `FuturesTradingLog.spec` with all hidden imports
  - Include templates and static directories
  - Configure --onedir mode with --windowed flag
  - Add application icon
  - Test build: `pyinstaller FuturesTradingLog.spec`

- [ ] **Task 2.2**: Create PyInstaller spec file for Celery worker
  - Create `FuturesTradingLog-Worker.spec`
  - Configure console mode for logging
  - Include Celery and Redis dependencies
  - Test build and verify worker starts correctly

- [ ] **Task 2.3**: Create PyInstaller spec file for file watcher
  - Create `FuturesTradingLog-FileWatcher.spec`
  - Include watchdog library and dependencies
  - Test build and verify file monitoring works

- [ ] **Task 2.4**: Optimize PyInstaller builds
  - Identify and exclude unnecessary modules (tkinter, matplotlib)
  - Configure UPX compression if needed
  - Verify bundle size is under 200MB
  - Test all executables run independently

- [ ] **Task 2.5**: Create file watcher entry point script
  - Create `scripts/file_watcher.py` if not exists
  - Implement standalone execution mode
  - Add proper error handling and logging
  - Test as executable

### Phase 3: Inno Setup Script Development

- [ ] **Task 3.1**: Create base Inno Setup script structure
  - Create `installer.iss` with setup metadata
  - Configure output directory and compression
  - Add license file reference
  - Set installation defaults (Program Files)

- [ ] **Task 3.2**: Configure file deployment in installer
  - Add [Files] section with all executables
  - Include Redis binaries and configuration
  - Include NSSM executable
  - Add configuration templates

- [ ] **Task 3.3**: Configure directory creation
  - Add [Dirs] section for ProgramData structure
  - Set proper permissions (users-modify for data directories)
  - Create logs, db, charts, archive, config subdirectories

- [ ] **Task 3.4**: Implement service installation in [Run] section
  - Add NSSM install commands for all four services
  - Configure service dependencies (Web depends on Redis, etc.)
  - Set service startup mode (AUTO_START)
  - Configure service environment variables
  - Add service logging configuration

- [ ] **Task 3.5**: Create Start Menu and Desktop shortcuts
  - Add [Icons] section with web application URL shortcut
  - Create helper shortcuts (Start Services, Stop Services, View Logs)
  - Configure optional desktop icon

- [ ] **Task 3.6**: Implement uninstaller service removal
  - Add [UninstallRun] section
  - Stop services in reverse dependency order
  - Remove services using NSSM
  - Add timeout handling

- [ ] **Task 3.7**: Implement data preservation prompt
  - Add [Code] section with Pascal script
  - Create CurUninstallStepChanged procedure
  - Prompt user to keep or delete ProgramData
  - Implement conditional deletion logic

### Phase 4: Redis and Service Configuration

- [ ] **Task 4.1**: Create Redis configuration file template
  - Create `vendor/redis/redis.conf`
  - Configure localhost binding and port 6379
  - Set persistence options (RDB snapshots)
  - Configure logging and memory limits
  - Use placeholder paths for dynamic substitution

- [ ] **Task 4.2**: Implement Redis configuration path replacement
  - Add installer script logic to update redis.conf paths
  - Replace {COMMONAPPDATA} with actual path
  - Ensure Redis data directory exists

- [ ] **Task 4.3**: Create helper batch scripts
  - Create `start-services.bat` for manual service startup
  - Create `stop-services.bat` for manual service shutdown
  - Add to installer bin directory

- [ ] **Task 4.4**: Configure environment variable template
  - Create comprehensive `.env.example` file
  - Document all configuration options
  - Set production-appropriate defaults
  - Include path configuration for ProgramData locations

### Phase 5: Build Automation

- [ ] **Task 5.1**: Create main build automation script
  - Create `build_installer.py` in project root
  - Implement clean_build() function
  - Implement build_executables() function
  - Implement download_dependencies() check function
  - Implement create_helper_scripts() function
  - Implement build_installer() function

- [ ] **Task 5.2**: Add version management
  - Create VERSION file or use setup.py for version
  - Update Inno Setup script to use version variable
  - Ensure version appears in installer filename

- [ ] **Task 5.3**: Create vendor dependency validation
  - Check for Redis binaries presence
  - Check for NSSM presence
  - Provide clear error messages if missing
  - Add download instructions

- [ ] **Task 5.4**: Integrate Inno Setup compilation
  - Locate ISCC.exe programmatically
  - Execute Inno Setup compilation from Python
  - Capture and display build output
  - Handle compilation errors

### Phase 6: Testing and Validation

- [ ] **Task 6.1**: Create installer testing script
  - Create `scripts/test_installer.py`
  - Implement test_services_running() function
  - Implement test_web_application() function
  - Implement test_redis_connection() function
  - Add 30-second startup delay

- [ ] **Task 6.2**: Test installation on clean Windows 10 VM
  - Provision clean Windows 10 VM
  - Run installer as administrator
  - Verify all services are created and started
  - Test web application accessibility at http://localhost:5555
  - Check all log files are created

- [ ] **Task 6.3**: Test installation on Windows 11 VM
  - Provision clean Windows 11 VM
  - Run installer and verify functionality
  - Check compatibility with Windows 11 security features

- [ ] **Task 6.4**: Test file watcher functionality
  - Configure NinjaTrader export directory in settings
  - Copy test CSV file to watched directory
  - Verify automatic import occurs
  - Check logs for file watcher activity

- [ ] **Task 6.5**: Test uninstallation with data preservation
  - Run uninstaller
  - Select "No" to data deletion prompt
  - Verify services are stopped and removed
  - Verify Program Files directory is deleted
  - Verify ProgramData directory is preserved
  - Verify no orphaned processes remain

- [ ] **Task 6.6**: Test uninstallation with data removal
  - Reinstall application
  - Run uninstaller
  - Select "Yes" to data deletion prompt
  - Verify all data directories are removed
  - Verify complete cleanup (services, files, registry)

- [ ] **Task 6.7**: Test upgrade installation
  - Install version 1.0.0
  - Create test data
  - Install version 1.0.1 over existing installation
  - Verify data is preserved
  - Verify services are reconfigured

### Phase 7: Documentation and Release

- [ ] **Task 7.1**: Create installation guide
  - Document system requirements (Windows 10/11, admin rights)
  - Document installation steps with screenshots
  - Document service management
  - Document configuration file locations

- [ ] **Task 7.2**: Create troubleshooting guide
  - Document common installation issues
  - Document service startup failures
  - Document port conflict resolution (5555, 6379)
  - Document log file locations

- [ ] **Task 7.3**: Create release notes template
  - Document new features in installer
  - Document installation process changes
  - Document upgrade path from previous versions
  - Document known issues and workarounds

- [ ] **Task 7.4**: Prepare GitHub release
  - Tag release version in git
  - Build final installer with production settings
  - Calculate and document installer checksum (SHA256)
  - Upload installer to GitHub releases
  - Add release notes

- [ ] **Task 7.5**: Optional: Code signing
  - Acquire code signing certificate (optional for v1.0)
  - Sign all executables with certificate
  - Sign installer with certificate
  - Verify signatures are valid

### Phase 8: Post-Release Validation

- [ ] **Task 8.1**: Monitor initial user installations
  - Collect installation feedback
  - Monitor for reported issues
  - Track service startup failures

- [ ] **Task 8.2**: Create installer metrics dashboard
  - Track download count
  - Track installation success/failure rates
  - Document common configuration issues

- [ ] **Task 8.3**: Plan auto-update functionality (future phase)
  - Research auto-update frameworks for Inno Setup
  - Design update check mechanism
  - Plan delta update strategy to reduce download size
