# SYSTEM SPECIFICATION: OFFLINE PATIENT PHOTO CAPTURE SYSTEM

## 1. Executive Summary
The **Offline Patient Photo Capture System** is a specialized Windows desktop software engineered for clinical environments (e.g., Physical Rehabilitation, Dermatology, ENT). It allows hands-free operation to ensure medical practitioners can capture patient photos cleanly and efficiently using voice commands or USB foot pedals, linked automatically to patient electronic medical record IDs.

---

## 2. Hardware Environment (Surveyed & Verified)
The system is specified to interface with the following physical hardware detected on the host workstation:
* **Camera**: **Logi Webcam C920e** (USB UVC compliant, up to 1080p frame resolution, autofocus).
* **Foot Pedal**: **HID Keyboard Device** (Vendor ID: `3553`, Product ID: `B001` - manufactured by *PCSensor/RDing FootSwitch*). Emulates USB keyboard keypresses.
* **Audio Input (Microphone)**: High Definition Audio Device (integrated Realtek input) or Logi C920e stereo microphone array.
* **Operating System**: Windows 10/11 x64.

---

## 3. Functional Requirements

### 3.1. Navigation Architecture & Tabs
* **Left Sidebar Navigation**: Fixed left-side navigation panel for switching between 4 workspaces:
  1. **Tab 1: Chụp ảnh Bệnh nhân (Live Capture & Split Comparison)**: Live video feed + split-screen baseline photo comparison + patient header + hands-free controls.
  2. **Tab 2: Tra cứu & Báo cáo (Patient History & Reports)**: Search bar, view switcher (Timeline vs Grid), PDF photo report exporter.
  3. **Tab 3: Quản lý Nhân viên (Staff & Audit Logs)**: Active shift operator selector, staff database management, system audit log viewer.
  4. **Tab 4: Cài đặt Hệ thống (Hardware & Settings)**: Camera selection, foot pedal key binding tool, mic sensitivity gauge, Intranet OTA updates, Dark/Light theme switcher.

### 3.2. Multi-System Barcode & QR Code Parsing
* **Real-Time Stream Analysis**: Decodes codes continuously from the webcam video feed.
* **Multi-Format Support**:
  * **1D Barcodes**: Code 128 / Code 39 (e.g. `PHCN2647781`, `KCB-2026-0012`, `XN2607290995`).
  * **JSON QR Strings**: Extracts `id`, `name`, `birth_year`, and `gender` automatically (e.g. `{"id": "BN123", "name": "Nguyễn Văn A"}`).
* **9-Stage Multi-Engine & Async OCR Pipeline**:
  * Stages 1-6: ZXing-CPP 360-degree scanning with Unsharp Masking, Adaptive Thresholding, Center ROI 2x Upscaling, CLAHE contrast enhancement, and Bottom-half cropping.
  * Stage 7-8: PyZbar Fallback and OpenCV BarcodeDetector/QRCodeDetector.
  * Stage 9: **Async RapidOCR Fallback**: Background thread running OpenCV region detection + CLAHE + RapidOCR (ONNX Runtime) to read printed text strings (e.g. `XN2607290995`) directly when camera autofocus fails or causes severe motion blur. Operates asynchronously without freezing the camera display thread (>30 FPS).

### 3.6. Standalone Offline Installation & Deployment Specification
* **Zero Python Requirement**: Target PCs in hospital wards do NOT require Python or any external runtime installed.
* **Standalone Bundle (`dist/PatientCaptureApp_v1.0_Offline`)**: Bundles PySide6, OpenCV, PyAudio, Vosk AI Vietnamese speech models (`vosk-model-small-vn-0.4`), SQLite, and config assets.
* **Automated Admin Script (`install_admin.bat`)**:
  * Requests Administrator elevation via native Windows `net session` check.
  * Installs application to `C:\Program Files\PatientCaptureApp`.
  * **Database Protection Rule**: Strictly preserves existing database records at `%APPDATA%\PatientCaptureApp\patients.db` (does NOT overwrite existing records during reinstall/upgrade).
  * Automatically creates Desktop and Start Menu shortcuts.
* **Automated Packaging (`build_package.py`)**: One-command build script (`.venv\Scripts\python build_package.py`) compiling source code and assembling ready-to-use distribution folders for USB transfer.
  * **URL QR Strings**: Extracts query parameters (e.g. `https://his.vn/emr?id=BN123`).
  * **Delimited Barcode Strings**: Splits by `|` or `;` (e.g. `BN123|Nguyễn Văn A|1952|Nam`).
* **Windows Path Sanitization**: Automatically strips or replaces illegal folder characters (`\ / : * ? " < > |`) into clean underscores, ensuring filesystem operations never fail.
* **Scan Feedback**: Audio beep cue upon successful code extraction.

