"""
Download Redis for Windows and NSSM for the installer.
This script downloads the required dependencies for the Windows installer.
"""

import urllib.request
import zipfile
import os
from pathlib import Path

def download_file(url, output_path):
    """Download a file from URL to output_path."""
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded to {output_path}")

def extract_zip(zip_path, extract_to):
    """Extract a zip file to a directory."""
    print(f"Extracting {zip_path} to {extract_to}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted successfully")

def download_redis():
    """Download Redis for Windows (Memurai or Redis fork)."""
    # Using the Microsoft Open Tech Redis port (maintained by ServiceStack)
    redis_url = "https://github.com/redis-windows/redis-windows/releases/download/7.2.6/Redis-7.2.6-Windows-x64-msys2.zip"
    redis_zip = Path("installer/downloads/redis.zip")

    redis_zip.parent.mkdir(parents=True, exist_ok=True)

    if redis_zip.exists():
        print(f"Redis zip already exists at {redis_zip}")
    else:
        download_file(redis_url, redis_zip)

    # Extract Redis
    extract_to = Path("installer/redis")
    extract_to.mkdir(parents=True, exist_ok=True)
    extract_zip(redis_zip, extract_to)

    print(f"Redis extracted to {extract_to}")

def download_nssm():
    """Download NSSM (Non-Sucking Service Manager)."""
    nssm_url = "https://nssm.cc/release/nssm-2.24.zip"
    nssm_zip = Path("installer/downloads/nssm.zip")

    nssm_zip.parent.mkdir(parents=True, exist_ok=True)

    if nssm_zip.exists():
        print(f"NSSM zip already exists at {nssm_zip}")
    else:
        download_file(nssm_url, nssm_zip)

    # Extract NSSM
    extract_to = Path("installer/nssm_temp")
    extract_to.mkdir(parents=True, exist_ok=True)
    extract_zip(nssm_zip, extract_to)

    # Copy the 64-bit version to the installer directory
    nssm_exe_src = extract_to / "nssm-2.24" / "win64" / "nssm.exe"
    nssm_exe_dest = Path("installer/nssm/nssm.exe")
    nssm_exe_dest.parent.mkdir(parents=True, exist_ok=True)

    if nssm_exe_src.exists():
        import shutil
        shutil.copy(nssm_exe_src, nssm_exe_dest)
        print(f"NSSM copied to {nssm_exe_dest}")
    else:
        print(f"Warning: Could not find NSSM executable at {nssm_exe_src}")

if __name__ == "__main__":
    print("=" * 60)
    print("Downloading Windows Installer Dependencies")
    print("=" * 60)

    try:
        download_redis()
        print()
        download_nssm()
        print()
        print("=" * 60)
        print("All dependencies downloaded successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"Error downloading dependencies: {e}")
        import traceback
        traceback.print_exc()
