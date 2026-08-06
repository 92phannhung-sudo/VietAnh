# TÀI LIỆU ĐẶC TẢ KỸ THUẬT HỆ THỐNG (SYSTEM TECHNICAL SPECIFICATION)
## Patient Capture Workstation - 354 Hospital Edition
**Phiên bản:** v1.0.0 | **Ngày phát hành:** 27/07/2026

---

## 1. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)

### 1.1 Mục tiêu Dự án
Hệ thống **Patient Capture Workstation** là giải pháp phần mềm chuyên dụng phục vụ công tác chụp ảnh, lưu trữ và đối chiếu hình ảnh Bệnh án Điện tử (EMR) tại Bệnh viện 354. Phần mềm cho phép Y Bác sĩ và Kỹ thuật viên thao tác **Rảnh tay 100% (Hands-Free Operations)** thông qua Bàn đạp chân USB và Lệnh giọng nói Tiếng Việt Offline, loại bỏ nguy cơ lây nhiễm khuẩn chéo và chuẩn hóa dữ liệu hình ảnh lâm sàng.

### 1.2 Kiến trúc Hệ thống (Architecture Diagram)

```mermaid
graph TD
    UI[PySide6 Qt GUI - MainWindow] --> CamThread[CameraThread - OpenCV 1080p]
    UI --> VoiceThread[VoiceDetectorThread - Vosk AI Offline]
    UI --> PedalFSM[PedalGestureFSM - Windows Global HID Hook]
    UI --> DB[Database Module - SQLite WAL Mode]
    UI --> HWScanner[HardwareScannerThread - Diagnostic Engine]
    UI --> UpdaterThread[UpdateCheckerThread - OTA Intranet]

    CamThread --> BarcodeEngine[PyZbar + OpenCV Multi-Engine Scanner]
    CamThread --> Disk[Dynamic Working Directory - JPG 95% Quality]
    VoiceThread --> PyAudio[PyAudio Stream / WASAPI]
    DB --> SQLite[(app.db WAL File)]
```

---

## 2. ĐẶC TẢ TÍNH NĂNG CỐT LÕI (CORE FUNCTIONAL SPECIFICATIONS)

### 2.1 Quét & Giải Mã Mã Vạch / QR Code (Multi-Engine & Async OCR Pipeline)
- **Chuẩn mã vạch hỗ trợ**: JSON QR, URL QR (`https://his...?id=BN123`), Chuỗi phân tách (`BN123|Nguyễn Văn A|1952|Nam`), Code 128, Code 39, QR Code tiêu chuẩn.
- **Thuật toán xử lý ảnh 9 cấp độ (9-Stage Multi-Engine + Async OCR Fallback)**:
  1. **ZXing-CPP Grayscale gốc**: Quét siêu tốc 360 độ trên ảnh xám (~6ms).
  2. **ZXing-CPP + Unsharp Mask**: Làm nét biên cạnh vạch barcode bị mờ nhẹ (~5ms).
  3. **ZXing-CPP + Adaptive Threshold**: Khử vùng tối / ánh sáng không đều (~4ms).
  4. **ZXing-CPP + ROI Center 2x**: Crop vùng trung tâm phiếu & phóng to 2 lần (~8ms).
  5. **ZXing-CPP + CLAHE**: Cân bằng tương phản vùng sáng/tối (~7ms).
  6. **ZXing-CPP + Bottom-Half Crop**: Crop nửa dưới phiếu (vùng bác sĩ giơ phiếu) (~6ms).
  7. **PyZbar Fallback**: Engine dự phòng chuẩn cho các định dạng mã 1D đặc thù (~10ms).
  8. **OpenCV BarcodeDetector & QRCodeDetector**: Phát hiện nhanh vùng chứa mã vạch.
  9. **Async RapidOCR Fallback (Khử lỗi Out-of-Focus)**: Khi camera bị mất nét / mờ vạch sọc, luồng ngầm bất đồng bộ (Thread riêng) tự động dùng OpenCV `BarcodeDetector.detect()` để tìm vị trí vạch (hoặc full-frame fallback), phóng to 2x, áp dụng CLAHE + Unsharp Mask và dùng **RapidOCR (ONNX Runtime)** để đọc trực tiếp dòng chữ mã số in bên dưới vạch barcode (ví dụ: `XN2607290995`). OCR chạy bất đồng bộ mỗi 2 giây, đảm bảo luồng camera chính đạt tốc độ **>30 FPS không bao giờ bị đơ**.
