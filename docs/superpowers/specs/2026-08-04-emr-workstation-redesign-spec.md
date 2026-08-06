# THIẾT KẾ ĐẶC TẢ GIAO DIỆN VÀ LUỒNG NGHIỆP VỤ HỆ THỐNG CHỤP ẢNH BỆNH ÁN ĐIỆN TỬ
*Dự án: 354 EMR Workstation (Offline Patient Photo Capture System)*
*Tệp đặc tả:* `docs/superpowers/specs/2026-08-04-emr-workstation-redesign-spec.md`  
*Ngày cập nhật đặc tả:* 2026-08-06  
*Trạng thái:* ĐÃ PHÊ DUYỆT (APPROVED BY USER)

---

## 1. MỤC TIÊU VÀ TỔNG QUAN HỆ THỐNG

### 1.1. Mục tiêu Cốt lõi
Chuyển đổi giao diện hệ thống sang **Bảng điều khiển Y tế Tập trung Màn hình Đơn (Unified Clinical Cockpit)** chuẩn PySide6 QDarkTheme. Đảm bảo Bác sĩ / Kỹ thuật viên vận hành 100% rảnh tay qua Bàn đạp chân USB và Giọng nói Tiếng Việt Offline, hỗ trợ so sánh Ảnh Baseline khám cũ song song bên cạnh Live Stream Camera.

### 1.2. Môi trường & Bộ Thư viện Giao diện
- **Khung giao diện:** PySide6 (Qt for Python).
- **Bộ chuẩn màu QDarkTheme:** Background `#0F172A`, Container `#1E293B`, Primary `#0284C7`, Success `#16A34A`, Border `#334155`, Text `#F8FAFC`.
- **Độ phân giải chuẩn:** 1440x900px (16:10 Desktop Window).

---

## 2. BỐ CỤC GIAO DIỆN BẢNG ĐIỀU KHIỂN TẬP TRUNG (UNIFIED CLINICAL COCKPIT)

Giao diện chính được bố trí theo 4 khu vực chức năng tiêu chuẩn:

```
+---------------------------------------------------------------------------------------------------+
| WINDOW TITLE BAR: 🔴 🟡 🟢  354 EMR Workstation v1.0.4 - Bảng Điều Khiển Y Tế Tập Trung            |
+---------------------------------------------------------------------------------------------------+
| HEADER BAR: [🏥 354 EMR] | 👤 BS. Nguyễn Văn A | 🦶 Pedal: OK | 🎙️ Voice: READY | 📷 Camera: 1080p|
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

## 3. CƠ CHẾ ĐIỀU KHIỂN ĐA PHƯƠNG THỨC SONG SONG (PARALLEL MULTI-MODAL CONTROL)

Hệ thống duy trì đồng thời 3 kênh đầu vào ngầm trên toàn bộ ứng dụng:

| Thao tác Lâm sàng | ⌨️ Bàn Phím / Phím Tắt | 🦶 Bàn Đạp Chân (FSM) | 🎙️ Giọng Nói Offline (Vosk) | 📷 Camera / Scanner |
| :--- | :--- | :--- | :--- | :--- |
| **Bắt đầu Phiên Mới** | `F1` | — | *"Tạo phiên làm việc mới"* / *"Bắt đầu phiên mới"* | — |
| **Tìm Hồ Sơ Bệnh Nhân** | `F5` / `Ctrl + F` | — | *"Tìm kiếm hồ sơ"* / *"Tra cứu bệnh nhân"* | Quét mã QR/Barcode phiếu ban đầu |
| **Chụp Ảnh** | `Phím Cách (Space)` | **1 Giậm** (Single Tap) | *"Chụp"* / *"Chụp ảnh"* | — |
| **Xóa Ảnh Vừa Chụp** | `Delete` / `Backspace` | **Giậm Giữ 1.5s** (Long Press) | *"Xóa"* / *"Xóa ảnh"* | — |
| **Hoàn thành / Lưu** | `F2` / `Ctrl + S` | — | *"Hoàn thành"* / *"Bệnh nhân tiếp"* | — |

---

## 4. QUY TRÌNH NGHIỆP VỤ VÒNG ĐỜI PHIÊN KHÁM (END-TO-END WORKFLOW)

### 🔵 BƯỚC 1: Chế độ Chờ, Tra Cứu Dạng Lưới & Kiểm duyệt (Standby, Grid Search & Validation)
1. **Khởi tạo:** Hệ thống ở Chế độ Chờ. Quét QR phiếu hoặc nhập thủ công 4 trường (`Mã BN`, `Họ tên`, `Năm sinh`, `Giới tính`).
2. **Tra cứu Hồ sơ Cũ dạng Lưới (`F5` Modal):**
   - Kích hoạt qua phím `F5`, nút GUI, giọng nói *"Tìm kiếm hồ sơ"*, hoặc quét QR phiếu cũ.
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
2. **Xử lý:** Lưu CSDL SQLite (`patients`, `photos`, `audit_logs`), xuất báo cáo PDF (nếu bật).
3. **Reset:** Xóa thông tin bệnh nhân trên màn hình, quay về Trạng thái Chờ cho bệnh nhân tiếp theo.
