import os
import json
import sys
from pathlib import Path

__version__ = "1.0.0"


def get_user_data_dir() -> Path:
    """App data root: %APPDATA% on Windows, ~/Library/Application Support on macOS."""
    override = os.getenv("PATIENT_CAPTURE_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "PatientCaptureApp"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PatientCaptureApp"

    xdg = os.getenv("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "PatientCaptureApp"
    return Path.home() / ".local" / "share" / "PatientCaptureApp"


# Base Data Directory
BASE_DIR = get_user_data_dir()
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Data Paths
PHOTOS_DIR = BASE_DIR / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# Logs Paths (App Data Directory for Production Write Permissions)
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOGS_DIR / "app.log"


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_sherpa_model_dir():
    """Resolve sherpa-onnx Vietnamese model directory."""
    model_name = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
    bundled = get_app_dir() / "models" / model_name
    if bundled.exists():
        return str(bundled)
    alt = get_app_dir() / model_name
    if alt.exists():
        return str(alt)
    return str(BASE_DIR / model_name)

DB_PATH = BASE_DIR / "app.db"
CONFIG_FILE = BASE_DIR / "config.json"

# Default configuration settings
DEFAULT_CONFIG = {
    "trigger_key": "f13",
    "camera_index": 0,
    "microphone_name": "default",
    "sherpa_model_dir": get_sherpa_model_dir(),
    "working_dir": str(PHOTOS_DIR),
    "update_url": "http://192.168.1.100/updates/version.json",
    "enable_ota": False,  # Temporarily disabled for offline hospital setup
    "active_theme": "dark",
    "active_operator_id": "NV001"
}

def get_photos_dir():
    try:
        cfg = load_config()
        w_dir = Path(cfg.get("working_dir", str(PHOTOS_DIR)))
        w_dir.mkdir(parents=True, exist_ok=True)
        return w_dir
    except Exception:
        return PHOTOS_DIR

def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["sherpa_model_dir"] = get_sherpa_model_dir()
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            save_config(data)
            return data
    except Exception:
        return DEFAULT_CONFIG

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

# Premium QSS Stylesheets
DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #121824;
}
QWidget {
    color: #e2e8f0;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 2px solid #1e293b;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    background-color: #1e2530;
    font-weight: bold;
    color: #38bdf8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 6px;
    color: #f8fafc;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
}
QPushButton {
    background-color: #0284c7;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0369a1;
}
QPushButton:pressed {
    background-color: #075985;
}
QPushButton#capture_btn {
    background-color: #22c55e;
    font-size: 16px;
    padding: 12px;
}
QPushButton#capture_btn:hover {
    background-color: #16a34a;
}
QListWidget#sidebar {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
    outline: none;
    font-size: 14px;
    font-weight: bold;
}
QListWidget#sidebar::item {
    height: 50px;
    padding-left: 15px;
    color: #94a3b8;
    border-left: 4px solid transparent;
}
QListWidget#sidebar::item:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-left: 4px solid #38bdf8;
}
QTableWidget {
    background-color: #0f172a;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    color: #e2e8f0;
}
QHeaderView::section {
    background-color: #1e2530;
    color: #38bdf8;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #1e293b;
}
QScrollBar:vertical {
    border: none;
    background-color: #0f172a;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 20px;
    border-radius: 5px;
}
QStatusBar {
    background-color: #0f172a;
    color: #94a3b8;
}
"""

LIGHT_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #f8fafc;
}
QWidget {
    color: #0f172a;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    background-color: #ffffff;
    font-weight: bold;
    color: #0284c7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px;
    color: #0f172a;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0284c7;
}
QPushButton {
    background-color: #0284c7;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0369a1;
}
QPushButton:pressed {
    background-color: #075985;
}
QPushButton#capture_btn {
    background-color: #16a34a;
    font-size: 16px;
    padding: 12px;
}
QPushButton#capture_btn:hover {
    background-color: #15803d;
}
QListWidget#sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
    outline: none;
    font-size: 14px;
    font-weight: bold;
}
QListWidget#sidebar::item {
    height: 50px;
    padding-left: 15px;
    color: #64748b;
    border-left: 4px solid transparent;
}
QListWidget#sidebar::item:selected {
    background-color: #f1f5f9;
    color: #0284c7;
    border-left: 4px solid #0284c7;
}
QTableWidget {
    background-color: #ffffff;
    gridline-color: #e2e8f0;
    border: 1px solid #e2e8f0;
    color: #0f172a;
}
QHeaderView::section {
    background-color: #f1f5f9;
    color: #0284c7;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #cbd5e1;
}
QScrollBar:vertical {
    border: none;
    background-color: #f1f5f9;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    min-height: 20px;
    border-radius: 5px;
}
QStatusBar {
    background-color: #f1f5f9;
    color: #64748b;
}
"""
