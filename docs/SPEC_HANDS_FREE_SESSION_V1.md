# SPEC — Phiên khám rảnh tay & chống lẫn hồ sơ (v1)

> **Trạng thái:** Draft sau grilling (2026-08-07)  
> **Phạm vi:** Vòng đời phiên, Voice Intake Mode, tìm kiếm hồ sơ, Tab thư mục, hợp đồng `PatientSessionController`  
> **Glossary:** `CONTEXT.md` · **ADR:** `docs/adr/0002-patient-session-controller-single-handle.md` · **API chi tiết:** `docs/PATIENT_SESSION_CONTROLLER_SPEC.md`  
> **Ngoài phạm vi v1:** Xuất PDF/F10 · Override lexicon theo nhân viên · Xóa cả thư mục BN

---

## 1. Problem Statement

Bác sĩ tại máy trạm EMR (BV 354) cần **chụp ảnh bệnh án rảnh tay** (pedal + giọng + phím), nhưng hiện tại:

1. Giọng nói vừa điền form vừa nhận lệnh — tiếng ồn / nói chuyện dễ **ghi đè họ tên** khi đã nhập xong.  
2. Dễ **lẫn hồ sơ** nếu quét nhầm phiếu hoặc đổi BN giữa lúc đang chụp.  
3. Mapping cử chỉ / phím / tài liệu **lệch nhau** (F2 từng là hoàn thành, pedal từng đa cử chỉ).  
4. F5 tìm hồ sơ và Tab Thư mục **dễ bị hiểu trùng vai trò**.

Cần một vòng đời phiên rõ ràng, khóa demography khi chụp, và một module quyết định tập trung để mọi kênh hành xử giống nhau.

---

## 2. Solution (góc nhìn người dùng)

Một ca khám với **một Bệnh Nhân**:

1. **F1** — mở phiên (bật cam/mic/pedal), vào nhập liệu.  
2. **Nhập hồ sơ** — quét mã / F5 / gõ / nói (pattern) đến đủ 4 field. Quét mã **mở lưới tìm**, chọn dòng mới vào form.  
3. **F2 / nói “bắt đầu chụp” / nút** — khóa hồ sơ, bắt đầu chụp.  
4. **Pedal / Space / “chụp”** — chụp ảnh; **Delete / “xóa”** — xóa ảnh gần nhất (không dùng pedal để xóa).  
5. Có thể **sửa hồ sơ** bằng lệnh/UI rồi khóa lại; **không** đổi sang BN khác.  
6. **F4 / “kết thúc” / “chuyển bệnh nhân mới”** — lưu, tắt thiết bị (Standby). BN sau phải F1 lại.  
7. Tab Thư mục — xem/xóa từng ảnh (confirm); **không** PDF; **không** thay F5.

Mọi quyết định “được làm gì lúc này” đi qua **`PatientSessionController.handle(event)`** (Design A).

---

## 3. Actors

| Actor | Vai trò |
|---|---|
| Bác sĩ / KTV | Vận hành ca khám rảnh tay |
| Admin/IT | Cấu hình lexicon giọng **toàn cục** (Tab Cài đặt) |
| Hệ thống | Camera, mic ASR, pedal HID, barcode trên stream |

---

## 4. User Stories

