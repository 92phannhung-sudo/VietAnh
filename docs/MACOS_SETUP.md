# HƯỚNG DẪN CHẠY TRÊN macOS (DEV / SMOKE)
# 354 EMR Workstation

> Mục tiêu sản phẩm chính vẫn là **Windows offline tại bệnh viện**. Tài liệu này phục vụ phát triển và kiểm thử trên Mac.

Cập nhật: 2026-08-09

---

## 1. Yêu cầu

| Thành phần | Ghi chú |
|---|---|
| **Python** | **3.12.x** khuyến nghị (`rapidocr` / một số wheel chưa sẵn trên 3.14) |
| **Homebrew** | `portaudio`, `zbar` (PyAudio + pyzbar) |
| **Model giọng** | `models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/` |
| **Dữ liệu app** | `~/Library/Application Support/PatientCaptureApp/` (`config.get_user_data_dir`) |

---

## 2. Cài đặt nhanh

```bash
brew install portaudio zbar
cd /path/to/VietAnh   # hoặc repo local
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Log chạy thử (tuỳ chọn):

```bash
python main.py 2>&1 | tee /tmp/patient_capture_run.log
```

---

## 3. Quyền hệ thống (bắt buộc cho smoke đầy đủ)

| Tính năng | Quyền macOS | Triệu chứng nếu thiếu |
|---|---|---|
| **Camera** | System Settings → Privacy & Security → Camera → Terminal/Cursor/Python | OpenCV: *not authorized*; panel đỏ “LỖI PHẦN CỨNG” khi phiên mở |
| **Microphone** | Privacy → Microphone | Voice thread không nhận âm |
| **Bàn đạp / hotkey toàn cục** | Privacy → Accessibility (và đôi khi Input Monitoring) cho app chạy Python | `keyboard` → `OSError: Error 13 - Must be run as administrator` |

Gợi ý OpenCV khi không muốn dialog auth từ thread phụ (chỉ dev):

```bash
export OPENCV_AVFOUNDATION_SKIP_AUTH=1
```

---

## 4. Lưu ý UI / ASR trên Mac

- Font QSS có thể cảnh báo thiếu **Segoe UI** (Windows) — chỉ chậm alias, không chặn chạy.
- Tab **Cài đặt** đã bọc `QScrollArea` + hàng form để layout không vỡ trên macOS.
- Voice: nếu năm sinh bị cắt 3 số, nói thêm chữ số cuối (xem `USER_GUIDE.md` / `CONTEXT.md`).
- Pedal thật thường chỉ smoke được trên Windows + PCSensor; trên Mac ưu tiên Space / giọng `"chụp"`.

---

## 5. Kiểm thử nhanh

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Smoke thủ công: F1 → nói họ tên / năm sinh / giới tính → nhập Mã BN → F2 → Space chụp → F4.
