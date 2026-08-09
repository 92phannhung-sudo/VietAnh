# HƯỚNG DẪN CÀI ĐẶT VÀ CHẠY TRÊN WINDOWS  
# 354 EMR Workstation — Offline Patient Photo Capture System

> **Tài liệu dành cho kỹ thuật viên IT bệnh viện.**  
> Cập nhật: 2026-08-09

---

## 1. YÊU CẦU PHẦN CỨNG

| Thiết bị | Yêu cầu tối thiểu |
|---|---|
| **Hệ điều hành** | Windows 10/11 x64 (Offline 100%) |
| **CPU** | Intel Core i3 thế hệ 8+ hoặc tương đương |
| **RAM** | ≥ 4 GB |
| **Ổ cứng trống** | ≥ 2 GB (cho ứng dụng + model AI + CSDL ảnh) |
| **Camera** | Logitech C920e USB UVC 1080p (hoặc camera USB tương thích) |
| **Bàn đạp chân** | PCSensor USB FootSwitch (VID `3553`, PID `B001`) |
| **Microphone** | Mic tích hợp Webcam Logitech C920e hoặc Realtek HD Audio |

---

## 2. CÀI ĐẶT MÔI TRƯỜNG PHÁT TRIỂN (DEVELOPER SETUP)

### Bước 2.1: Cài Python 3.10+

Tải từ trang chính thức: https://www.python.org/downloads/  
Khi cài **BẮT BUỘC** tích chọn ✅ **"Add Python to PATH"**.

Kiểm tra sau khi cài:
```powershell
python --version
# Python 3.10.x hoặc cao hơn
```

### Bước 2.2: Clone Mã Nguồn

```powershell
git clone https://github.com/92phannhung-sudo/VietAnh.git
cd VietAnh
```

### Bước 2.3: Tạo Virtual Environment & Cài Thư Viện

```powershell
python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

> **⚠️ LƯU Ý VỀ PyAudio TRÊN WINDOWS:**  
> Nếu `pip install pyaudio` báo lỗi thiếu `portaudio.h`, cài bản wheel dựng sẵn:
> ```powershell
> pip install pipwin
> pipwin install pyaudio
> ```
> Hoặc tải file `.whl` phù hợp từ https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
>
> **Python khuyến nghị:** 3.10–3.12. Tránh 3.14+ cho đến khi các wheel (`rapidocr`, …) sẵn sàng.
>
> **macOS (dev):** xem [`docs/MACOS_SETUP.md`](MACOS_SETUP.md).

> **⚠️ LƯU Ý VỀ pyzbar TRÊN WINDOWS:**  
> Thư viện `pyzbar` yêu cầu file `libzbar-64.dll`. Nếu thiếu:  
> Tải **Visual C++ Redistributable** từ https://aka.ms/vs/17/release/vc_redist.x64.exe  
> Hoặc copy file `libzbar-64.dll` vào thư mục gốc dự án.

### Bước 2.4: Mô Hình AI Giọng Nói Tiếng Việt (sherpa-onnx Zipformer)

Ứng dụng sử dụng **sherpa-onnx Streaming ASR** với model **Zipformer Vietnamese 30M INT8** (không cần Internet khi chạy, kháng nhiễu tốt hơn Vosk).

Model đã có sẵn trong mã nguồn tại `models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/`.

Nếu thiếu, tải từ HuggingFace:
```powershell
# https://huggingface.co/hynt/Zipformer-30M-RNNT-6000h
```

Cấu trúc thư mục model:
```
VietAnh/
├── models/
│   └── sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/
│       ├── encoder.int8.onnx
│       ├── decoder.onnx
│       ├── joiner.int8.onnx
│       ├── tokens.txt
│       └── bpe.model
├── main.py
├── voice_detector.py
└── ...
```

Ứng dụng tự tìm model ở các vị trí: `models/`, thư mục gốc, hoặc `%APPDATA%\PatientCaptureApp\`.

---

## 3. KHỞI CHẠY ỨNG DỤNG

### 3.1 Chạy Từ Mã Nguồn (Developer Mode)

```powershell
cd VietAnh
.venv\Scripts\activate
python main.py
```

### 3.2 Phím Tắt & Điều Khiển Rảnh Tay

| Phím / Thao tác | Chức năng |
|---|---|
| `F1` | Bắt đầu phiên chụp mới |
| `F2` / `Ctrl + S` | Hoàn thành ca khám & lưu CSDL |
| `F5` / `Ctrl + F` | Mở Tra cứu hồ sơ bệnh nhân (Grid View) |
| `Space` | Chụp ảnh (Camera shutter) |
| `Delete` | Xóa ảnh vừa chụp (vào thùng rác tạm) |
| `F11` | Chuyển toàn màn hình / cửa sổ |
| **🦶 1 Giậm bàn đạp** | Chụp ảnh (<150ms) |
| **🦶 Giậm giữ 1.5s** | Xóa ảnh gần nhất |
| **🎙️ Nói "Chụp"** | Chụp ảnh qua giọng nói offline |
| **🎙️ Nói "Xóa"** | Xóa ảnh qua giọng nói offline |
| **🎙️ Nói "Tìm kiếm"** | Mở tra cứu hồ sơ |
| **🎙️ Nói "Hoàn thành"** | Kết thúc ca khám |

---

## 4. ĐÓNG GÓI BẢN CÀI ĐẶT OFFLINE (CHO MÁY TRẠM BỆNH VIỆN)

### Bước 4.1: Cài PyInstaller

```powershell
pip install pyinstaller
```

### Bước 4.2: Build Bản Standalone

```powershell
python build_package.py
```

Kết quả tạo ra:
```
dist/
├── PatientCaptureApp_v1.0_Offline/
│   ├── app_dist/                  <-- Bản .exe standalone (không cần Python)
│   │   ├── PatientCaptureApp.exe
│   │   ├── vosk-model-small-vn-0.4/
│   │   └── ...
│   ├── install_admin.bat          <-- Script cài đặt tự động (Run as Admin)
│   └── uninstall_admin.bat        <-- Script gỡ cài đặt
└── PatientCaptureApp_v1.0_Offline.zip  <-- File zip copy vào USB
```

### Bước 4.3: Triển Khai Tại Máy Trạm Bệnh Viện

1. Copy thư mục `PatientCaptureApp_v1.0_Offline/` hoặc file `.zip` vào USB.
2. Cắm USB vào máy trạm Windows tại phòng khám.
3. Chuột phải `install_admin.bat` → **"Run as administrator"**.
4. Script sẽ tự động:
   - Copy ứng dụng vào `C:\Program Files\PatientCaptureApp\`
   - Bảo vệ CSDL cũ tại `%APPDATA%\PatientCaptureApp\` (không ghi đè)
   - Tạo Shortcut trên Desktop & Start Menu

---

## 5. CẤU TRÚC DỮ LIỆU TRÊN WINDOWS

```
%APPDATA%\PatientCaptureApp\
├── app.db                         <-- CSDL SQLite (patients, photos, audit_logs, staff)
├── config.json                    <-- Cấu hình ứng dụng (camera, mic, pedal key, theme)
├── vosk-model-small-vn-0.4\      <-- Mô hình AI giọng nói (nếu giải nén ở đây)
├── photos\                        <-- Thư mục lưu ảnh bệnh nhân
│   ├── BN2026-0001\
│   ├── BN2026-0002\
│   └── ...
└── logs\
    └── app.log                    <-- Log xoay vòng (10MB x 10 = max 100MB)
