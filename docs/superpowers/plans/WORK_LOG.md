# NHẬT KÝ HOẠT ĐỘNG DỰ ÁN (WORK LOG)
*Cập nhật tự động bởi Agent*

## 2026-09-07 — Triển khai bố cục ảnh hàng ngang (Side-by-Side) & Tối ưu báo cáo đạt đúng 20 trang
- **Trạng thái chung:** Hoàn thành (Cổng 4: VERIFICATION & HANDOFF)
- **Nhánh:** `main`
- **Nhiệm vụ:** Gom các cụm 2-3 ảnh vào chung 1 hàng (side-by-side) bằng bảng ẩn viền và tinh chỉnh bố cục, giãn dòng 1.15 lines để toàn bộ tài liệu M7 đạt chính xác 20 trang theo Nghị định 30/2020/NĐ-CP.

### 1. Các việc đã hoàn thành
- [x] **Task 1: Tạo bảng ảnh hàng ngang ẩn viền (`insert_side_by_side_image_table`):**
  - Tạo bảng 2 hàng không viền (`tcBorders` và `tblBorders` đều đặt `none`), có thuộc tính `cantSplit` chống ngắt trang.
  - Cụm Ảnh 3 (2 ảnh: Ảnh 3a webcam và Ảnh 3b vị trí gắn hộp) xếp cạnh nhau trên 1 hàng (mỗi ảnh 5.5cm).
  - Cụm Ảnh 7 (3 ảnh: Ảnh 7a tiếp nhận, Ảnh 7b giao diện, Ảnh 7c bằng chứng số) xếp cạnh nhau trên 1 hàng (mỗi ảnh 4.8cm).
  - Điều chỉnh kích thước các ảnh đơn (Ảnh 1, 2, 4, 5, 6) từ 8.5–9cm về 5.5–6.5cm để cân đối với văn bản.
  - Commit: `4e70c82`.
- [x] **Task 2: Tinh chỉnh Typography và Spacing hướng tới mục tiêu đúng 20 trang:**
  - Áp dụng giãn dòng `1.15 lines` (chuẩn Nghị định 30/2020/NĐ-CP).
  - Spacing after đoạn thân bài: `Pt(1.5)`; khoảng cách trước/sau đề mục: `Pt(4)/Pt(2)`.
  - TDD: Cập nhật unit test `test_typography` và `test_insert_side_by_side_image_table` (Pass 6/6 tests).
  - Commit: `d69c0df`.
- [x] **Task 3: Tái tạo tài liệu M7 Word, Xác minh 20 trang và Bàn giao:**
  - Chạy `python3 scripts/format_m7_document.py` cập nhật trực tiếp `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx`.
  - Đối soát xuất PDF và kiểm tra `pdfinfo`: Số trang đạt chính xác **20 trang**.
  - Trang 20 kết thúc trọn vẹn gồm 2 đoạn kết luận Mục 5 + Ngày tháng địa danh + Bảng chữ ký tác giả.
  - Kiểm thử toàn bộ dự án: 63/63 tests PASS (3 skipped macOS).

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- Không phát sinh nợ kỹ thuật mới.

---

## 2026-09-07 — Khắc phục triệt để lỗi giãn cách chữ (Stretched Justification) tại Mục 2.3.4
- **Trạng thái chung:** Hoàn thành (Cổng 4: VERIFICATION & HANDOFF)
- **Nhánh:** `main`
- **Nhiệm vụ:** Sửa lỗi các tiêu đề "Bước 1", "Bước 2", ..., "Bước 7" trong mục 2.3.4 bị dãn khoảng cách chữ rất rộng do soft break `\n` / `<w:br/>` trong đoạn căn lề `JUSTIFY`. Xuất bản file `.docx` chuẩn mực theo yêu cầu người dùng.

### 1. Các việc đã hoàn thành
- [x] **Điều tra nguyên nhân gốc rễ (Root Cause Investigation):** Phát hiện trong file Word gốc, 7 bước quy trình được lưu trong cùng 1 paragraph với nội dung mô tả qua ký tự ngắt dòng mềm `<w:br/>` (`Shift+Enter`). Khi áp dụng `WD_ALIGN_PARAGRAPH.JUSTIFY`, Word căn đều toàn dòng cho dòng trước `\n`, kéo dãn các từ trong tiêu đề "Bước X..." ra toàn trang.
- [x] **Giải pháp kỹ thuật:**
  - Phát triển hàm `split_soft_break_paragraphs(doc: Document)` tự động phân tách các đoạn chứa `\n` thành các paragraph độc lập.
  - Cập nhật `is_title_or_heading`: Nhận diện mẫu `^Bước\s+\d+\.` là level 5 (tiêu đề bước quy trình).
  - Cập nhật `apply_typography`: Tiêu đề bước được căn lề trái (`LEFT`), in đậm, thụt lề đầu dòng 1.27cm, `keep_with_next = True`. Đoạn mô tả bên dưới được căn đều hai bên (`JUSTIFY`), chữ thường 13pt, thụt lề 1.27cm.
- [x] **Quy trình TDD:**
  - Viết test case `test_split_soft_break_paragraphs` trong `tests/test_format_m7_document.py` (Red -> Green).
  - Chạy toàn bộ test suite: 62/62 tests PASS (3 skipped do PySide6 trên macOS).
