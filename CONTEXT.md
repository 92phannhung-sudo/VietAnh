# CONTEXT - GLOSSARY & DOMAIN MODEL
*Dự án Hệ thống Chụp ảnh Bệnh án Điện tử (354 EMR Workstation)*

## 1. Các Khái niệm Miền (Domain Terms)

### Parallel Multi-Modal Control (Điều khiển Đa Phương thức Song song)
Khả năng hệ thống lắng nghe và phản hồi đồng thời 3 kênh điều khiển ngầm trên toàn bộ ứng dụng:
1. **Bàn phím & Đầu đọc Mã vạch (Keyboard & Barcode Scanner):** Phím tắt F1-F12, phím điều hướng và quét mã vạch HID.
2. **Bàn đạp chân (USB Foot Pedal):** Chỉ cử chỉ **chụp ảnh** khi Locked Capture (xem Pedal Capture-Only).
3. **Giọng nói tiếng Việt Offline (Offline Voice AI):** Luồng ASR nhận diện câu lệnh giọng nói tiếng Việt liên tục, được định tuyến theo **Voice Intake Mode** (không phải mọi utterance đều ghi vào form).

### Voice Intake Mode (Pha nghe giọng theo mục đích)
Máy trạng thái định tuyến ASR để vừa nhập liệu vừa khẩu lệnh mà không ghi đè demography khi nói ồn:
1. **Intake** — Chỉ parse demography vào form (pattern-only). Khẩu lệnh chụp/xóa bị bỏ qua. Field còn mở để sửa tự do (giọng pattern / tay) cho đến khi vào Locked Capture.
2. **Ready (Đủ hồ sơ — chờ Bắt đầu chụp)** — Đã đủ Demography Lock Gate (4 trường) nhưng **chưa** chụp. Hệ thống chờ hành động tường minh **Bắt đầu chụp** qua cả ba kênh: giọng (*"bắt đầu chụp"* / tương đương), nút GUI, và phím tắt. Chưa khóa field; chưa cho phép chụp.
3. **Locked Capture** — Sau **Bắt đầu chụp**: demography **khóa**. ASR chỉ nhận khẩu lệnh lâm sàng (`chụp`, `xóa`, `tiếp`…). Tiếng nói thường / ồn **không** ghi vào form.
4. **Correction** — Mở lại field chỉ khi lệnh tường minh hoặc UI:
   - *"sửa tên"* / *"sửa năm sinh"* / *"sửa giới tính"* → chỉ field đó; pattern-only; đủ giá trị → auto-lock lại Locked Capture.
   - *"mở lại hồ sơ"* / *"sửa thông tin"* → mở Họ tên + Năm sinh + Giới tính; **Mã Bệnh Nhân vẫn khóa** trên form. Đổi Mã BN chỉ bằng gõ tay khi field được mở theo policy riêng (v1: không đổi Mã BN trong Correction — phải F4 rồi phiên mới).
   - Icon ổ khóa trên UI tương đương các lệnh trên.

Chuyển Ready → Locked Capture **không** tự động: bắt buộc **Bắt đầu chụp** qua ba affordance cùng một hành động — giọng (*"bắt đầu chụp"* / *"bắt đầu khám"*), nút GUI (`F2 Bắt đầu chụp`, chỉ enable khi đủ gate), và phím tắt **F2**.

**Kết thúc phiên:** Phím **F4**, nút `F4 Kết thúc phiên`, giọng mặc định gồm *"kết thúc phiên"*, *"hoàn thành"*, *"chuyển bệnh nhân mới"* / *"bệnh nhân tiếp"* — cùng một hành động chốt ca hiện tại và chỉ sau đó mới được nạp BN mới. Không đổi BN giữa phiên dù quét barcode khác.

**Pedal Capture-Only:** Bàn đạp chân **chỉ** kích hoạt **chụp ảnh** (một cử chỉ / một hành động). Không dùng pedal để xóa, xem lại, hay chuyển bệnh nhân — các việc đó thuộc giọng / phím / UI. Pedal chỉ có hiệu lực trong **Locked Capture**; Standby / Intake / Ready bỏ qua.

**Demography Lock Gate:** Bắt buộc đủ cả bốn trường — **Mã Bệnh Nhân**, **Họ và Tên**, **Năm sinh**, **Giới tính** — trước khi **Bắt đầu chụp** được phép kích hoạt. Thiếu bất kỳ trường nào thì nút/phím/giọng "Bắt đầu chụp" bị vô hiệu hoặc báo thiếu field.

**Nguồn Mã Bệnh Nhân:** Chỉ từ **chọn dòng trên lưới tìm kiếm** (sau quét mã hoặc gõ lọc), nhập tay trên Cockpit, hoặc chọn hồ sơ F5. Giọng nói **không bao giờ** ghi vào ô Mã Bệnh Nhân. Quét barcode **không** tự ghi Mã BN — chỉ lọc lưới.

