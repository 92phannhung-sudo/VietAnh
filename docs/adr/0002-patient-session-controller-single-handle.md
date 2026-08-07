# ADR 0002: PatientSessionController — một cửa `handle(event)`

* **Trạng thái:** Accepted  
* **Ngày quyết định:** 2026-08-07  

Sau grilling Voice Intake Mode (Standby → Intake → Ready → F2 Locked Capture → F4 Standby; pattern-only; cấm Mã BN từ giọng; pedal chỉ chụp; barcode không tự chụp; lexicon global Settings), cần một module sở hữu toàn bộ FSM và định tuyến đa kênh. Đã so sánh bốn hình dạng interface (minimal `handle`, command-bus linh hoạt, sáu verb happy-path, FSM `dispatch`+snapshot) và **chọn Design A: một phương thức công khai `handle(SessionEvent) → SessionOutcome`**.

Caller (MainWindow, barcode thread, pedal, ASR, Cockpit) chỉ gửi event tagged-union và áp `view` + `effects`. Không expose `start_session` / `begin_capture` / `on_voice` riêng — tránh lệch hành vi giữa kênh và tránh UI tự đoán phase.

**Bổ sung từ các phương án khác (không phá A):** `SessionView.affordances` (F2 enable, pedal_armed, voice_mode, editable fields) để UI bind đèn/nút; `Effect` có tên rõ (`POWER_DEVICES_ON/OFF`, `CAPTURE_FRAME`, `PERSIST_AND_CLEAR`, `WARN`, …) để vòng `apply` kỷ luật.

## Considered options

| Option | Lý do không chọn làm bề mặt chính |
|---|---|
| B — Command bus + policy ports | Linh hoạt thừa cho một shell Qt; học phí cao |
| C — Sáu verb đặt tên cử chỉ | Discoverability tốt nhưng dễ phình method và lệch với voice routing |
| D — `dispatch` + `state` + `subscribe` | Gần A về tinh thần một cửa; A gọn hơn (một method), subscribe/Qt Signal để ở lớp adapter |

## Consequences

- `MultiModalDispatcher` trở thành adapter tạo `SessionEvent`, không còn là nơi giữ lifecycle.
- Rule miền (gate 4 field, khóa demography, ignore barcode mid-session) chỉ sửa trong controller — một nơi test bảng chuyển trạng thái.
- MainWindow phải có vòng `apply(effects)` đầy đủ; quên một effect = lệch thiết bị/UI.
- Thêm hành vi mới = thêm variant event / effect, không thêm method public.
