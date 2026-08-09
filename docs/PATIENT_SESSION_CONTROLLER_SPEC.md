# PatientSessionController — Spec Interface Design A

> **Nguồn:** ADR 0002, `CONTEXT.md` (Voice Intake Mode + Patient History Grid Search)  
> **Bề mặt:** một method `handle(event) → SessionOutcome`  
> **Chưa phải implementation** — hợp đồng để MainWindow / dispatcher / test bám vào.

---

## 1. Một câu tóm tắt

```text
mọi thao tác  →  handle(SessionEvent)  →  SessionOutcome { view, effects }
UI chỉ vẽ view + chạy effects. Không tự đoán “được chụp chưa”.
```

---

## 2. Phase (trạng thái phiên)

| Phase | Ý nghĩa ngắn | Thiết bị | Giọng (Cockpit) | Pedal / Space chụp | Mở lưới F5 |
|---|---|---|---|---|---|
| `STANDBY` | Chờ mở phiên | Tắt | Off | Không | Không |
| `INTAKE` | Đang nhập hồ sơ (thiếu field) | Bật | Pattern demography* | Không | Có |
| `READY` | Đủ 4 field, chờ F2 | Bật | Pattern + “bắt đầu chụp”* | Không | Có |
| `LOCKED_CAPTURE` | Đang chụp, form khóa | Bật | Khẩu lệnh lâm sàng | Có | Không |
| `CORRECTION` | Sửa field đã mở khóa | Bật | Pattern field đang mở* | Không | Không |

\*Khi **lưới tìm kiếm đang mở** (`view.search.open == True`): giọng **không** ghi Cockpit — chỉ điền **ô lọc lưới** / đóng / confirm BN mới (xem §10).

**Chuyển pha chính**

```text
STANDBY --F1 / "mở phiên"--> INTAKE
INTAKE  --đủ 4 field------> READY          (tự động trong handle)
READY   --F2 / "bắt đầu chụp"--> LOCKED_CAPTURE
LOCKED_CAPTURE --"sửa …" / UI unlock--> CORRECTION
CORRECTION --field đã có giá trị--> LOCKED_CAPTURE   (auto re-lock)
* --F4 / "kết thúc" / "chuyển bệnh nhân mới"--> STANDBY (+ persist)
```

---

## 3. `SessionEvent` — mọi thứ đổ vào đây

```python
SessionEvent =
  | Hotkey(key)                 # "F1" | "F2" | "F4" | "F5" | "Space" | "Delete"
  | VoiceUtterance(text)        # ASR thô — controller tự route (kể cả khi search mở)
  | BarcodeScan(code)           # Intake/Ready → mở/cập nhật lưới; không bao giờ = chụp
  | PedalGesture                # chỉ nghĩa "capture"
  | UiFieldEdit(field, value)   # gõ trên Cockpit banner
  | UiUnlock(fields)
  | LoadRecord(demography)      # chọn MỘT dòng trên lưới → thay toàn bộ demography
  | SearchFilterEdit(...)       # gõ / voice điền ô lọc trên lưới (khi search mở)
  | ConfirmNewPatientId         # 0 kết quả: user xác nhận dùng mã đang lọc làm BN mới
  | CloseSearch                 # đóng lưới
  | LexiconUpdate(phrases)
```

```python
SearchFilterEdit:
  patient_id: str | None      # exact match khi set
  full_name: str | None       # substring, unaccented
  birth_year: str | None      # exact khi set
  gender: str | None          # exact khi set
```

### Ý nghĩa từng event (theo phase)

