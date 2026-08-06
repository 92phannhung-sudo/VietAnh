# THIẾT KẾ ĐẶC TẢ TÁI THIẾT KẾ GIAO DIỆN VÀ LUỒNG NGHIỆP VỤ HỆ THỐNG CHỤP ẢNH BỆNH ÁN ĐIỆN TỬ
*Dự án: 354 EMR Workstation (Offline Patient Photo Capture System)*  
*Tệp đặc tả:* `docs/superpowers/specs/2026-08-04-emr-workstation-redesign-spec.md`  
*Ngày cập nhật đặc tả:* 2026-08-06  
*Trạng thái:* ĐÃ PHÊ DUYỆT & ĐỒNG BỘ 100% QUY TRÌNH NGUYÊN BẢN (FULLY SYNCHRONIZED)

---

## 1. TỔNG QUAN & MỤC TIÊU HỆ THỐNG

### 1.1. Mục tiêu Tái Thiết Kế
Chuyển đổi giao diện hệ thống từ 4-Tab phân mảnh sang **Bảng điều khiển Y tế Tập trung Màn hình Đơn (Unified Clinical Cockpit)** chuẩn PySide6 QDarkTheme (1440x900px Desktop Window). Đồng thời **bảo tồn và kế thừa 100% toàn bộ quy trình nghiệp vụ y tế gốc** từ `docs/SPECIFICATION.md`:
- Vận hành rảnh tay 100% song song qua 3 kênh: **Bàn đạp chân USB (FSM)**, **Giọng nói Tiếng Việt Offline (Vosk ASR)**, và **Phím tắt Bàn phím**.
- Quét mã vạch/QR tự động tách dữ liệu bệnh nhân (JSON QR, Delimited String `Mã|Tên|Năm|Giới`, URL QR).
- Tra cứu hồ sơ bệnh nhân cũ dạng **Lưới (Grid View `F5`)** với bộ lọc 4 trường optional và xem thumbnail Ảnh Baseline.
- So sánh Ảnh Baseline khám cũ song song (Split 60% Camera Live Feed / 40% Ảnh Baseline cũ).
- Bộ công cụ Kiểm chẩn Phần cứng (Diagnostic Test Dialogs `F4`): Test Camera & QR, Test Giọng nói RMS/Vosk, Test 4 Thao tác Giậm Bàn đạp, Ping Cổng COM.
- Ghi nhật ký truy vết y tế (`audit_logs`) và CSDL SQLite WAL mode hoàn toàn offline.

### 1.2. Môi trường & Bộ Thư viện Giao diện
- **Khung giao diện:** PySide6 (Qt for Python).
- **Bộ chuẩn màu QDarkTheme (WCAG 2.1 AAA):** Window BG `#0F172A`, Container `#1E293B`, Primary `#0284C7`, Success `#16A34A`, Border `#334155`, Text `#F8FAFC`.
- **Độ phân giải chuẩn:** 1440x900px (16:10 Desktop Window).

---

## 2. BỐ CỤC GIAO DIỆN BẢNG ĐIỀU KHIỂN TẬP TRUNG (UNIFIED CLINICAL COCKPIT)