```

> **🔒 BẢO MẬT:** Toàn bộ dữ liệu bệnh nhân lưu trữ 100% offline tại máy trạm. Khuyến cáo bật **BitLocker** trên ổ đĩa chứa `%APPDATA%` theo chuẩn HIPAA.

---

## 6. XỬ LÝ SỰ CỐ THƯỜNG GẶP

### 6.1 PyAudio không cài được
```powershell
# Cách 1: Dùng pipwin
pip install pipwin && pipwin install pyaudio

# Cách 2: Tải wheel thủ công
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
pip install PyAudio-0.2.14-cp310-cp310-win_amd64.whl
```

### 6.2 pyzbar báo lỗi "FileNotFoundError: libzbar-64.dll"
- Cài Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
- Hoặc copy `libzbar-64.dll` vào thư mục gốc dự án.

### 6.3 Camera không nhận
- Kiểm tra Camera trong **Device Manager** > Imaging devices.
- Đảm bảo chỉ 1 ứng dụng truy cập camera cùng lúc.
- Thử đổi `camera_index` trong Tab Cài đặt (`F4`).

### 6.4 Bàn đạp chân không phản hồi
- Kiểm tra bàn đạp trong **Device Manager** > HID Keyboard Devices.
- Mặc định gán phím `F13`. Có thể đổi trong cài đặt (`trigger_key`).
- Nếu phần mềm Antivirus chặn keyboard hook, ứng dụng tự động dùng Qt `keyPressEvent` fallback (cửa sổ phải đang được focus).

### 6.5 Giọng nói không nhận diện (sherpa-onnx)
- Kiểm tra Microphone đã được chọn đúng trong Tab Cài đặt.
- Đảm bảo thư mục `models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/` tồn tại và chứa đủ file `encoder.int8.onnx`, `decoder.onnx`, `joiner.int8.onnx`, `tokens.txt`.
- Kiểm tra thanh Volume Gauge trên giao diện (phải nhảy khi nói).
- Nói rõ ràng, cách micro 30-50cm: *"Chụp"*, *"Xóa"*, *"Tìm kiếm"*, *"Mở phiên"*, *"Bắt đầu chụp"*, *"Hoàn thành"* / *"Kết thúc phiên"*.
- Năm sinh bị ASR cắt (vd. *"một chín chín"*): nói thêm chữ số cuối (*"chín"* → 1999). Hệ thống không tự pad thành 1990.
- Nếu môi trường ồn, cài thêm `rapidfuzz` để bật fuzzy matching: `pip install rapidfuzz`

### 6.6 Ứng dụng khởi động chậm lần đầu
- Lần chạy đầu tiên, sherpa-onnx cần 2-3 giây để nạp Zipformer model vào RAM (~30MB). Các lần sau sẽ nhanh hơn.
- Nếu model chưa có, ứng dụng hiển thị trạng thái **"Model missing"** — cần tải model theo Bước 2.4.
