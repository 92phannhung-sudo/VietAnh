# APPLICATION DESIGN & ARCHITECTURE

## 1. System Architecture Overview

The application follows a **Monolithic Multi-Tab Desktop Architecture** built with PySide6 (Qt6). The layout features a fixed **Left Sidebar Navigation** connecting 4 dedicated workspaces:

```text
+-----------------------------------------------------------------------------------+
| LEFT SIDEBAR    | WORKSPACE CONTENT AREA                                          |
|                 |                                                                 |
| [Tab 1: Capture]| Tab 1: Live 1080p Stream + Split Baseline Comparison + Controls  |
| [Tab 2: History]| Tab 2: Patient Records (Timeline / Grid View) + PDF Export        |
| [Tab 3: Staff]  | Tab 3: Shift Operator Selection + Staff Registry + Audit Logs   |
| [Tab 4: Settings| Tab 4: Hardware Calibration + Dark/Light Theme + Intranet OTA   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Component & Module Responsibilities

* **`main.py`**:
  * Constructs the `MainWindow` with a custom `QListWidget` Sidebar and `QStackedWidget` for tab switching.
  * Manages active operator session state across capture events.
  * Integrates Dark (`#121824`) and Light (`#f8fafc`) QSS theme switching.
* **`database.py`**:
  * Manages SQLite tables with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
  * Tables: `patients`, `photos` (with `operator_id`), `staff`, and `audit_logs`.
* **`barcode_parser.py`**:
  * Decodes raw barcode/QR strings (JSON, URL, Delimited, Standard 1D).
  * Sanitizes invalid characters (`\ / : * ? " < > |`) into safe Windows folder names.
* **`voice_detector.py`**:
  * Background thread listening to PyAudio stream, computing audio RMS volume, and detecting "Chụp" via Vosk.
* **`updater.py`**:
  * Checks Intranet version endpoints, validates SHA-256 Checksums, extracts updates using Python `zipfile`, and emits restart signals.

---

## 3. Database Schema

```sql
-- Patients Table
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,           -- Sanitized Medical Record ID (e.g. PHCN2647781)
    name TEXT,                     -- Patient Name
    birth_year INTEGER,            -- Birth Year
    gender TEXT,                   -- Gender
    created_at TEXT NOT NULL       -- Scan Timestamp
);

-- Staff Table (Medical Operators)
CREATE TABLE IF NOT EXISTS staff (
    id TEXT PRIMARY KEY,           -- Staff ID (e.g. NV001)
    name TEXT NOT NULL,            -- Full Name (e.g. BS. Nguyễn Văn A)
    title TEXT,                    -- Title (Bác sĩ, Kỹ thuật viên, Điều dưỡng)
    department TEXT,               -- Department (Khoa PHCN, Da liễu, v.v.)
    status TEXT DEFAULT 'ACTIVE'   -- ACTIVE / INACTIVE
);

-- Staff Action Mappings Table
CREATE TABLE IF NOT EXISTS staff_action_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT NOT NULL,
    trigger_source TEXT NOT NULL,  -- 'PEDAL_GESTURE' or 'VOICE_KEYWORD'
    trigger_value TEXT NOT NULL,   -- 'SINGLE_TAP', 'DOUBLE_TAP', 'LONG_PRESS', 'chụp', 'xóa'
    action_id TEXT NOT NULL,       -- 'ACTION_CAPTURE', 'ACTION_DELETE_LAST', etc.
    updated_at TEXT NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE,
    UNIQUE(staff_id, trigger_source, trigger_value)
);

-- Hardware Devices Cache Table
CREATE TABLE IF NOT EXISTS hardware_devices (
    device_type TEXT NOT NULL,     -- 'Camera / Webcam', 'Microphone', 'Bàn đạp chân', 'Cổng COM'
    device_name TEXT NOT NULL,     -- e.g. 'Logi Webcam C920e'
    device_index INTEGER DEFAULT 0,
    device_info TEXT,              -- e.g. 'Cổng Index 0 | 1080p Stream'
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_type, device_name, device_index)
);

-- Photos Table
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,      -- Foreign Key -> patients(id) ON DELETE CASCADE
    operator_id TEXT,              -- Foreign Key -> staff(id)
    operator_name TEXT,            -- Cached Operator Name at capture time
    file_path TEXT NOT NULL,       -- Path relative to BASE_DIR
    captured_at TEXT NOT NULL,     -- Capture Timestamp
    FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
);

-- Audit Logs Table (Compliance & System Events)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,      -- SCAN, CAPTURE, DELETE, LOGIN, UPDATE
    operator_name TEXT,
    patient_id TEXT,
    details TEXT
);
```

---

## 4. File Storage Structure

All patient data and images are stored under the app's persistent data directory:

```text
%APPDATA%/PatientCaptureApp/
│
├── app.db                        # SQLite Database (WAL Mode)
├── app.log                       # Rotating Application Trace Logs
├── config.json                   # User Preferences & Keybindings
│
└── photos/                       # Patient Photo Repository
    ├── PHCN2647781/
    │   ├── PHCN2647781_20260727_143025_01.jpg
    │   └── PHCN2647781_20260727_143030_02.jpg
    └── PHCN998877/
        └── PHCN998877_20260727_150012_01.jpg
```