**Đổi Bệnh Nhân / barcode khác giữa phiên:** Không được chuyển hồ sơ khi phiên hiện tại chưa kết thúc. Quét mã khác với Mã Bệnh Nhân đang mở → **bỏ qua** (có tín hiệu cảnh báo), không nạp BN mới, không hỏi đổi giữa chừng. Chỉ sau **Kết thúc phiên** mới được nạp phiếu/BN tiếp theo.

### Vòng đời Phiên Bệnh Nhân (Patient Session Lifecycle)
Chuỗi bắt buộc trong một ca khám (một Bệnh Nhân):
1. **Bắt đầu phiên (thoát Standby)** — F1 / lệnh mở phiên: bật cam/mic/pedal, vào Intake.
2. **Nhập liệu (Intake → Ready)** — nạp demography đủ gate 4 trường (pattern-only cho giọng); khi đủ gate → Ready, chờ **Bắt đầu chụp**.
3. **Bắt đầu chụp → Locked Capture** — F2 / nút / giọng; khóa demography; chỉ khẩu lệnh/pedal chụp–xóa.
4. **Kết thúc phiên (F4 / “chuyển bệnh nhân mới” / “hoàn thành”)** — chốt ảnh + CSDL, dọn form, và **về Standby** (tắt cam/mic/pedal) — an toàn chống chụp/nhầm hồ sơ giữa hai BN. BN mới bắt buộc F1 mở phiên lại rồi mới nạp liệu.
   **hoặc** trong lúc chưa Kết thúc: **Correction** — sửa demography rồi trở lại Locked Capture, vẫn cùng một Bệnh Nhân.

**Định tuyến giọng pha Intake:** **Pattern-only** — chỉ chấp nhận utterance khớp mẫu demography (*"Họ và tên…"*, *"Năm sinh…"*, *"Giới tính…"*, hoặc câu đủ các trường được phép). Câu không khớp pattern bị bỏ qua; không ghi tự do vào ô đang focus.

**Năm sinh ASR cắt số (truncated year):** Zipformer đôi khi nuốt chữ số cuối (*"một chín chín"* thay vì *"một chín chín chín"*). Hệ thống **không** được pad `199→1990`. Thay vào đó giữ prefix 3 số và chờ utterance tiếp theo là một chữ số (*"chín"* → `1999`). Module: `incomplete_birth_year_prefix` / `complete_truncated_birth_year` trong `patient_voice_parser` + `_pending_year_prefix` trong `voice_detector`.

**Demography field coercion:** Gõ xóa ô / `UiFieldEdit(..., None)` không được biến thành chuỗi literal `"None"`. Domain dùng `_clean_str`; Cockpit bind qua `_ui_text` (bỏ `"none"`).

**Camera panel theo phase:** Chỉ Standby hiện copy “chế độ chờ / bấm F1”. Khi phiên đang mở mà camera lỗi phần cứng → panel đỏ lỗi USB/quyền; khi chờ stream → “đang chờ camera”, không revert Standby.

**Barcode / QR:** Trong **Intake/Ready**, quét mã là **đầu vào tìm kiếm**: luôn mở hoặc cập nhật **lưới hồ sơ** (lọc đúng mã) — **không** ghi thẳng banner Cockpit, **không** tự chụp. Chọn một dòng trên lưới mới nạp demography. Ngoài các phase đó: Standby bỏ qua; Locked/Correction gặp mã khác BN đang mở → bỏ qua + cảnh báo.

### Standby QR & Input Mode (Chế độ Chờ / Standby)
Trạng thái **thiết bị tắt** (camera, mic, bàn đạp) giữa các Bệnh Nhân và khi chưa mở phiên. Vào Standby khi: khởi động app, F1 kết thúc ca, hoặc **sau F4 Kết thúc phiên** (mỗi BN xong đều về Standby). Thoát Standby chỉ bằng **Bắt đầu phiên (F1)**. Trong Standby không nạp BN bằng giọng/pedal; barcode cũng không kích hoạt chụp hay search.

### Intake & Ready (Nhập liệu sau khi mở phiên)
Sau F1: nạp Bệnh Nhân bằng **tìm kiếm** (F5 / giọng / quét mã → lưới → chọn dòng), gõ tay, hoặc giọng pattern-only (trừ Mã BN). Đủ 4 trường → **Ready** (chờ F2 Bắt đầu chụp). Chưa Locked Capture thì chưa được chụp ảnh.

### Patient Photo Folder Browser (Tab Thư Mục Bệnh Án)
Không gian **xem lại** ảnh đã lưu trên đĩa (browse 2 cấp: thư mục BN → lưới ảnh). **Không** thay F5: không dùng Tab này để chọn hồ sơ bắt đầu khám. Muốn nạp BN vào phiên chụp → F5 / quét mã (Intake·Ready). Tab Thư mục tách biệt **Patient History Grid Search**.

**Khi đang Locked Capture:** Vẫn **được** mở Tab Thư mục để xem. Không được nạp BN khác vào Cockpit từ đây. Nút “Mở ở Tab Chụp” với BN **khác** BN đang khám → **chặn** (phải F4 kết thúc rồi F1 lại). Nút đó với **cùng** BN đang mở chỉ chuyển về Tab Chụp, không đổi demography.