- **Tốc độ xử lý luồng camera chính**: < 150ms per frame.

### 2.2 Điều Khiển Rảnh Tay (Hands-Free Control System)
1. **Bàn Đạp Chân (USB FootSwitch - HID Global Hook)**:
   - Phím nhận diện: `F13`, `ALT`, `F12`.
   - Cử chỉ FSM:
     - **Single Tap (1 giậm)** -> Chụp ảnh bệnh nhân (`ACTION_CAPTURE`).
     - **Double Tap (2 giậm)** -> Xóa ảnh vừa chụp (`ACTION_DELETE_LAST`).
     - **Triple Tap (3 giậm)** -> Chuyển bệnh nhân mới (`ACTION_NEXT_PATIENT`).
     - **Long Press (>1500ms)** -> Xem ảnh phóng to (`ACTION_VIEW_PHOTO`).
2. **Nhận Diện Giọng Nói Tiếng Việt Offline (Vosk Speech AI)**:
   - Mô hình AI: `vosk-model-small-vn-0.4` (Chạy hoàn toàn Offline 100%).
   - Từ khóa khớp chuẩn: `"chụp"`, `"xóa"`, `"tiếp"`, `"xem"`.
   - Cooldown khử nhiêu lặp: 2.0 giây.

### 2.3 Quản Lý Bệnh Nhân & Lưu Trữ Hình Ảnh
- **Thư mục làm việc động (Dynamic Working Directory)**: Tùy chỉnh lưu trữ trên bất kỳ ổ đĩa nội cục (`C:`, `D:`) hoặc ổ đĩa mạng Intranet (`\\server\emr_photos`).
- **Cấu trúc lưu trữ**: `{working_dir}/{patient_id}/{patient_id}_{YYYYMMDD_HHMMSS}_{index:02d}.jpg`.
- **Chất lượng hình ảnh**: JPEG Quality 95%, giữ đúng độ phân giải phần cứng (1920x1080).
- **Màn hình chia đôi đối chiếu (Split-screen Baseline View)**:
  - Bên trái: Luồng Camera thời gian thực.
  - Bên phải: Ảnh mốc đợt 1 (hoặc ảnh tùy chọn qua menu chuột phải).

---

## 3. ĐẶC TẢ CƠ SỞ DỮ LIỆU (DATABASE SCHEMA SPECIFICATION)

Cơ sở dữ liệu SQLite chạy chế độ **WAL (Write-Ahead Logging)** để đảm bảo an toàn truy xuất đa luồng đồng thời.

```sql
-- 1. Bảng Bệnh Nhân
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT,
    birth_year INTEGER,
    gender TEXT,
    created_at TEXT NOT NULL
);

-- 2. Bảng Nhân Viên Y Tế
CREATE TABLE IF NOT EXISTS staff (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    department TEXT,
    status TEXT DEFAULT 'ACTIVE'
);

-- 3. Bảng Hình Ảnh Chụp
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    operator_id TEXT,
    operator_name TEXT,
    file_path TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
);

-- 4. Bảng Nhật Ký Kiểm Toán (Audit Logs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    operator_name TEXT,
    patient_id TEXT,
    details TEXT
);

-- 5. Bảng Ánh Xạ Hành Động Nhân Viên (Action Mappings)
CREATE TABLE IF NOT EXISTS staff_action_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT NOT NULL,
    trigger_source TEXT NOT NULL,
    trigger_value TEXT NOT NULL,
    action_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE,
    UNIQUE(staff_id, trigger_source, trigger_value)
);

-- 6. Bảng Bộ Nhớ Đệm Phần Cứng Scanned Cache
CREATE TABLE IF NOT EXISTS hardware_devices (
    device_type TEXT NOT NULL,
    device_name TEXT NOT NULL,
    device_index INTEGER DEFAULT 0,
    device_info TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_type, device_name, device_index)
);
```