| Event | STANDBY | INTAKE / READY | LOCKED_CAPTURE | CORRECTION |
|---|---|---|---|---|
| `Hotkey F1` | → INTAKE + bật máy | EndSession → Standby* | như trái | như trái |
| `Hotkey F2` | ignore / warn | READY → LOCKED; thiếu gate → reject | ignore | ignore |
| `Hotkey F4` | ignore | kết thúc nếu đang có phiên | kết thúc | kết thúc |
| `Hotkey F5` | ignore | `OPEN_SEARCH_GRID` (recent) | **ignore + WARN** | **ignore + WARN** |
| `Hotkey Space` | ignore | ignore | `CAPTURE_FRAME` | ignore |
| `Hotkey Delete` | ignore | ignore | `DELETE_LAST` | ignore |
| `VoiceUtterance` | ignore | xem §6 / §10 | lexicon lâm sàng + “sửa …” | pattern field mở |
| `BarcodeScan` | ignore | **luôn** mở/cập nhật lưới, lọc **exact mã**; không ghi Cockpit | mã ≠ BN đang mở → WARN; không đổi BN | như Locked |
| `PedalGesture` | ignore | ignore | `CAPTURE_FRAME` | ignore |
| `UiFieldEdit` | ignore | ghi nếu `editable` | reject nếu locked | ghi field unlock |
| `UiUnlock` | ignore | ignore | → CORRECTION | mở thêm field |
| `LoadRecord` | ignore | **thay toàn bộ** demography (không hỏi); đóng lưới | **ignore + WARN** | **ignore + WARN** |
| `SearchFilterEdit` | ignore | chỉ khi `search.open`; cập nhật filter + kết quả | ignore | ignore |
| `ConfirmNewPatientId` | ignore | 0 kết quả + có mã lọc → chỉ ghi `patient_id` vào Cockpit; đóng lưới | ignore | ignore |
| `CloseSearch` | noop | đóng lưới | đóng nếu còn sót UI | đóng |
| `LexiconUpdate` | luôn apply | luôn | luôn | luôn |

\*F1 khi không Standby = kết thúc về Standby (confirm UI nếu có ảnh — tầng MainWindow).

---

## 4. `SessionView` — UI chỉ đọc cái này

```python
Demography:
  patient_id, full_name, birth_year, gender   # cả 4 bắt buộc cho gate

SearchView:                    # trạng thái lưới (controller sở hữu để route giọng đúng)
  open: bool
  filter: SearchFilterEdit
  mode: "recent" | "filtered" | "empty_new_patient_prompt"
  # recent: chưa gõ/quét — danh sách mới nhất → cũ nhất, giới hạn N (vd. 50)
  # filtered: đã có filter từ gõ/quét/voice
  # empty_new_patient_prompt: 0 hit + có mã → hiện confirm BN mới

Affordances:
  start_session: bool
  begin_capture: bool          # True chỉ READY + đủ gate + search không chặn F2 (search có thể vẫn mở)
  end_session: bool
  pedal_capture: bool          # True chỉ LOCKED_CAPTURE
  can_open_search: bool        # True chỉ INTAKE | READY
  voice_mode: "off" | "intake_pattern" | "command" | "correction_pattern" | "search_filter"
  editable: set[Field]
  patient_id_voice_forbidden: True

SessionView:
  phase: Phase
  demography: Demography
  search: SearchView
  affordances: Affordances
  missing_for_gate: set[Field]
  notice: str | None
```

**Gate:** `patient_id` ∧ `full_name` ∧ `birth_year` ∧ `gender` → `begin_capture = True`.

**Field coercion (`UiFieldEdit` / `_apply_field`):** Chuỗi demography (`patient_id`, `full_name`, `gender`) đi qua `_clean_str`: `None` / `""` / literal `"None"` / `"none"` → `None` trong model (ô UI trống). **Cấm** `str(None)` vì tạo chuỗi `"None"` và làm gate hiểu nhầm là đã có Mã BN. `birth_year` vẫn `None` hoặc `int`.

**Camera UI (shell, không thuộc domain):** `SessionView.phase` điều khiển placeholder camera. Standby → copy chờ F1. Phase khác + lỗi HW → panel lỗi; phase khác + chưa có frame → “đang chờ camera”. Domain không phát Effect riêng cho lỗi camera — MainWindow/`ClinicalCockpitWidget` gắn từ `handle_thread_error`.

---

## 5. `Effect` — MainWindow phải chạy hết

