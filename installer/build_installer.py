"""
Automated build script for Futures Trading Log Windows Installer.
This script handles the complete build process from PyInstaller to Inno Setup.
"""

import subprocess
import sys
import shutil
from pathlib import Path
import time

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(message):
    """Print a formatted header message."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")

def print_step(step_num, message):
    """Print a formatted step message."""
    print(f"{Colors.OKCYAN}{Colors.BOLD}Step {step_num}: {message}{Colors.ENDC}")

def print_success(message):
    """Print a success message."""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")

def print_error(message):
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

def print_warning(message):
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")

def run_command(command, description, cwd=None):
    """Run a shell command and handle errors."""
    print(f"\n{Colors.OKBLUE}Running: {description}{Colors.ENDC}")
    print(f"Command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        print_success(f"{description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed!")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print_error(f"Command not found: {command[0]}")
        print_warning("Make sure the required tool is installed and in PATH")
        return False

def clean_build_directories():
    """Clean previous build artifacts."""
    print_step(1, "Cleaning previous build artifacts")

    dirs_to_clean = [
        Path("build"),
        Path("dist"),
        Path("output"),
    ]

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print(f"Removing {dir_path}...")
            shutil.rmtree(dir_path)
            print_success(f"Removed {dir_path}")

    print_success("Build directories cleaned")

def build_executables():
    """Build all executables using PyInstaller."""
    print_step(2, "Building executables with PyInstaller")

    spec_files = [
        ("app.spec", "Main Flask Application"),
    ]

    for spec_file, description in spec_files:
        print(f"\n{Colors.OKBLUE}Building: {description}{Colors.ENDC}")

        if not run_command(
            ["pyinstaller", spec_file, "--clean", "--noconfirm"],
            f"PyInstaller build for {description}",
            cwd=Path.cwd()
        ):
            return False

        time.sleep(1)

    print_success("All executables built successfully")
    return True

def verify_dependencies():
    """Verify that Redis and NSSM are downloaded."""
    print_step(3, "Verifying dependencies")

    redis_dir = Path("redis")
    nssm_exe = Path("nssm/nssm.exe")

    missing_deps = []

    if not redis_dir.exists() or not any(redis_dir.glob("redis-server.exe")):
        missing_deps.append("Redis for Windows")
    else:
        print_success("Redis found")

    if not nssm_exe.exists():
        missing_deps.append("NSSM")
    else:
        print_success("NSSM found")

    if missing_deps:
        print_error(f"Missing dependencies: {', '.join(missing_deps)}")
        print_warning("Run 'python download_dependencies.py' to download them")
        return False

    print_success("All dependencies verified")
    return True

def create_icon():
    """Create or verify icon file exists."""
    print_step(4, "Checking icon file")

    icon_path = Path("icon.ico")

    if not icon_path.exists():
        print_warning("icon.ico not found, installer will use default icon")
        # Create a dummy icon file reference
        static_icon = Path("../static/favicon.ico")
        if static_icon.exists():
            shutil.copy(static_icon, icon_path)
            print_success("Copied icon from static/favicon.ico")
        else:
            print_warning("No icon available - installer will proceed without custom icon")
    else:
        print_success("Icon file found")

    return True

def build_installer():
    """Build the installer using Inno Setup."""
    print_step(5, "Building Windows installer with Inno Setup")

    # Try common Inno Setup installation paths
    inno_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
    ]

    inno_compiler = None
    for path in inno_paths:
        if path.exists():
            inno_compiler = path
            break

    if not inno_compiler:
        print_error("Inno Setup compiler not found!")
        print_warning("Please install Inno Setup from: https://jrsoftware.org/isdl.php")
        print_warning("After installation, run this script again")
        return False

    print(f"Using Inno Setup compiler: {inno_compiler}")

    if not run_command(
        [str(inno_compiler), "FuturesTradingLog.iss"],
        "Inno Setup compilation",
        cwd=Path.cwd()
    ):
        return False

    print_success("Installer built successfully!")
    return True

def display_results():
    """Display build results and output location."""
    print_header("BUILD COMPLETE!")

    output_dir = Path("output")
    if output_dir.exists():
        installers = list(output_dir.glob("*.exe"))
        if installers:
            print(f"{Colors.OKGREEN}{Colors.BOLD}Installer created:{Colors.ENDC}")
            for installer in installers:
                size_mb = installer.stat().st_size / (1024 * 1024)
                print(f"  📦 {installer.name}")
                print(f"     Location: {installer.absolute()}")
                print(f"     Size: {size_mb:.2f} MB")
        else:
            print_warning("No installer file found in output directory")
    else:
        print_warning("Output directory not found")

    print(f"\n{Colors.OKCYAN}Next steps:{Colors.ENDC}")
    print("  1. Test the installer on a clean Windows machine")
    print("  2. Verify all services start correctly")
    print("  3. Check http://localhost:5000 after installation")
    print("  4. Test the uninstaller")

def main():
    """Main build process."""
    start_time = time.time()

    print_header("Futures Trading Log - Windows Installer Build")

    # Change to installer directory
    installer_dir = Path(__file__).parent
    import os
    os.chdir(installer_dir)

    print(f"Build directory: {Path.cwd()}")

    # Build process steps
    steps = [
        (clean_build_directories, "Clean"),
        (verify_dependencies, "Verify dependencies"),
        (create_icon, "Check icon"),
        (build_executables, "Build executables"),
        (build_installer, "Build installer"),
    ]

    for step_func, step_name in steps:
        if not step_func():
            print_error(f"Build failed at step: {step_name}")
            sys.exit(1)

    # Display results
    display_results()

    elapsed_time = time.time() - start_time
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}Total build time: {elapsed_time:.2f} seconds{Colors.ENDC}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Build cancelled by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