---

## 4. QUẢN LÝ ĐA LUỒNG & BỘ NHỚ (MULTI-THREADING & MEMORY MANAGEMENT)

### 4.1 Danh sách Luồng Độc Lập (QThread Architecture)
1. **`CameraThread` (QThread)**: Đọc luồng video OpenCV 30 FPS, phát tín hiệu QImage đã sao chép bộ nhớ độc lập (`.copy()`), thực hiện chụp ảnh & quét mã vạch background.
2. **`VoiceDetectorThread` (QThread)**: Mở stream PyAudio WASAPI 16kHz, chạy mô hình Kaldi Vosk AI, tính toán Volume RMS độ nhạy micro và phát tín hiệu từ khóa.
3. **`HardwareScannerThread` (QThread)**: Quét chẩn đoán các cổng USB UVC, Audio Input, HID Pedal, COM Serial Ports không làm đơ main GUI thread.
4. **`UpdateCheckerThread` (QThread)**: Kiểm tra và tải bản cập nhật OTA từ Server Intranet ngầm.

### 4.2 Nguyên Tắc An Toàn Bộ Nhớ & Thread Safety
- **Tránh rò rỉ QImage**: Sử dụng `QImage(...).copy()` trước khi emit signal qua Qt Event Loop.
- **An toàn dừng luồng (Shutdown Safety)**: Bỏ hoàn toàn `QThread.terminate()`, áp dụng dừng luồng hợp tác (*Cooperative Flag Check*) với `wait(1000)`.
- **An toàn SQLite**: Mọi kết nối CSDL đều được giải phóng trong khối `try...finally: conn.close()`.

---

## 5. CẤU TRÚC MÃ NGUỒN (CODEBASE DIRECTORY STRUCTURE)

```
VietAnh/
├── main.py                     # Cửa sổ chính MainWindow & các luồng giao diện Qt
├── config.py                   # Quản lý file cấu hình config.json & QSS Theme
├── database.py                 # Hàm tương tác SQLite CSDL & Audit Logs
├── voice_detector.py           # Luồng nhận diện giọng nói Vosk AI Offline & PyAudio
├── pedal_gesture_fsm.py        # Máy trạng thái hữu hạn (FSM) phân tích cử chỉ bàn đạp
├── hardware_test_dialogs.py    # Modal kiểm thử phần cứng & Dialog xem ảnh PySide6 nội bộ
├── barcode_parser.py           # Bộ giải mã chuẩn mã vạch / QR Bệnh án
├── action_registry.py          # Hệ thống đăng ký & điều phối hành động lâm sàng
├── updater.py                  # Luồng cập nhật OTA tự động qua Intranet
├── PatientCaptureApp.spec      # File cấu hình đóng gói PyInstaller .exe
├── requirements.txt            # Danh sách thư viện phụ thuộc Python
└── docs/                       # Tài liệu đặc tả & kế hoạch thực thi
```

---

## 6. QUY TRÌNH ĐÓNG GÓI & CẬP NHẬT (BUILD & OTA PROTOCOL)

### 6.1 Lệnh đóng gói PyInstaller
```bash
pyinstaller PatientCaptureApp.spec
```

### 6.2 Cấu trúc file cấu hình OTA Intranet (`version.json`)
```json
{
    "version": "1.0.1",
    "url": "http://192.168.1.100/updates/update_v1.0.1.zip",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```
Khi phát hiện bản mới, luồng `UpdateCheckerThread` tải file zip, xác thực mã băm SHA-256, sinh script `updater.bat` và kích hoạt tự động khởi động lại ứng dụng.