| Effect | Khi nào | Việc MainWindow làm |
|---|---|---|
| `POWER_DEVICES_ON` | F1 → INTAKE | Bật cam / mic / pedal hook |
| `POWER_DEVICES_OFF` | → STANDBY | Tắt cam / mic / pedal |
| `CAPTURE_FRAME` | Pedal / Space / “chụp” lúc Locked | Shutter + filmstrip + DB ảnh |
| `DELETE_LAST` | Delete / “xóa” lúc Locked | Xóa ảnh gần nhất |
| `OPEN_SEARCH_GRID` | F5 / giọng tìm / BarcodeScan Intake·Ready | Mở dialog nếu chưa; bind `view.search` (recent hoặc filter mã) |
| `REFRESH_SEARCH_RESULTS` | SearchFilterEdit / barcode khi lưới đã mở | Query DB theo §10; render lưới |
| `CLOSE_SEARCH_GRID` | LoadRecord / ConfirmNewPatientId / CloseSearch | Đóng dialog |
| `PERSIST_AND_CLEAR` | F4 / kết thúc / chuyển BN | Commit + xóa form |
| `WARN` | Sai phase, barcode locked, … | Beep / toast từ `view.notice` |

```python
SessionOutcome:
  view: SessionView
  effects: list[Effect]
```

**Trách nhiệm query DB:** MainWindow / `PatientSearchService` thực hiện khi nhận `OPEN_SEARCH_GRID` / `REFRESH_SEARCH_RESULTS`, đọc `view.search.filter` + `mode`. Controller **không** trả list row trong outcome (tránh phình domain) — chỉ nói filter/mode.

---

## 6. Voice routing (Cockpit — khi `search.open == False`)

1. `voice_mode == off` → ignore.  
2. `intake_pattern` / `correction_pattern` → pattern demography cho `editable`; **không bao giờ** `patient_id`.  
3. `command` (Locked) → lexicon: chụp / xóa / kết thúc / chuyển BN / sửa… / mở lại hồ sơ.  
4. READY: pattern + “bắt đầu chụp” / “bắt đầu khám”.  
5. “tìm kiếm hồ sơ” / F5-equivalent → `OPEN_SEARCH_GRID` (recent) nếu `can_open_search`.  
6. Không khớp → ignore.

---

## 7. Wiring gọi `handle` (ví dụ)

```text
F1                → Hotkey("F1")
F2                → Hotkey("F2")
F4                → Hotkey("F4")
F5                → Hotkey("F5")
Space / Delete    → Hotkey(...)
ASR final         → VoiceUtterance(text)
Barcode           → BarcodeScan(code)
Pedal             → PedalGesture
Ô Cockpit         → UiFieldEdit(...)
Ô lọc lưới        → SearchFilterEdit(...)
Chọn 1 card lưới  → LoadRecord(demography)
Confirm BN mới    → ConfirmNewPatientId
Đóng lưới         → CloseSearch
Settings lexicon  → LexiconUpdate(...)
```

```text
outcome = controller.handle(event)
cockpit.render(outcome.view)
for fx in outcome.effects:
    apply(fx)
```

---

## 8. Invariants (luôn đúng)

1. Giọng không ghi `patient_id` trên Cockpit (kể cả Correction).  
2. Barcode **không** sinh `CAPTURE_FRAME`.  
3. Barcode Intake/Ready **không** ghi thẳng demography — chỉ qua lưới (`OPEN_SEARCH_GRID` / filter).  
4. Pedal / Space chỉ `CAPTURE_FRAME` khi `LOCKED_CAPTURE`.  
5. F2 chỉ khi `READY` + đủ 4 field.  
6. Search chỉ Intake/Ready; Locked/Correction không `LoadRecord` BN khác.  
7. `LoadRecord` **thay toàn bộ** demography, không merge, không confirm.  
8. F4 → Standby + `PERSIST_AND_CLEAR` + `POWER_DEVICES_OFF`.  
9. BN mới sau F4: phải F1 lại.

---

## 9. Việc chưa làm (ngoài spec này)