```
+---------------------------------------------------------------------------------------------------+
| WINDOW TITLE BAR: 🔴 🟡 🟢  354 EMR Workstation v1.0.4 - Bảng Điều Khiển Y Tế Tập Trung            |
+---------------------------------------------------------------------------------------------------+
| HEADER BAR: [🏥 354 EMR] | 👤 BS. Nguyễn Văn A | 🦶 Pedal: CONNECTED | 🎙️ Voice: READY | 📷 1080p |
+---------------------------------------------------------------------------------------------------+
| STANDBY PATIENT BANNER:                                                                           |
| Mã BN: [ BN2026-0804 ] | Họ Tên: [ Nguyễn Văn A ] | Năm Sinh: [ 1987 ] | Giới Tính: [ Nam ]        |
| [🔍 F5 Tra Cứu Hồ Sơ Grid]   [🚀 F1 Bắt Đầu Phiên Chụp]                                           |
+---------------------------------------------------------------------------------------------------+
| CENTER SPLIT PANEL (TỈ LỆ 60 / 40):                                                               |
| +-----------------------------------------------+ +---------------------------------------------+ |
| | LIVE STREAM CAMERA FEED 1080p (60% WIDTH)     | | ÂNH BASELINE LẦN KHÁM TRƯỚC (40% WIDTH)     | |
| | - Feed Logitech C920e 1080p Full HD           | | - Tự động hiển thị song song khi chọn BN cũ| |
| | - Green border shutter cue (<150ms)           | | - Thẻ lâm sàng: [✓ Da liễu] [✓ Vùng Mặt]  | |
| | - Overlay hướng dẫn Bàn đạp / Voice           | |                                             | |
| +-----------------------------------------------+ +---------------------------------------------+ |
+---------------------------------------------------------------------------------------------------+
| BOTTOM FILMSTRIP CAROUSEL & ACTION TOOLBAR                                                         |
| [Ảnh #1]  [Ảnh #2]  [Ảnh #3]               |  [✅ F2 HOÀN THÀNH CA KHÁM (Lưu CSDL & Reset)]     |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. CƠ CHẾ BẢO TỒN VÀ TÁCH MÃ QR / BARCODE ĐA ĐỊNH DẠNG (BARCODE & QR PARSER)

Hệ thống phân tích luồng camera live feed liên tục và tự động bóc tách thông tin Bệnh nhân:
1. **Mã vạch 1D Barcode (Code 128 / Code 39):** Trích xuất `patient_id` (ví dụ: `PHCN2647781`, `KCB-2026-0012`).
2. **Chuỗi QR JSON:** Bóc tách tự động các khóa `id`, `name`, `birth_year`, `gender` (ví dụ: `{"id": "BN123", "name": "Nguyễn Văn A", "birth_year": 1987, "gender": "Nam"}`).
3. **Chuỗi Mã Vạch Phân Phân Tách (`|` hoặc `;`):** Bóc tách `BN123|Nguyễn Văn A|1987|Nam`.
4. **URL QR String:** Bóc tách tham số Query string (ví dụ: `https://his.vn/emr?id=BN123`).
5. **Âm thanh Phản hồi:** Phát tiếng `Beep` cue khi quét thành công và điền tự động 4 trường dữ liệu.

---

## 4. CƠ CHẾ ĐIỀU KHIỂN ĐA PHƯƠNG THỨC SONG SONG (PARALLEL MULTI-MODAL CONTROL)

Hệ thống duy trì đồng thời 3 kênh đầu vào ngầm trên toàn bộ ứng dụng:

| Thao tác Lâm sàng | ⌨️ Bàn Phím / Phím Tắt | 🦶 Bàn Đạp Chân (FSM) | 🎙️ Giọng Nói Offline (Vosk) | 📷 Camera / Scanner |
| :--- | :--- | :--- | :--- | :--- |
| **Bắt đầu Phiên Mới** | `F1` | — | *"Tạo phiên làm việc mới"* / *"Bắt đầu phiên mới"* | — |
| **Tìm Hồ Sơ Bệnh Nhân** | `F5` / `Ctrl + F` | — | *"Tìm kiếm hồ sơ"* / *"Tra cứu bệnh nhân"* | Quét mã QR/Barcode phiếu ban đầu |
| **Chụp Ảnh** | `Phím Cách (Space)` | **1 Giậm** (Single Tap) | *"Chụp"* / *"Chụp ảnh"* | — |
| **Xóa Ảnh Vừa Chụp** | `Delete` / `Backspace` | **Giậm Giữ 1.5s** (Long Press) | *"Xóa"* / *"Xóa ảnh"* | — |
| **Hoàn thành / Lưu** | `F2` / `Ctrl + S` | — | *"Hoàn thành"* / *"Bệnh nhân tiếp"* | — |

---

## 5. BỘ HỘP THOẠI KIỂM CHẨN PHẦN CỨNG THỰC TẾ (HARDWARE DIAGNOSTIC TEST MODALS `F4`)