- [x] **Xuất bản & Kiểm tra:**
  - Chạy `python3 scripts/format_m7_document.py` cập nhật trực tiếp `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx`.
  - Xác minh bằng `docx` MCP (`find_text_in_document`, `get_paragraph_text_from_document`): Xác nhận Bước 1 đến Bước 7 đã thành các paragraph độc lập, căn trái, in đậm, không còn bất kỳ ký tự `\n` hay `<w:br/>` nào trong toàn bộ tài liệu.

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- Không có nợ kỹ thuật phát sinh.

---

## 2026-09-07 — Chuẩn hóa tài liệu M7 Thuyết minh Công trình và Chèn ảnh theo NĐ 30/2020
- **Trạng thái chung:** Hoàn thành (Cổng 4: VERIFICATION & HANDOFF)
- **Nhánh:** `main`
- **Nhiệm vụ:** Chuẩn hóa lề trang, typography, bảng biểu, làm sạch số liệu, chèn 10 ảnh thực tế và xuất bản bản Word/PDF hoàn chỉnh.

### 1. Các việc đã hoàn thành
- [x] Task 1: Thiết lập cấu trúc trang in A4 và Typography theo Nghị định 30 (Top/Bottom 20mm, Left 30mm, Right 15mm; Times New Roman 13pt; indent 1.27cm; line spacing 1.2). Commit: `1e255ea`.
- [x] Task 2: Chuẩn hóa toàn bộ bảng biểu (viền đơn 0.5pt, header xám 5%, căn lề số tiền sang phải) và làm sạch số liệu (fix lỗi `..` trong đơn giá/thành tiền). Commit: `ad7b09d`.
- [x] Task 3: Chèn đầy đủ 10 hình ảnh thực tế và chú thích chuẩn in nghiêng 11pt căn giữa (bao gồm Ảnh 1, 2, 3a, 3b, 4, 5, 6, 7a, 7b, 7c). Commit: `eb01b03`.
- [x] Task 4: Chạy toàn trình tạo file Word `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx` và xuất bản PDF `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.pdf` qua LibreOffice (24 trang).
- [x] Kiểm thử toàn bộ dự án: `61/61 tests OK` (3 skipped do PySide6 trên macOS).

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- Không phát sinh nợ kỹ thuật mới. Module `scripts/format_m7_document.py` độc lập, tái sử dụng được.

---
- **Trạng thái chung:** Hoàn thành — commit vào `main` + push
- **Nhánh:** `main`
- **Nhiệm vụ:** Smoke macOS, sửa regression năm sinh ASR, panel lỗi camera, chữ `"None"` trên ô Mã BN, polish Tab Cài đặt (macOS layout)

### 1. Các việc đã hoàn thành

#### Runtime / nền tảng
- [x] Chạy `main.py` trên macOS (Python 3.12 venv); log `/tmp/patient_capture_run.log`
- [x] `config.get_user_data_dir()` đã dùng `~/Library/Application Support/PatientCaptureApp/` (commit trước `f830865`)
- [x] Ghi nhận giới hạn macOS: Camera cần quyền Privacy; pedal `keyboard` → OSError 13 (Accessibility); font "Segoe UI" alias

#### Voice — năm sinh bị cắt số cuối
- [x] Bỏ pad `199 → 1990` trong `_normalize_year` (`src/patient_voice_parser.py`)
- [x] `incomplete_birth_year_prefix` + `complete_truncated_birth_year`; `voice_detector` giữ `_pending_year_prefix`
- [x] Filter nhiễu ASR: `ờ`, `không`, `trong`, `<`, …
- [x] Siết keyword: `"mở phiên"` / `"bắt đầu chụp"` (tránh khớp nhầm `"bắt đầu"` đơn)
- [x] Tests: `tests/test_patient_voice_parser.py`

#### UI / session demography
- [x] Bug ô Mã BN hiện `"None"`: `str(None)` trong `_apply_field` → `_clean_str`; sanitize `_ui_text` khi bind Cockpit
- [x] Regression: `test_clearing_patient_id_does_not_store_literal_none`
- [x] Panel camera: Standby text **không** đè khi đang phiên; lỗi HW hiện đỏ (`set_camera_hardware_error` / `refresh_camera_panel`); `main.handle_thread_error` đẩy lỗi camera

#### Tab Cài đặt (macOS)
- [x] `QScrollArea` + form row wrapper + bảng settings resize modes; QSS ComboBox/TableWidget dark+light

#### Tài liệu
- [x] `CONTEXT.md`, `USER_GUIDE.md`, `PATIENT_SESSION_CONTROLLER_SPEC.md`, `WINDOWS_SETUP.md`, `MACOS_SETUP.md`, `README.md`, WORK_LOG này

### 2. Kiểm thử
- Unittest session + voice parser (trước commit)
- Smoke: F1 / voice họ tên–năm sinh–GT; camera fail đúng panel lỗi (không còn copy Standby khi Locked)

### 3. Nợ kỹ thuật còn lại
- [ ] Seed operator `"BS. Nguyễn Văn A"` / `NV001` vẫn hardcode khởi tạo UI (demo) — không phải bug `str(None)`
- [ ] Legacy `load_patient` / grid card f-string vẫn có thể hiện `None` nếu dict thiếu field
- [ ] Pedal trên macOS cần Accessibility; camera cần TCC Camera
- [ ] Các nợ cũ từ 2026-08-07 (dead `build_tab1_capture`, MultiModalDispatcher legacy, …)

### 4. Tham chiếu nhanh
- Spec session: `docs/SPEC_HANDS_FREE_SESSION_V1.md`
- macOS: `docs/MACOS_SETUP.md`

---

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
