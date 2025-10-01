#!/usr/bin/env python3
"""
Build script for Windows installer using PyInstaller and Inno Setup.
This script automates the entire build process for the Futures Trading Log installer.
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path


class InstallerBuilder:
    """Handles the complete Windows installer build process."""

    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.dist_dir = self.root_dir / "dist"
        self.build_dir = self.root_dir / "build"
        self.vendor_dir = self.root_dir / "vendor"
        self.output_dir = self.root_dir / "Output"

        # Version management
        self.version = self._get_version()

    def _get_version(self):
        """Extract version from VERSION file or default to 1.0.0."""
        version_file = self.root_dir / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0"

    def clean_build(self):
        """Remove previous build artifacts."""
        print("[*] Cleaning previous build artifacts...")

        dirs_to_clean = [self.dist_dir, self.build_dir, self.output_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"    Removed {dir_path}")

        print("[OK] Clean complete")

    def download_dependencies(self):
        """Download Redis and NSSM if not already present."""
        print("[*] Checking vendor dependencies...")

        self.vendor_dir.mkdir(exist_ok=True)

        # Check for Redis
        redis_dir = self.vendor_dir / "redis"
        if not redis_dir.exists() or not (redis_dir / "redis-server.exe").exists():
            print("[WARN] Redis binaries not found in vendor/redis/")
            print("       Please download Redis for Windows and extract to vendor/redis/")
            print("       Download: https://github.com/microsoftarchive/redis/releases")
            return False
        else:
            print("[OK] Redis binaries found")

        # Check for NSSM
        nssm_dir = self.vendor_dir / "nssm" / "win64"
        if not nssm_dir.exists() or not (nssm_dir / "nssm.exe").exists():
            print("[WARN] NSSM not found in vendor/nssm/win64/")
            print("       Please download NSSM and extract to vendor/nssm/win64/")
            print("       Download: https://nssm.cc/download")
            return False
        else:
            print("[OK] NSSM found")

        return True

    def build_executables(self):
        """Build all executables using PyInstaller."""
        print("[*] Building executables with PyInstaller...")

        specs = [
            "FuturesTradingLog.spec",
            "FuturesTradingLog-Worker.spec",
            "FuturesTradingLog-FileWatcher.spec"
        ]

        for spec in specs:
            spec_path = self.root_dir / spec
            if not spec_path.exists():
                print(f"[WARN] Spec file not found: {spec}")
                continue

            print(f"    Building {spec}...")
            result = subprocess.run(
                ["pyinstaller", "--clean", str(spec_path)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"[ERROR] Build failed for {spec}")
                print(result.stderr)
                return False
            else:
                print(f"[OK] Built {spec}")

        return True

    def create_helper_scripts(self):
        """Create batch helper scripts for manual service management."""
        print("📝 Creating helper scripts...")

        bin_dir = self.dist_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Start services script
        start_script = bin_dir / "start-services.bat"
        start_script.write_text("""@echo off
echo Starting Futures Trading Log services...
net start FuturesTradingLog-Redis
timeout /t 2 /nobreak >nul
net start FuturesTradingLog-Web
net start FuturesTradingLog-Worker
net start FuturesTradingLog-FileWatcher
echo All services started!
pause
""")

        # Stop services script
        stop_script = bin_dir / "stop-services.bat"
        stop_script.write_text("""@echo off
echo Stopping Futures Trading Log services...
net stop FuturesTradingLog-FileWatcher
net stop FuturesTradingLog-Worker
net stop FuturesTradingLog-Web
net stop FuturesTradingLog-Redis
echo All services stopped!
pause
""")

        print("[OK] Helper scripts created")

    def create_redis_config(self):
        """Create Redis configuration template."""
        print("[*] Creating Redis configuration template...")

        redis_config_dir = self.vendor_dir / "redis"
        redis_config_dir.mkdir(parents=True, exist_ok=True)

        redis_conf = redis_config_dir / "redis.conf"
        redis_conf.write_text("""# Redis configuration for Futures Trading Log
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 300

# Persistence
save 900 1
save 300 10
save 60 10000
dir {COMMONAPPDATA}\\FuturesTradingLog\\redis

# Logging
loglevel notice
logfile {COMMONAPPDATA}\\FuturesTradingLog\\logs\\redis.log

# Memory
maxmemory 256mb
maxmemory-policy allkeys-lru
""")

        print("[OK] Redis config created")

    def build_installer(self):
        """Compile the Inno Setup installer."""
        print("[*] Building Windows installer...")

        # Find Inno Setup compiler
        iscc_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]

        iscc_exe = None
        for path in iscc_paths:
            if Path(path).exists():
                iscc_exe = path
                break

        if not iscc_exe:
            print("[ERROR] Inno Setup compiler (ISCC.exe) not found")
            print("   Please install Inno Setup 6 from https://jrsoftware.org/isdl.php")
            return False

        # Check if installer script exists
        installer_script = self.root_dir / "installer.iss"
        if not installer_script.exists():
            print(f"[ERROR] Installer script not found: {installer_script}")
            return False

        # Compile installer
        print(f"   Using ISCC: {iscc_exe}")
        result = subprocess.run(
            [iscc_exe, str(installer_script)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("[ERROR] Installer compilation failed")
            print(result.stderr)
            return False

        print("[OK] Installer built successfully")

        # Find the generated installer
        installer_files = list(self.output_dir.glob("*.exe"))
        if installer_files:
            installer_path = installer_files[0]
            print(f"[*] Installer: {installer_path}")
            print(f"    Size: {installer_path.stat().st_size / (1024*1024):.1f} MB")

        return True

    def run(self, skip_download=False):
        """Execute the complete build process."""
        print("=" * 60)
        print("Futures Trading Log - Windows Installer Builder")
        print(f"Version: {self.version}")
        print("=" * 60)

        # Step 1: Clean
        self.clean_build()

        # Step 2: Check dependencies
        if not skip_download:
            if not self.download_dependencies():
                print("\n[ERROR] Build aborted: Missing vendor dependencies")
                return False

        # Step 3: Create Redis config
        self.create_redis_config()

        # Step 4: Build executables
        if not self.build_executables():
            print("\n[ERROR] Build aborted: Executable build failed")
            return False

        # Step 5: Create helper scripts
        self.create_helper_scripts()

        # Step 6: Build installer
        if not self.build_installer():
            print("\n[ERROR] Build aborted: Installer compilation failed")
            return False

        print("\n" + "=" * 60)
        print("[OK] Build completed successfully!")
        print("=" * 60)
        return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Build Windows installer")
    parser.add_argument("--skip-download", action="store_true",
                       help="Skip dependency download check")
    parser.add_argument("--download-only", action="store_true",
                       help="Only check dependencies, don't build")

    args = parser.parse_args()

    builder = InstallerBuilder()

    if args.download_only:
        success = builder.download_dependencies()
        sys.exit(0 if success else 1)

    success = builder.run(skip_download=args.skip_download)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