### 3.3. Hands-Free Capture Triggers & Antivirus Resilience
* **Foot Pedal Trigger**:
  * Primary: Global keyboard hook listening to a user-configured key (defaults to `F13` or any mapped key).
  * Antivirus Fallback: Native Qt `keyPressEvent` filter active when app window is focused, ensuring pedal functionality even if low-level OS hooks are flagged by corporate Antivirus.
* **Voice Command (Offline)**:
  * Speech recognition loop powered by Vosk.
  * Triggers instant capture when the word **"Chụp"** is spoken.

### 3.4. Staff Registry & Operator Audit Logging
* **Active Shift Operator Selection**: Doctors/technicians select their name at the start of a shift.
* **Photo Tagging**: Every captured image record in SQLite stores `operator_id` and `operator_name`.
* **Audit Trail**: All critical operations (Barcode Scan, Photo Capture, Photo Delete, Staff Edit, OTA Update) are logged to the `audit_logs` database table.

---

### 3.5. Interactive Hardware Test Dialogs (Diagnostic Test Popups)
Each physical hardware component on Tab 4 includes dedicated interactive **`[ 🛠️ Test ]`** buttons (placed next to configuration comboboxes and in the Hardware Diagnostic Table). Clicking a test button opens a specialized test modal dialog (`QDialog`):

1. **📷 Camera Test Modal (`CameraTestDialog`)**:
   * **Live Stream & QR/Barcode Detection**: Renders a live 1080p video feed and continuously runs barcode/QR detection.
   * **Verification Criterion**: Holding a barcode or QR code in front of the camera plays a beep cue and displays a green badge: `Đã Quét Mã: [ PHCN2647781 ] - TRẠNG THÁI: TỐT (OK)`.

2. **🎙️ Microphone Test Modal (`MicrophoneTestDialog`)**:
   * **Live Audio Gauge & Vosk AI Command Verification**: Renders a real-time RMS Volume Meter (0-100%) and runs Vosk Speech AI.
   * **Verification Criterion**: Speaking any of the 4 standard medical commands (`"chụp"`, `"xóa"`, `"tiếp"`, `"xem"`) highlights the spoken command with a green checkmark badge: `Đã Nhận Lệnh: "CHỤP" - TRẠNG THÁI: TỐT (OK)`.

3. **🦶 Foot Pedal Test Modal (`PedalTestDialog`)**:
   * **4-Gesture Live Checklist**: Displays a checklist of the 4 supported pedal gestures:
     - `[ ] 1 Giậm (Single Tap) -> Chụp ảnh`
     - `[ ] 2 Giậm (Double Tap) -> Xóa ảnh gần nhất`
     - `[ ] 3 Giậm (Triple Tap) -> Bệnh nhân tiếp theo`
     - `[ ] Nhấn Giữ (Long Press) -> Xem lại ảnh`
   * **Verification Criterion**: Stepping on the physical pedal dynamically checks off `[✓]` the corresponding gesture in real time with green visual feedback.

4. **🔌 COM Serial Port Test Modal (`COMPortTestDialog`)**:
   * **Handshake Ping**: Sends test packet (`Ping 0x06` / Baudrate 9600) to RS232/USB Serial port and displays connection response: `Phản Hồi Cổng COM1: OK`.

---

## 4. Non-Functional & Operations Requirements
* **Privacy & Isolation**: 100% offline operation for patient data security.
* **Capture Latency**: Sub-150ms shutter trigger response.
* **Database Concurrency**: SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), foreign keys enabled, and a 5-second busy timeout.
### 4.2. Tracing & Enterprise Production Logging Specification
* **Secure Production Log Path**: Maintains diagnostic & audit logs at `%APPDATA%\PatientCaptureApp\logs\app.log`. Guarantees 100% write permission compatibility on Windows 10/11 enterprise workstations without requiring UAC elevation.
* **Rotating Log File Policy**: Uses `RotatingFileHandler` with `maxBytes = 10MB` and `backupCount = 10` (strict 100MB disk quota cap). Automatically rotates older logs without losing diagnostic history.
* **Log Format & Encoding**: `%(asctime)s [%(levelname)s] [%(name)s] [PID:%(process)d/Thread:%(thread)d] - %(message)s` formatted in UTF-8 to prevent Vietnamese character encoding corruption.
* **Global Unhandled Exception Interceptor**: Overrides `sys.excepthook` to catch and record any unhandled fatal crashes to `app.log` before application exit.
* **Dual Audit Persistence**: Medical operations (patient photo capture, operator changes, hardware scans, barcode scans) are recorded BOTH to `app.log` and stored permanently in the SQLite `audit_logs` database table.
* **OTA Security**: Background version checking over Intranet HTTP or LAN Shared Drive (`\\Server\Share\`). Downloads `update.zip`, verifies **SHA-256 Checksum**, extracts safely using Python `zipfile`, and requests graceful GUI shutdown.
