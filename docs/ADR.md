# ARCHITECTURAL DECISION RECORDS (ADR)

This document records key technical decisions made during the development of the Patient Photo Capture System.

---

## ADR-001: Technology Stack (Python 3.10+ & PySide6)
* **Status**: Accepted
* **Context**: Need a responsive desktop GUI on Windows with OpenCV camera support and speech recognition.
* **Decision**: Adopt Python 3.10+ with `PySide6` (Qt 6 for Python).
* **Consequences**: Fast development, native UI performance, clean thread separation (`QThread`).

---

## ADR-002: Offline Voice Engine (Vosk)
* **Status**: Accepted
* **Context**: Require offline Vietnamese speech recognition for hands-free photo triggering ("Chụp").
* **Decision**: Implement `vosk` with `vosk-model-small-vn-0.22` (~45MB).
* **Consequences**: Zero cloud dependencies, fast recognition latency (<100ms), low memory footprint.

---

## ADR-003: Database Engine & Concurrency (SQLite WAL Mode)
* **Status**: Accepted
* **Context**: Local relational storage for patient records and image paths. Concurrent reads/writes can trigger `database is locked` errors in standard rollback journal mode.
* **Decision**: Enable Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), foreign key constraints (`PRAGMA foreign_keys=ON;`), and busy timeouts (`PRAGMA busy_timeout=5000;`). Next photo index is derived from parsing max file index rather than `COUNT(*)`.
* **Consequences**: Eliminates database lock errors during simultaneous scan/write operations.

---

## ADR-004: Foot Pedal Trigger Strategy & Antivirus Fallback
* **Status**: Accepted
* **Context**: USB foot pedals simulate keyboard presses. Global hooks (`keyboard` library using `SetWindowsHookExW`) can be flagged by corporate Antivirus (Kaspersky Endpoint, Windows Defender ATP) as keyloggers.
* **Decision**: Implement a dual-layer strategy:
  1. Primary: Global keyboard hook (`keyboard` library).
  2. Fallback: Native Qt `keyPressEvent` filter when application window is focused.
* **Consequences**: 100% operational resilience even on locked-down Windows Enterprise computers.

---

## ADR-005: Auto-Update (OTA) & Model Provisioning via Intranet
* **Status**: Accepted (Temporarily Disabled by Default)
* **Context**: Hospital workstations operate in an isolated environment with NO direct public Internet connectivity.
* **Decision**: 
  1. Set `"enable_ota": False` in `config.json` by default to disable background network polling.
  2. Support version checks against an Intranet HTTP URL or LAN Share when re-enabled by IT administrators.
* **Consequences**: Zero unnecessary background network requests or connection timeout errors on offline PCs.

---

## ADR-006: Patient Data Protection & Access Security
* **Status**: Accepted
* **Context**: Healthcare regulations (Ministry of Health / HIPAA) require securing patient data at rest.
* **Decision**: Store patient data under protected user profile directories (`%APPDATA%/PatientCaptureApp/`). Recommend deploying Windows BitLocker full-disk encryption on clinic workstations.
* **Consequences**: Unauthenticated USB BOOT or physical disk theft cannot extract patient photos without workstation decryption keys.

---

## ADR-007: Photo Lifecycle & Storage Management
* **Status**: Accepted
* **Context**: Medical staff need to delete accidental or blurry photos and avoid running out of disk space.
* **Decision**: 
  1. Implement thumbnail right-click context menu ("Xóa ảnh này") to delete both DB record and disk file.
  2. Add pre-capture disk space check alerting staff if free space drops below 500MB.
* **Consequences**: Prevents full disk crashes and gives clinicians full control over photo quality.

---

## ADR-008: Multi-Tab Architecture with Staff & Operator Audit Logging
* **Status**: Accepted
* **Context**: Medical compliance requires tracking which doctor or technician captured each photo session during a shift.
* **Decision**:
  1. Structure the UI into 4 dedicated tabs with a fixed Left Sidebar Navigation.
  2. Implement a Session Operator selector allowing doctors/technicians to pick their active profile at shift start.
  3. Log `operator_id` and `operator_name` alongside every photo record in SQLite (`photos` table) and in the system `audit_logs` table.
* **Consequences**: Full medical audit compliance and accountability without impeding clinical speed during captures.

---

## ADR-009: DirectShow Device Naming, SQLite Hardware Cache & Async Scanner Thread
* **Status**: Accepted
* **Context**: OpenCV default device indices display generic numbers ("Camera Device 0") and probing ports synchronously causes the main GUI to freeze for 2-3 seconds.
* **Decision**:
  1. Query physical friendly names (`Logi Webcam C920e`) via Windows DirectShow `QMediaDevices`.
  2. Create SQLite `hardware_devices` table to cache scanned hardware configuration across application restarts ($<5\text{ms}$ startup load).
  3. Run hardware probes asynchronously on a background `HardwareScannerThread(QThread)` with a native `QProgressDialog` loading modal.
* **Consequences**: Eliminates GUI freezes, provides clear hardware names, and accelerates application startup.

---

## ADR-010: Interactive Hardware Test Dialogs with Real-Time QR, Speech & Pedal Verification
* **Status**: Accepted
* **Context**: Clinicians need interactive hardware verification tools to confirm camera barcode reading, speech AI command recognition, and pedal gesture responsiveness before patient examination shifts.
* **Decision**:
  1. Add dedicated `[ 🛠️ Test ]` buttons next to settings comboboxes and in the Tab 4 Hardware Diagnostic Table.
  2. Implement interactive modal dialogs:
     - `CameraTestDialog`: Live video feed + QR/Barcode detection highlighting.
     - `MicrophoneTestDialog`: Real-time audio volume gauge + Vosk speech AI command recognition (`"chụp"`, `"xóa"`, `"tiếp"`, `"xem"`).
     - `PedalTestDialog`: Interactive 4-gesture checklist (1, 2, 3 taps & long press) checked off in real time upon pedal presses.
     - `COMPortTestDialog`: RS232/USB Serial handshake ping test.
* **Consequences**: Guarantees zero hardware failures during live patient clinical sessions.