1. As a bác sĩ, I want mở phiên bằng F1, so that thiết bị chỉ bật khi bắt đầu khám.  
2. As a bác sĩ, I want quét barcode để ra lưới hồ sơ đúng mã, so that tôi chọn đúng BN trước khi chụp.  
3. As a bác sĩ, I want F5 hiện hồ sơ gần đây rồi lọc, so that tìm BN cũ nhanh.  
4. As a bác sĩ, I want khi không có hồ sơ thì confirm dùng mã đó cho BN mới, so that không bịa demography.  
5. As a bác sĩ, I want nói họ tên / năm sinh / giới tính theo mẫu, so that điền form không cần chuột.  
6. As a bác sĩ, I want giọng **không bao giờ** ghi Mã BN, so that tránh mã ASR sai.  
7. As a bác sĩ, I want đủ 4 field mới bật F2, so that không chụp thiếu định danh.  
8. As a bác sĩ, I want F2 tường minh mới bắt đầu chụp, so that tôi kiểm soát lúc khóa hồ sơ.  
9. As a bác sĩ, I want sau F2 hồ sơ khóa, so that nói ồn không đè tên.  
10. As a bác sĩ, I want pedal chỉ chụp trong lúc Locked, so that không xóa/chuyển BN nhầm bằng chân.  
11. As a bác sĩ, I want xóa ảnh bằng Delete hoặc giọng, so that vẫn sửa được ảnh sai.  
12. As a bác sĩ, I want “sửa tên” / mở khóa UI để sửa rồi tự khóa lại, so that sửa được mà không mở lung tung.  
13. As a bác sĩ, I want F4 kết thúc về Standby, so that BN sau không dính ảnh/thiết bị ca trước.  
14. As a bác sĩ, I want barcode BN khác lúc Locked bị bỏ qua, so that không đổi hồ sơ giữa chừng.  
15. As a bác sĩ, I want Tab Thư mục để xem ảnh cũ, so that đối chiếu không lẫn với F5.  
16. As a bác sĩ, I want xóa từng ảnh trên Tab Thư mục có confirm, so that dọn ảnh sai có chủ đích.  
17. As a bác sĩ, I want không xuất PDF, so that bớt bước không dùng.  
18. As an admin, I want sửa text khẩu lệnh ở Settings global, so that khớp thói quen phòng khám.  
19. As a developer, I want một `handle(event)`, so that mọi kênh không lệch rule.  
20. As a bác sĩ, I want khi lưới F5 mở thì giọng điền ô lọc, so that vẫn rảnh tay khi tìm.

---

## 5. Functional requirements

### 5.1 Vòng đời phiên & phase

| Phase | Thiết bị | Form | Chụp | Search F5 |
|---|---|---|---|---|
| Standby | Tắt | Trống / cleared | Không | Không |
| Intake | Bật | Mở | Không | Có |
| Ready | Bật | Mở; đủ 4 field | Không (chờ F2) | Có |
| Locked Capture | Bật | Khóa | Có | Không |
| Correction | Bật | Subset mở | Không | Không |

- Gate Ready: `patient_id` + `full_name` + `birth_year` + `gender`.  
- Ready → Locked: chỉ F2 / nút / giọng “bắt đầu chụp|khám”.  
- Kết thúc: F4 / “kết thúc phiên” / “hoàn thành” / “chuyển bệnh nhân mới” → persist + Standby.  
- F1 khi không Standby: về Standby (confirm UI nếu còn ảnh chưa chốt — tầng shell).

### 5.2 Demography & giọng

- Intake/Ready/Correction (field mở): **pattern-only**.  
- Locked: chỉ lexicon lâm sàng + lệnh sửa / mở lại hồ sơ.  
- `patient_id` không từ giọng.  
- Correction: sửa từng field hoặc mở lại hồ sơ (trừ Mã BN trừ quét/gõ/F5 — nhưng F5/Locked không mở search; đổi Mã BN thực tế chỉ trước Locked hoặc sau F4).

### 5.3 Tìm kiếm hồ sơ (F5)

- Chỉ Intake/Ready.  
- Vào bằng F5 / giọng tìm / **BarcodeScan**.  
- Barcode → luôn mở/cập nhật lưới, filter **exact mã**; không ghi thẳng Cockpit; không chụp.  
- Mở trống: N hồ sơ gần đây, **mới → cũ**.  
- Lọc: mã exact; tên chứa đoạn (bỏ dấu); NS/GT exact nếu có.  
- Chọn dòng: **thay toàn bộ** demography, không hỏi.  
- **1 kết quả exact:** highlight dòng duy nhất; **Enter / Space** = chọn (không bắt buộc chuột).  
- 0 kết quả + có mã: confirm → chỉ `patient_id` vào Cockpit.  
- Giọng khi lưới mở: điền filter / đóng / confirm BN mới — không ghi Cockpit.

### 5.4 Capture & xóa (Cockpit)

- Chụp: pedal (chỉ Locked) / Space / giọng “chụp”; feedback shutter + filmstrip; latency mục tiêu &lt;150ms.  
- Xóa ảnh gần nhất: Delete / giọng “xóa” (Locked); **không** pedal.  
- Xóa hết: ngoài v1 bắt buộc trừ khi đã có trong lexicon — **khuyến nghị confirm** (xem phản biện).  
- Baseline 60/40: giữ ý tưởng hiện có khi có ảnh cũ (chi tiết UI không chặn v1 session).

### 5.5 Tab Thư mục

