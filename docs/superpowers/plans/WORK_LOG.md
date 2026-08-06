# NHẬT KÝ HOẠT ĐỘNG DỰ ÁN (WORK LOG)
*Cập nhật tự động bởi Agent*

## 2026-08-06 - Phiên làm việc lúc 20:00–20:31
- **Trạng thái chung:** Hoàn thành
- **Nhiệm vụ đang thực hiện:** Tích hợp giao diện mới + Chuyển đổi Voice AI Stack

### 1. Các việc đã hoàn thành

- [x] **Commit `4c5bed6`** — Viết `docs/WINDOWS_SETUP.md` hướng dẫn cài đặt & triển khai Windows offline đầy đủ 6 phần (Phần cứng, Cài đặt, Khởi chạy, Đóng gói, Cấu trúc dữ liệu, Xử lý sự cố). Cập nhật link vào `README.md`.

- [x] **Commit `7534e0e`** — Thay thế Tab 1 cũ (`build_tab1_capture`) bằng `ClinicalCockpitWidget` mới trong `main.py`:
  - Tạo `self.cockpit_widget = ClinicalCockpitWidget(...)` trong `setup_ui()`
  - Đấu nối 5 signal: `capture_requested`, `delete_last_requested`, `complete_session_requested`, `start_session_requested`, `patient_loaded`
  - Thêm 2 handler: `_on_cockpit_start_session()`, `_on_cockpit_patient_loaded()`
  - Thêm `patient_loaded = Signal(dict)` vào `src/ui_clinical_cockpit.py`
  - Khởi tạo safe defaults cho legacy widget references (`lbl_scan_status`, `txt_patient_id`, `voice_gauge`, v.v.)

- [x] **Commit `30e39c1`** — Fix 3 gap từ code review:
  - `src/patient_search_service.py`: sqlite3 `with` context manager (tránh connection leak)
  - `src/multimodal_dispatcher.py`: Xóa PySide6 mock fallback, thay if/elif chains bằng dict lookup (`VOICE_MAP`, `PEDAL_MAP`, `KEY_MAP`)
  - `tests/test_multimodal_dispatcher.py`: `@skipUnless(HAS_PYSIDE6)` guard cho macOS

- [x] **Commit `cf8139a`** — **CHUYỂN ĐỔI STACK VOICE AI: Vosk → sherpa-onnx**:
  - Viết lại hoàn toàn `voice_detector.py`: sherpa-onnx `OnlineRecognizer.from_transducer`
  - Model: `models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/` (encoder.int8.onnx + decoder.onnx + joiner.int8.onnx + tokens.txt)
  - Endpoint detection cho streaming real-time keyword triggering
  - RapidFuzz fuzzy matching fallback (≥75% similarity) cho môi trường nhiễu
  - Cập nhật `config.py`: `vosk_model_path` → `sherpa_model_dir`
  - Cập nhật `requirements.txt`: `vosk` → `sherpa-onnx>=1.10.0` + `numpy` + `rapidfuzz`
  - Cập nhật `main.py`: loại bỏ Vosk download prompt, cập nhật hardware info text
  - Cập nhật `docs/WINDOWS_SETUP.md`: model mới, troubleshooting mới

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- [ ] ponytail: `demo_voice_agent_offline.py` vẫn import `faster_whisper` + `llama_cpp` — file demo cũ cần xóa hoặc chuyển sang sherpa-onnx
- [ ] ponytail: `docs/RESEARCH_VOICE_AI_OFFLINE.md` vẫn mô tả stack Faster-Whisper + Qwen cũ — cần cập nhật hoặc đánh dấu deprecated
- [ ] ponytail: `build_tab1_capture()` (~130 dòng) trong `main.py` giờ là dead code — cần xóa
- [ ] ponytail: `models/campp.onnx` + `models/doctor_voiceprint.npy` — chưa rõ có được tích hợp vào speaker verification hay chưa

### 3. Kiểm thử
- `py_compile` main.py, voice_detector.py, config.py, src/*.py → ✅ PASS
- `unittest discover -s tests` → ✅ 4 tests (1 OK + 3 skipped do macOS không có PySide6)
- Git push `origin/main` → ✅ Thành công tất cả 4 commits