**Lọc trên Tab Thư mục:** Ô search / quét mã khi đang ở Tab 2 chỉ **lọc browse** (thư mục/ảnh theo mã exact hoặc tên). Không mở F5, không nạp demography vào phiên khám.

**Không có xuất báo cáo PDF** — bỏ F10 / export report khỏi phạm vi sản phẩm (Tab 2 không xuất PDF).

**Xóa ảnh trên Tab 2:** Cho **xóa từng ảnh** khi đang xem Level 2, **bắt buộc confirm** trước khi xóa. Không xóa cả thư mục BN trong một thao tác (v1).

### Patient History Grid Search (Tra Cứu & Tìm Kiếm Hồ Sơ Dạng Lưới)
Chức năng tra cứu ra **danh sách hồ sơ** để chọn một dòng nạp vào Cockpit:
- **Kích hoạt mở lưới:** Nút / phím `F5`, giọng lexicon, hoặc **quét QR/barcode camera** (Intake/Ready).
- **Phase được phép:** Chỉ **Intake** và **Ready**.
- **Hai cách tìm (chính xác theo mã; tên linh hoạt):**
  1. Quét QR/barcode → mở/cập nhật lưới, lọc **đúng mã** (exact).
  2. Gõ vào form lọc trên lưới: **Mã** khớp đúng toàn bộ; **Họ tên** cho phép **chứa đoạn** (bỏ dấu, không phân biệt hoa thường); **Năm sinh** / **Giới tính** khớp đúng khi được điền.
- **Mở lưới khi chưa gõ/quét:** Hiện danh sách hồ sơ **gần đây** (giới hạn N, mặc định hợp lý ~20–50), sắp xếp **mới nhất → cũ nhất**. Gõ lọc hoặc quét mã thì thay bằng kết quả lọc.
- **Giọng khi lưới đang mở:** Định tuyến vào **ô lọc của lưới** (pattern điền mã/tên/năm sinh/GT trên form tìm — mã vẫn không bịa; ưu tiên lệnh lọc tường minh). **Không** ghi demography vào Cockpit phía sau. Thêm lệnh đóng lưới / xác nhận “bệnh nhân mới” khi 0 kết quả.
- **Không có kết quả (BN mới):** Lưới trống + gợi ý dùng mã vừa quét/gõ; bác sĩ **xác nhận** → đóng lưới, ghi **chỉ Mã BN** vào Cockpit; tên / năm sinh / GT để trống cho Intake tiếp. Không tự điền demography khác.
- **Chọn một dòng:** thay toàn bộ demography trên Cockpit (không hỏi khi Intake/Ready). **Đúng 1 kết quả:** highlight; Enter/Space = chọn.
- Tách biệt Tab Thư mục ảnh (browse file).

### Widescreen Live Capture Engine (Động cơ Chụp Ảnh Live Stream Màn Hình Rộng 100%)
Chế độ chụp rảnh tay tối đa hóa diện tích quan sát (Toàn bộ chiều rộng 100%):
- **Kích hoạt Chụp:** 1 Giậm / Giọng nói *"Chụp ảnh"* / Phím `Space`. Chớp viền xanh nhạt + phát hiệu ứng âm thanh shutter.
- **Lưu & Phim cuộn:** Lưu ngầm vào đĩa (<150ms) và đẩy ảnh mới lên thanh cuộn Filmstrip dưới cùng.
- **Diện tích tối đa:** Không sử dụng ô so sánh Baseline, toàn bộ màn hình trung tâm dành riêng cho Live Camera Stream 1080p siêu nét.

### Deletion & Trash Lifecycle (Luồng Xóa & Thùng Rác Tạm)
- **Cockpit (Locked Capture):** Giọng *"Xóa ảnh"* / phím `Delete` — xóa ảnh gần nhất trên Filmstrip; **toast Undo ~5s**. **Không** dùng bàn đạp để xóa (`Pedal Capture-Only`).
- **Tab Thư mục:** Xóa từng ảnh ở Level 2 với **confirm** bắt buộc.

### Session Lifecycle (Vòng đời Phiên Khám)
Khi **Kết thúc phiên** (F4 / giọng “kết thúc” / “chuyển bệnh nhân mới”):
1. Chốt danh sách ảnh và đồng bộ CSDL (`patients`, `photos`, `audit_logs`).
2. Dọn form Cockpit và về **Standby** (tắt cam/mic/pedal).
3. **Không** xuất PDF / báo cáo (đã loại khỏi phạm vi).
4. BN tiếp theo: F1 mở phiên lại rồi nạp liệu / tìm kiếm.

## 3. Dữ liệu ứng dụng theo OS
| OS | Thư mục dữ liệu (`config.get_user_data_dir`) |
|---|---|
| Windows | `%APPDATA%\PatientCaptureApp\` |
| macOS | `~/Library/Application Support/PatientCaptureApp/` |
| Linux | `~/.local/share/PatientCaptureApp/` |

Chi tiết cài đặt: `docs/WINDOWS_SETUP.md`, `docs/MACOS_SETUP.md`.