- Browse 2 cấp; lọc local; không F5/LoadRecord.  
- Locked: xem được; “Mở Tab Chụp” BN khác = chặn.  
- Không PDF.  
- Xóa từng ảnh + confirm; không xóa cả folder.

### 5.6 Settings

- Lexicon khẩu lệnh **global** only.  
- Không per-staff override (v1).

### 5.7 Out of scope (v1)

- Xuất PDF / F10.  
- Auto-capture khi quét barcode.  
- Đổi BN giữa Locked không qua F4.  
- Pedal đa cử chỉ (xóa/xem/next).

---

## 6. Non-functional

- Offline-first; ASR sherpa-onnx (hiện trạng code).  
- Một nguồn sự thật hành vi: `PatientSessionController`.  
- Test được bằng chuỗi `SessionEvent` → assert `SessionView` / effects (không cần Qt).  
- MainWindow bắt buộc thi hành đủ `effects`.

---

## 7. Architecture / seam chính

**Seam duy nhất khuyến nghị cho rule phiên:**

```text
SessionEvent → PatientSessionController.handle → SessionOutcome{view, effects}
```

- `MultiModalDispatcher` / barcode thread / pedal → chỉ tạo event.  
- Cockpit / Tab2 / Settings → render view + apply effects / browse đĩa.  
- Search query DB: shell đọc `view.search` khi `OPEN_SEARCH_GRID` / `REFRESH_SEARCH_RESULTS`.

Chi tiết type: `docs/PATIENT_SESSION_CONTROLLER_SPEC.md`.

---

## 8. Hotkey map (v1)

| Phím | Hành động |
|---|---|
| F1 | Bắt đầu phiên / (không Standby → kết thúc về Standby) |
| F2 | Bắt đầu chụp (Ready) |
| F4 | Kết thúc phiên |
| F5 | Mở lưới tìm (Intake/Ready) |
| Space | Chụp (Locked) |
| Delete | Xóa ảnh gần nhất (Locked) |
| Esc | Thoát app (shell, có confirm) |

---

## 9. Acceptance criteria (tóm tắt)

- [ ] Standby: cam/mic/pedal off; F1 mới bật.  
- [ ] Đủ 4 field → Ready; F2 mới Locked; thiếu field F2 không vào Locked.  
- [ ] Locked: utterance không khớp lệnh không đổi `full_name`.  
- [ ] Voice không set `patient_id` trong mọi phase.  
- [ ] Barcode Intake → lưới filtered exact; chọn dòng mới có demography.  
- [ ] 1 hit exact: Enter/Space chọn được không cần chuột.  
- [ ] Barcode Locked khác ID → demography không đổi + WARN + banner giải thích.  
- [ ] Pedal ngoài Locked không chụp; Locked chỉ chụp (không xóa).  
- [ ] F4 → Standby + devices off; không PDF.  
- [ ] F1 đóng ca khi còn ảnh chưa F4 → confirm (không cúp lặng).  
- [ ] F5/LoadRecord bị từ chối ở Locked.  
- [ ] Tab2 khi Locked: pill “Đang ghi ảnh cho [BN]”; “Mở Tab Chụp” BN khác bị chặn.  
- [ ] Lưới F5 mở: badge “ĐANG TÌM HỒ SƠ”; giọng không ghi Cockpit.  
- [ ] Xóa Cockpit: toast Undo; Tab2 xóa: confirm.  
- [ ] Lexicon đổi ở Settings áp dụng không cần theo NV.  
- [ ] Bảng transition `handle` có unit test cho các dòng trên.
- [ ] `UiFieldEdit(..., None)` / xóa ô không lưu literal `"None"` trên demography.
- [ ] ASR năm sinh 3 số (*"một chín chín"*) không pad thành `1990`; chờ digit cuối hoặc re-speak đủ 4 số.
- [ ] Khi phase ≠ Standby và camera lỗi HW: UI hiện lỗi phần cứng, không hiện copy Standby “bấm F1”.

---

## 10. Implementation notes (gợi ý thứ tự)

Plan chi tiết (task/TDD/file): **`docs/superpowers/plans/2026-08-07-hands-free-session.md`**.

Tóm tắt:
1. Skeleton `PatientSessionController` + tests FSM — **đã có**.  
2. `SessionEffectApplier` + wire MainWindow.  
3. PatientGridDialog + search rules + barcode→lưới.  
4. UI §12 conflict UX.  
5. Voice → `VoiceUtterance`.  
6. Tab2: bỏ PDF; confirm xóa; chặn jump BN khác.  
7. Settings lexicon global.  
8. Dọn docs cũ.

