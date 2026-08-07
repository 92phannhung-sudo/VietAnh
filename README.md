# OFFLINE PATIENT PHOTO CAPTURE SYSTEM (HỆ THỐNG CHỤP ẢNH BỆNH ÁN)

Một phần mềm Windows chuyên dụng dành cho các khoa/phòng khám y tế (Phục hồi chức năng, Da liễu, Tai Mũi Họng) hỗ trợ chụp ảnh bệnh nhân rảnh tay qua **Bàn đạp chân (USB Foot Pedal)** hoặc **Giọng nói offline ("Chụp")**, tự động phân loại ảnh theo Mã Bệnh Án và lưu vết kiểm toán y tế.

**Phiên khám (v1):** F1 mở → F5/barcode lưới hồ sơ → F2 khóa & chụp → pedal chỉ chụp → F4 Standby. Spec: [`docs/SPEC_HANDS_FREE_SESSION_V1.md`](docs/SPEC_HANDS_FREE_SESSION_V1.md) · Hướng dẫn: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

---

## 🚀 Hướng Dẫn Nhanh (Quick Start)

### 1. Khởi chạy Ứng dụng
Khởi chạy trực tiếp từ PowerShell tại thư mục ứng dụng:
```powershell
.venv\Scripts\python main.py
```

### 2. Yêu cầu Hệ thống & Phần cứng (Đã khảo sát)
* **Hệ điều hành**: Windows 10/11 x64 (Chạy 100% Offline hoặc Mạng Nội Bộ Intranet).
* **Camera**: **Logi Webcam C920e** (USB UVC, 1080p Stream).
* **Bàn đạp chân**: **PCSensor USB FootSwitch** (Vendor ID `3553`, Product ID `B001` - Gán phím `F13`).
* **Microphone**: Micro tích hợp Webcam Logitech C920e hoặc Realtek High Definition Audio.

---

## 📁 Danh Mục Tài Liệu Kỹ Thuật (Documentation Index)

Toàn bộ tài liệu thiết kế và vận hành theo quy chuẩn SDLC được lưu trữ đầy đủ trong thư mục `docs/`:

1. 📄 **[docs/SPECIFICATION.md](docs/SPECIFICATION.md)**
   * Đặc tả yêu cầu chức năng, quét mã vạch đa hệ thống, làm sạch tên thư mục Windows, và quy chuẩn ghi Trace Log.
2. 🎯 **[docs/ACTION_MAPPING_SPEC.md](docs/ACTION_MAPPING_SPEC.md)**
   * Đặc tả Kỹ thuật Động cơ Ánh xạ Hành động (Action Mapping Engine), bộ đếm nhịp giậm chân FSM (Single/Double/Triple tap/Long press), Giới hạn Ngữ pháp Vosk AI Grammar, và CSDL lưu cấu hình theo từng Bác sĩ.
3. 🏛️ **[docs/ADR.md](docs/ADR.md)**
   * Nhật ký 9 quyết định kiến trúc cốt lõi (PySide6, Vosk Offline, SQLite WAL Mode, Antivirus Keypress Fallback, SHA-256 OTA Security, HIPAA BitLocker Data Protection, Photo Deletion Lifecycle, Staff Audit Logging, DirectShow Device Friendly Naming & SQLite Hardware Cache).
3. 📐 **[docs/DESIGN.md](docs/DESIGN.md)**
   * Mô tả sơ đồ kiến trúc 4 Tab Sidebar, sơ đồ các mô-đun Python, Lược đồ CSDL SQLite (`patients`, `staff`, `staff_action_mappings`, `hardware_devices`, `photos`, `audit_logs`), và cấu trúc thư mục lưu trữ.
4. 📖 **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**
   * Hướng dẫn chi tiết dành cho Bác sĩ & Quản trị viên IT: Quy trình chụp ảnh màn hình đôi (Split-screen), xem/xóa ảnh, chọn người thao tác ca trực, xuất báo cáo PDF, Quét chẩn đoán phần cứng bất đồng bộ với bảng Loading Progress Modal, và xử lý sự cố.
5. 💻 **[docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)**
   * Hướng dẫn cài đặt và chạy trên Windows 10/11: Cài Python, tạo venv, cài thư viện (PyAudio, pyzbar, Vosk), tải mô hình AI giọng nói, đóng gói bản cài đặt offline (PyInstaller), triển khai USB tại máy trạm bệnh viện, xử lý sự cố.

---

## 🛠️ Cấu Trúc Mã Nguồn (Source Code Map)

* **`main.py`**: Mã nguồn giao diện chính 4 Tab, `HardwareScannerThread` bất đồng bộ với Modal Progress Dialog, OpenCV Stream, Keyboard Hook & Qt Fallback.
* **`database.py`**: Trình quản lý CSDL SQLite WAL Mode (`patients`, `staff`, `staff_action_mappings`, `hardware_devices`, `photos`, `audit_logs`).
* **`action_registry.py`**: Đăng ký các Hành động lâm sàng mở rộng bằng Python Decorators (`@register_action`).
* **`pedal_gesture_fsm.py`**: Động cơ đếm nhịp giậm chân FSM phân biệt 1, 2, 3 giậm và nhấn giữ.
* **`barcode_parser.py`**: Trình bóc tách mã vạch đa chuẩn & làm sạch ký tự đường dẫn Windows.
* **`voice_detector.py`**: Luồng ngầm xử lý Microphone & Nhận diện giọng nói tiếng Việt offline bằng Vosk với mảng Ràng buộc Ngữ pháp.
* **`updater.py`**: Luồng ngầm kiểm tra bản cập nhật OTA Intranet & xác thực Checksum SHA-256.
* **`config.py`**: Quản lý đường dẫn `%APPDATA%\PatientCaptureApp\` và bộ chủ đề Dark/Light QSS.
