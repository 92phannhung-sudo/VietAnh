import os
import json
import logging
import urllib.request
import subprocess
import sys
import hashlib
import zipfile
from pathlib import Path
from PySide6.QtCore import QThread, Signal
import config

logger = logging.getLogger("PatientApp")

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest().lower()

class UpdateCheckerThread(QThread):
    update_checked = Signal(bool, str, str, str)  # (has_update, new_version, download_url, sha256)
    update_progress = Signal(int)                 # 0 to 100
    error_signal = Signal(str)
    status_signal = Signal(str)
    ready_to_restart = Signal(str)                # Emits batch script path to main GUI thread

    def __init__(self, update_url=None):
        super().__init__()
        app_config = config.load_config()
        self.update_url = update_url or app_config.get("update_url", "http://192.168.1.100/updates/version.json")
        self._download_url = None
        self._expected_sha256 = None

    def run(self):
        try:
            self.status_signal.emit("Checking for updates on Intranet...")
            
            # Support both HTTP Intranet URLs and Shared Network Paths
            if self.update_url.startswith("http://") or self.update_url.startswith("https://"):
                req = urllib.request.Request(
                    self.update_url, 
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
            else:
                with open(self.update_url, "r", encoding="utf-8") as f:
                    data = json.load(f)

            remote_version = data.get("version", "1.0.0")
            download_url = data.get("url", "")
            expected_sha256 = data.get("sha256", "").strip().lower()
            
            # Check version components (Major.Minor.Patch)
            local_parts = [int(x) for x in config.__version__.split(".")]
            remote_parts = [int(x) for x in remote_version.split(".")]
            
            has_update = remote_parts > local_parts
            
            self.update_checked.emit(has_update, remote_version, download_url, expected_sha256)
            if has_update:
                self.status_signal.emit(f"New update v{remote_version} available")
            else:
                self.status_signal.emit("Application is up to date")
                
        except Exception as e:
            logger.error(f"[UPDATER_ERROR] Error checking updates: {str(e)}")
            self.status_signal.emit("Intranet check offline")
            self.update_checked.emit(False, "", "", "")

    def download_and_install(self, url, expected_sha256=""):
        self._download_url = url
        self._expected_sha256 = expected_sha256.lower()
        self.status_signal.emit("Downloading Intranet update...")
        
        try:
            zip_path = Path(os.getcwd()) / "update.zip"
            
            if self._download_url.startswith("http://") or self._download_url.startswith("https://"):
                def report_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = int(block_num * block_size * 100 / total_size)
                        self.update_progress.emit(min(100, percent))
                
                urllib.request.urlretrieve(self._download_url, zip_path, reporthook=report_hook)
            else:
                import shutil
                shutil.copy(self._download_url, zip_path)
                self.update_progress.emit(100)

            # Security Verification: SHA-256 Checksum
            if self._expected_sha256:
                actual_sha256 = calculate_sha256(zip_path)
                if actual_sha256 != self._expected_sha256:
                    zip_path.unlink()
                    err = f"SHA-256 mismatch! Expected: {self._expected_sha256}, Got: {actual_sha256}"
                    logger.error(f"[SECURITY_ALERT] {err}")
                    self.error_signal.emit("Bản cập nhật không an toàn (Lỗi Hash SHA-256)!")
                    self.status_signal.emit("Lỗi Checksum Hash")
                    return

            self.status_signal.emit("Extracting update package...")
            extract_dir = Path(os.getcwd()) / "_update_temp"
            extract_dir.mkdir(exist_ok=True)
            
            # Safe extraction using Python zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
            zip_path.unlink()
            
            is_frozen = getattr(sys, 'frozen', False)
            if is_frozen:
                restart_cmd = f'start "" "{sys.executable}"'
            else:
                restart_cmd = f'start "" "{sys.executable}" "{Path(os.getcwd()) / "main.py"}"'

            # Write batch file to safely swap files after app closes
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
xcopy /E /Y "{extract_dir}\\*" "{os.getcwd()}"
rmdir /S /Q "{extract_dir}"
{restart_cmd}
del "%~f0"
"""
            bat_path = Path(os.getcwd()) / "updater.bat"
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
            
            logger.info("[UPDATER] Update downloaded & verified. Requesting main app shutdown.")
            self.ready_to_restart.emit(str(bat_path))
            
        except Exception as e:
            logger.error(f"[UPDATER_ERROR] Error executing update: {str(e)}", exc_info=True)
            self.error_signal.emit(f"Cập nhật thất bại: {str(e)}")
            self.status_signal.emit("Update failed")