---

## 11. Tài liệu liên quan

| File | Vai trò |
|---|---|
| `CONTEXT.md` | Glossary |
| `docs/adr/0002-…` | Quyết định Design A |
| `docs/PATIENT_SESSION_CONTROLLER_SPEC.md` | Hợp đồng event/view/effect |
| Spec này | PRD / yêu cầu sản phẩm v1 |

---

## 12. UX — giải quyết xung đột luồng (giữ rule miền)

Rule FSM / gate / barcode→lưới / pedal chỉ chụp / F4→Standby **không đổi**. Chỉ vá **nhãn, feedback, shortcut, confirm/undo**.

### 12.1 Quét mã đa nghĩa theo context

| Context | Feedback bắt buộc khi nhận mã |
|---|---|
| Intake / Ready | Banner: `Tìm hồ sơ: [MÃ] — chọn dòng để nạp` + mở/cập nhật lưới |
| Locked / Correction | Beep warn + banner: `Đang khám [A] — bỏ qua mã [B]. F4 rồi F1 để đổi BN` |
| Tab Thư mục | Banner: `Lọc thư mục: [MÃ]` (không mở F5) |

**1 hit exact trên lưới:** auto-highlight; Enter/Space = `LoadRecord` (rảnh tay, vẫn qua lưới).

### 12.2 F2 / F4 lệch thói quen

- Nút copy đầy đủ: `F2 · Bắt đầu chụp (khóa hồ sơ)` / `F4 · Kết thúc phiên (tắt thiết bị)`.  
- Màu phân vai: F2 = hành động tiến; F4 = kết thúc.  
- Optional: tip một lần cho user mới (tắt được trong Settings).

### 12.3 F1 mở/đóng

- Standby: nút `F1 Mở phiên` (xanh).  
- Đang có phiên: nút `F1 Đóng ca (Standby)`.  
- Nếu đóng mà chưa F4 và filmstrip còn ảnh: **dialog** — ưu tiên hướng user tới F4 để lưu & đóng; không cúp lặng.

### 12.4 Giọng khi lưới F5 mở

- Lưới = modal làm tối Cockpit.  
- Badge lớn: `ĐANG TÌM HỒ SƠ — giọng điền ô lọc`.  
- Placeholder ô lọc gợi lệnh nói.  
- Đóng lưới → hết badge, giọng về Intake/Ready pattern.

### 12.5 Correction không đổi Mã BN

- Ô Mã BN luôn ổ khóa + tooltip: `Đổi mã: F4 kết thúc phiên, rồi F1 và tìm lại`.  
- “Mở lại hồ sơ” chỉ mở tên / năm sinh / GT trên UI copy.

### 12.6 Tab Thư mục vs phiên Locked

- Pill dính khi Locked (mọi tab): `Đang ghi ảnh cho: [Mã] — [Tên]`.  
- Pedal khi đang Tab 2 + Locked: **vẫn chụp BN đang khám** (ưu tốc độ) + pill bắt buộc nhìn thấy.  
- “Mở ở Tab Chụp” BN khác: disabled + tooltip lý do.

### 12.7 Giảm ma sát không phá an toàn

- Sau F4: Standby với **CTA F1 lớn** + giọng “mở phiên”.  
- F2 disabled: liệt kê field thiếu trên banner (`Thiếu: Năm sinh — nói "năm sinh …"`).  
- Alias thoại “chuyển bệnh nhân mới” giữ hành vi F4; **toast**: `Đã kết thúc phiên — nhấn F1 cho BN tiếp`.

### 12.8 Xóa / xem lại (bù pedal một nghĩa)

- Xóa Cockpit: Delete / giọng “xóa” + **toast Undo ~5s**.  
- Xóa Tab 2: **modal confirm** (đã chốt).  
- Xem lại: click filmstrip và/hoặc giọng “xem lại” → lightbox; không long-press pedal.

### 12.9 Thứ tự implement UX này

1. Banner ngữ cảnh barcode + 1-hit Enter  
2. Nhãn F1/F2/F4 động + confirm F1 khi còn ảnh chưa F4  
3. Pill “Đang ghi cho BN …”  
4. Badge lưới F5 + modal dim  
5. Undo xóa Cockpit + toast sau “chuyển BN”  
6. Tooltip khóa Mã BN  
