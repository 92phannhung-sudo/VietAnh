# NHẬT KÝ HOẠT ĐỘNG DỰ ÁN (WORK LOG)
*Cập nhật tự động bởi Agent*

## 2026-08-07 - Phiên làm việc lúc ~20:00–22:12
- **Trạng thái chung:** Hoàn thành — đã merge vào `main`
- **Nhánh:** `feat/hands-free-session` → fast-forward merge `main` @ `a43378b`
- **Nhiệm vụ:** Triển khai **Hands-Free Session v1** (Design A — `PatientSessionController.handle(event)`)

### 1. Các việc đã hoàn thành

#### Spec & tài liệu
- [x] **`docs/SPEC_HANDS_FREE_SESSION_V1.md`** — PRD, AC, §12 UX conflict resolutions
- [x] **`docs/PATIENT_SESSION_CONTROLLER_SPEC.md`** — hợp đồng event/view/effect + search + Tab 2
- [x] **`docs/adr/0002-patient-session-controller-single-handle.md`** — ADR Design A single door
- [x] **`docs/superpowers/plans/2026-08-07-hands-free-session.md`** — plan 9 task (TDD)
- [x] **`CONTEXT.md`** — glossary Voice Intake, lifecycle F1→F4, barcode→lưới, Tab 2 rules
- [x] **`docs/USER_GUIDE.md`** — luồng Tab 1 mới (F1/F2/F4/F5, pedal chỉ chụp, không PDF)
- [x] Banner *Superseded* trên `docs/UI_UX_FLOW.md`, `docs/TECHNICAL_SPEC.md`; blurb trên `README.md`

#### Domain (Qt-free)
- [x] **`src/patient_session_controller.py`** — FSM Standby/Intake/Ready/Locked/Correction; events `Hotkey`, `VoiceUtterance`, `BarcodeScan`, `PedalGesture`, `UiFieldEdit`, `LoadRecord`, `SearchFilterEdit`, …
- [x] **`src/session_effect_applier.py`** — map `Effect` → callback MainWindow
- [x] **`src/voice_lexicon_store.py`** — load/save `voice_lexicon.json` (global Settings)
- [x] Tests: **`test_patient_session_controller.py`** (25), **`test_session_effect_applier.py`**, **`test_voice_lexicon_store.py`**

#### Shell / UI wiring
- [x] **`main.py`** — `_dispatch_session`, `SessionEffectApplier`, hotkeys F1/F2/F4/F5/Space/Delete, pedal → `PedalGesture`, barcode → `BarcodeScan`, voice → `VoiceUtterance`
- [x] **`src/ui_clinical_cockpit.py`** — `apply_session_view`, nút F2/F4 động, badge gate, confirm F1 khi còn ảnh, pill Locked trên status bar, hoàn tác xóa 5s
- [x] **`src/patient_search_service.py`** — exact ID, `recent(50)`, schema `id/name` + `patient_id/full_name`
- [x] **`src/ui_patient_grid.py`** — recent/filtered, 0-hit confirm BN mới, Enter/Space 1-hit, voice filter hooks
- [x] Tab 2: bỏ PDF/F10, xóa ảnh có confirm, chặn “Mở Tab Chụp” BN khác, barcode lọc browse

#### Commit & merge
- [x] **`635704e`** — `feat(session): wire hands-free PatientSessionController end-to-end`
- [x] Bugbot review (subagent) — 5 findings
- [x] **`a43378b`** — `fix(session): route eventFilter through controller and close search on F2`
- [x] Push `origin/feat/hands-free-session` + **fast-forward merge `main`** + push `origin/main`

### 2. Bugbot fixes (`a43378b`)
| Mức | Vấn đề | Sửa |
|---|---|---|
| High | `eventFilter` gọi thẳng `trigger_photo_capture`, bypass FSM | Route qua `_dispatch_session(PedalGesture/Hotkey)`; bỏ F5 khỏi pedal |
| Medium | Tab 2 barcode không lọc browse | `txt_search` + `load_history_records()` |
| Medium | F2 không đóng dialog F5 | `_begin_capture` phát `CLOSE_SEARCH_GRID` |
| Medium | Correction khóa sau 1 field | Chỉ Locked khi hết `_correction_fields` |
| Low | `validate_inputs` ghi đè badge SessionView | Gỡ `textChanged`; badge qua `apply_session_view` |

### 3. Kiểm thử
- `python3 -m unittest discover -s tests` → ✅ **32 tests OK** (3 skipped PySide6 trên macOS)
- Smoke domain: F1 → gate 4 field → F2 → pedal/voice chụp → F4 Standby

### 4. Nợ kỹ thuật còn lại
- [ ] `build_tab1_capture()` trong `main.py` — dead code (~130 dòng)
- [ ] `MultiModalDispatcher` / `action_registry` — một phần legacy vẫn tồn tại; cockpit `on_action_triggered` chưa gỡ hết
- [ ] `demo_voice_agent_offline.py`, `docs/RESEARCH_VOICE_AI_OFFLINE.md` — stack cũ
- [ ] Smoke UI thật trên Windows (PySide6): F1→F5→F2→pedal→F4 end-to-end
- [ ] `PatientSearchService` test DB dùng schema `patient_id/full_name`; production DB dùng `id/name` — service đã dual-schema nhưng cần integration test trên `app.db` thật

### 5. Tham chiếu nhanh
- Spec chính: `docs/SPEC_HANDS_FREE_SESSION_V1.md`
- API domain: `docs/PATIENT_SESSION_CONTROLLER_SPEC.md`
- Plan: `docs/superpowers/plans/2026-08-07-hands-free-session.md`

---

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
