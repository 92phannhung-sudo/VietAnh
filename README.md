# OFFLINE PATIENT PHOTO CAPTURE SYSTEM (HỆ THỐNG CHỤP ẢNH BỆNH ÁN)

Phần mềm desktop dành cho khoa/phòng khám (Phục hồi chức năng, Da liễu, Tai Mũi Họng): chụp ảnh bệnh nhân rảnh tay qua **bàn đạp chân**, **giọng nói offline (sherpa-onnx)**, hoặc phím tắt; phân loại theo Mã Bệnh Án và ghi audit.

**Phiên khám (v1):** F1 mở → F5/barcode lưới hồ sơ → F2 khóa & chụp → pedal chỉ chụp → F4 Standby.  
Spec: [`docs/SPEC_HANDS_FREE_SESSION_V1.md`](docs/SPEC_HANDS_FREE_SESSION_V1.md) · Hướng dẫn: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) · Glossary: [`CONTEXT.md`](CONTEXT.md).

---

## Quick Start

### Windows (máy trạm bệnh viện)
```powershell
.venv\Scripts\python main.py
```
Cài đặt đầy đủ: [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md).

### macOS (dev / smoke)
```bash
source .venv/bin/activate
python main.py
```
Chi tiết quyền Camera / Accessibility: [`docs/MACOS_SETUP.md`](docs/MACOS_SETUP.md).

---

## Yêu cầu phần cứng (khảo sát)

* **OS sản phẩm:** Windows 10/11 x64 (offline / intranet).
* **Camera:** Logi Webcam C920e (USB UVC, 1080p) hoặc tương thích.
* **Bàn đạp:** PCSensor USB FootSwitch (VID `3553`, PID `B001` — thường gán `F13`).
* **Microphone:** mic webcam hoặc Realtek HD Audio.
* **ASR:** sherpa-onnx Zipformer VI INT8 (`models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/`).

---

## Chỉ mục tài liệu

| Tài liệu | Nội dung |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | Glossary miền + lifecycle phiên + coercion demography / ASR năm sinh |
| [`docs/SPEC_HANDS_FREE_SESSION_V1.md`](docs/SPEC_HANDS_FREE_SESSION_V1.md) | PRD / AC Hands-Free Session v1 |
| [`docs/PATIENT_SESSION_CONTROLLER_SPEC.md`](docs/PATIENT_SESSION_CONTROLLER_SPEC.md) | Hợp đồng event / view / effect |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Hướng dẫn bác sĩ & vận hành Tab 1–4 |
| [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md) | Cài đặt Windows offline |
| [`docs/MACOS_SETUP.md`](docs/MACOS_SETUP.md) | Chạy / smoke trên macOS |
| [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) | Đặc tả barcode / trace |
| [`docs/ACTION_MAPPING_SPEC.md`](docs/ACTION_MAPPING_SPEC.md) | Action mapping & pedal FSM |
| [`docs/DESIGN.md`](docs/DESIGN.md) / [`docs/ADR.md`](docs/ADR.md) | Kiến trúc & quyết định |
| [`docs/adr/0002-patient-session-controller-single-handle.md`](docs/adr/0002-patient-session-controller-single-handle.md) | ADR Design A single `handle` |
| [`docs/superpowers/plans/WORK_LOG.md`](docs/superpowers/plans/WORK_LOG.md) | Nhật ký phiên làm việc |

> Một số doc cũ (`UI_UX_FLOW.md`, `TECHNICAL_SPEC.md`, phần Vosk trong ADR) có thể **superseded** bởi Hands-Free Session v1 + sherpa-onnx — ưu tiên bảng trên.

---

## Bản đồ mã nguồn (rút gọn)

* **`main.py`** — MainWindow, wiring session / camera / voice / Tab Cài đặt.
* **`src/patient_session_controller.py`** — FSM phiên (Qt-free).
* **`src/session_effect_applier.py`** — Effect → callback shell.
* **`src/ui_clinical_cockpit.py`** — Tab 1 Cockpit + panel camera theo phase.
* **`src/patient_voice_parser.py`** / **`voice_detector.py`** — demography giọng + keyword.
* **`src/patient_search_service.py`** / **`src/ui_patient_grid.py`** — F5 lưới hồ sơ.
* **`database.py`**, **`barcode_parser.py`**, **`pedal_gesture_fsm.py`**, **`config.py`**.

Dữ liệu runtime: Windows `%APPDATA%\PatientCaptureApp\` · macOS `~/Library/Application Support/PatientCaptureApp/`.