Kế thừa 100% các Hộp thoại Kiểm chẩn Phần cứng từ Tab Cài đặt cũ (Mở từ nút `F4 Cài Đặt`):
1. **📷 Camera & QR Test Modal (`CameraTestDialog`)**: Stream 1080p, quét mã barcode/QR trực tiếp, phát tiếng beep và hiện badge `Đã Quét Mã: [ PHCN2647781 ] - OK`.
2. **🎙️ Microphone Test Modal (`MicrophoneTestDialog`)**: Đồng hồ RMS Volume Meter (0-100%) live + Vosk AI. Nhận diện 4 câu lệnh (`"chụp"`, `"xóa"`, `"tiếp"`, `"xem"`) và hiện badge checkmark xanh lá.
3. **🦶 Foot Pedal Test Modal (`PedalTestDialog`)**: Checklist live 4 thao tác giậm chân (`1 Giậm`, `2 Giậm`, `3 Giậm`, `Giậm Giữ`) tự động tick `[✓]` khi giậm bàn đạp thực tế.
4. **🔌 COM Serial Port Test Modal (`COMPortTestDialog`)**: Gửi gói tin handshake `Ping 0x06` (Baudrate 9600) tới cổng RS232/USB Serial và kiểm tra phản hồi `OK`.

---

## 6. QUY TRÌNH NGHIỆP VỤ VÒNG ĐỜI PHIÊN KHÁM (END-TO-END WORKFLOW)

### 🔵 BƯỚC 1: Chế độ Chờ, Tra Cứu Dạng Lưới & Kiểm duyệt (Standby, Grid Search & Validation)
1. **Khởi tạo:** Hệ thống ở Chế độ Chờ. Quét QR phiếu hoặc nhập thủ công 4 trường (`Mã BN`, `Họ tên`, `Năm sinh`, `Giới tính`).
2. **Tra cứu Hồ sơ Cũ dạng Lưới (`F5` Modal):**
   - Kích hoạt qua phím `F5`, nút GUI, giọng nói *"Tìm kiếm hồ sơ"*, hoặc quét QR phiếu cũ.
   - Bộ lọc optional 4 trường: *Mã hồ sơ*, *Họ tên không dấu*, *Năm sinh*, *Giới tính*.
   - Hiển thị danh sách Lưới 3 cột (Grid View) với thumbnail Ảnh Baseline cũ và ngày khám gần nhất.
3. **Kiểm duyệt (Validation):** Đổi màu viền xanh lá (Valid) khi đủ 4 trường $\rightarrow$ Nút `F1 Bắt Đầu Phiên` sáng lên.

### 🟢 BƯỚC 2: Chụp Ảnh Rảnh Tay & So Sánh Baseline (Live Capture Mode)
1. **Chụp Ảnh:** 1 Giậm bàn đạp / Voice *"Chụp ảnh"* / `Space`.
   - Nháy viền xanh nhạt + Âm thanh shutter.
   - Ảnh lưu ngầm đĩa đệm (<150ms) và đẩy lên thanh Filmstrip ở dưới.
2. **So sánh Baseline:** Ô 40% bên phải hiển thị ảnh khám cũ của bệnh nhân để bác sĩ đánh giá tiến triển ngay tại chỗ.
3. **Xóa Ảnh Vừa Chụp:** Giậm giữ bàn đạp (Long press) / Voice *"Xóa ảnh"* / `Delete`.
   - Đưa ảnh gần nhất trên Filmstrip vào thùng rác tạm + Toast thông báo *"Đã xóa ảnh #X"*.

### 🟡 BƯỚC 3: Hoàn Thành Ca Khám & Reset (Session Completion Mode)
1. **Kích hoạt:** Bấm `F2` / Voice *"Hoàn thành"*.
2. **Xử lý:** Lưu CSDL SQLite WAL mode (`patients`, `photos`, `audit_logs`), xuất báo cáo PDF (nếu bật).
3. **Reset:** Xóa thông tin bệnh nhân trên màn hình, quay về Trạng thái Chờ cho bệnh nhân tiếp theo.