- Class Python + bảng transition test  
- UI badge theo `phase` / `voice_mode` / `search.open`  
- Settings CRUD lexicon  
- Đồng bộ USER_GUIDE (F2/F4, search, bỏ PDF)  
- Chi tiết UI Tab Thư mục (card, breadcrumb) — rule miền ở §11  

---

## 10. Tìm kiếm hồ sơ (chi tiết — đã grill)

### 10.1 Hai cách vào lưới

1. **F5 / giọng “tìm…”** → `mode=recent`: N hồ sơ (vd. 50), **mới nhất → cũ nhất**.  
2. **Quét QR/barcode** (Intake/Ready) → mở/cập nhật lưới, `filter.patient_id = code` (**exact**), `mode=filtered`.

### 10.2 Luật lọc khi `mode=filtered`

| Field | Match |
|---|---|
| Mã hồ sơ | **Exact** (trim) |
| Họ tên | **Chứa đoạn**, bỏ dấu, không phân biệt hoa thường |
| Năm sinh | **Exact** nếu ô có giá trị |
| Giới tính | **Exact** nếu ô có giá trị |

Các ô filter kết hợp AND (ô trống = bỏ qua điều kiện đó).

### 10.3 0 kết quả + có mã

- `mode=empty_new_patient_prompt`  
- User `ConfirmNewPatientId` → Cockpit chỉ nhận `patient_id`; tên/NS/GT trống; đóng lưới; phase vẫn Intake (hoặc Ready nếu sau này đủ field — thường vẫn thiếu).  

### 10.4 Chọn một dòng

- `LoadRecord` → thay **toàn bộ** 4 field (và field kèm theo nếu có); đóng lưới; toast/notice “Đã nạp hồ sơ …”.  
- **Đúng 1 kết quả:** UI highlight dòng duy nhất; **Enter / Space** phát `LoadRecord` (không bắt buộc chuột).  

### 10.5 Giọng khi `search.open`

- `voice_mode = search_filter`  
- Pattern điền `SearchFilterEdit` (tên / năm sinh / GT / mã nếu lexicon cho phép — **không** bịa mã nếu không nói rõ).  
- “đóng” → `CloseSearch`  
- “bệnh nhân mới” / tương đương → `ConfirmNewPatientId` khi đang empty prompt  
- Không ghi banner Cockpit phía sau  

### 10.6 Khác Tab Thư mục

F5 search = chọn **hồ sơ bệnh nhân** trong CSDL. Tab 2 = browse **file ảnh** — xem §11.

---

## 11. Tab Thư mục bệnh án (đã grill)

Tab 2 **không** thuộc happy-path `handle` cho nạp BN; phần lớn là UI browse đĩa. Vẫn phải tôn trọng phase từ `SessionView`:

| Rule | Chi tiết |
|---|---|
| Vai trò | Xem lại ảnh trên đĩa (Level 1 folder BN → Level 2 lưới ảnh). **Không** thay F5. |
| Locked Capture | Cho mở Tab 2 xem. |
| “Mở ở Tab Chụp” | Cùng `patient_id` đang khám → chỉ `switch_tab(0)`. **Khác** BN → chặn + WARN (phải F4 rồi F1). MainWindow đọc `view.demography.patient_id` + `phase`. |
| Search / barcode trên Tab 2 | Chỉ **lọc browse** (mã exact / tên). Không `OPEN_SEARCH_GRID` F5, không `LoadRecord`. |
| PDF / F10 | **Loại bỏ** khỏi sản phẩm. |
| Xóa ảnh | Cho xóa **từng ảnh** ở Level 2, **bắt buộc confirm**. Không xóa cả thư mục BN (v1). Xóa cập nhật đĩa + DB `photos` nếu có record. |

**Gợi ý affordance (optional trên view):** `can_jump_to_capture_for(patient_id: str) -> bool` — True iff phase ∈ {INTAKE, READY, LOCKED_CAPTURE, CORRECTION} và `patient_id == demography.patient_id`, hoặc phase ∈ {INTAKE, READY} và form trống (chưa có BN) *nếu sau này cho phép* — **v1 đơn giản:** chỉ True khi trùng BN đang mở; Standby → False (phải F1 trước đã có ở Cockpit).

