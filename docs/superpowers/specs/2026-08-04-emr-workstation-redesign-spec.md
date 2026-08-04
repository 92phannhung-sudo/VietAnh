# THIẾT KẾ ĐẶC TẢ TÁI THIẾT KẾ GIAO DIỆN VÀ LUỒNG NGHIỆP VỤ HỆ THỐNG CHỤP ẢNH BỆNH ÁN ĐIỆN TỬ
*Dự án: 354 EMR Workstation (Offline Patient Photo Capture System)*
*Ngày cập nhật đặc tả:* 2026-08-04  
*Trạng thái:* Đang tinh chỉnh theo phản hồi người dùng (Bỏ Baseline)

---

## 1. MỤC TIÊU VÀ TỔNG QUAN TÁI THIẾT KẾ

### 1.1. Mục tiêu Cốt lõi
Chuyển đổi từ giao diện 4-Tab phân mảnh sang **Bảng điều khiển Y tế Tập trung (Unified Clinical Cockpit)** trên 1 màn hình đơn duy nhất. Tối ưu diện tích quan sát Camera Live Stream 1080p lên **100% chiều rộng màn hình (Bỏ phần so sánh Baseline)**, cho phép Bác sĩ / Kỹ thuật viên chụp ảnh tổn thương rõ nét nhất và vận hành 100% rảnh tay qua Bàn đạp chân USB và Giọng nói Tiếng Việt Offline.

---

## 2. BỐ CỤC GIAO DIỆN TẬP TRUNG MÀN HÌNH RỘNG (WIDESCREEN CLINICAL COCKPIT)

Màn hình làm việc chính được chia làm 3 khu vực chức năng dọc:

```
+---------------------------------------------------------------------------------------------------+
| TOP BAR: [🏥 354 EMR] | 👤 Bác sĩ: BS. Nguyễn Văn A | 🦶 Pedal: OK | 🎙️ Voice: OK | 📷 Camera: 1080p |
+---------------------------------------------------------------------------------------------------+
| STANDBY / PATIENT BANNER: Mã BN: [__________] | Họ Tên: [__________] | Năm Sinh: [____] | Nam/Nữ  |
| [🔍 F5 Tra Cứu Hồ Sơ Grid]  [🚀 F1 Bắt Đầu Phiên Chụp]                                            |
+---------------------------------------------------------------------------------------------------+
| CENTER PANEL (100% WIDESCREEN): LIVE CAMERA STREAM 1080p                                          |
|                                                                                                   |
| - Live feed Logitech C920e 1080p diện tích tối đa (Widescreen 1400x640px)                        |
| - Flash green border cue on capture (<150ms)                                                      |
| - Voice waveform / Pedal trigger overlay cues                                                     |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
| BOTTOM PANEL: FILMSTRIP THUMBNAIL CAROUSEL & ACTION TOOLBAR                                       |
| [Ảnh #1]  [Ảnh #2]  [Ảnh #3]  | [F1 Tạo/Bắt đầu phiên]  [F5 Tìm hồ sơ]  [F2 Hoàn thành] [Delete Xóa]|
+---------------------------------------------------------------------------------------------------+
```

---

## 3. CƠ CHẾ ĐIỀU KHIỂN ĐA PHƯƠNG THỨC SONG SONG (PARALLEL MULTI-MODAL CONTROL)

Hệ thống duy trì đồng thời 3 kênh đầu vào lắng nghe ngầm trên toàn bộ ứng dụng mà không cần chuyển tiêu điểm chuột:

| Thao tác Lâm sàng | ⌨️ Bàn Phím / Phím Tắt | 🦶 Bàn Đạp Chân (FSM) | 🎙️ Giọng Nói Offline (Vosk) | 📷 Camera / Scanner |
| :--- | :--- | :--- | :--- | :--- |
| **Bắt đầu Phiên Mới** | `F1` | — | *"Tạo phiên làm việc mới"* / *"Bắt đầu phiên mới"* | — |
| **Tìm Hồ Sơ Bệnh Nhân** | `F5` / `Ctrl + F` | — | *"Tìm kiếm hồ sơ"* / *"Tra cứu bệnh nhân"* | Quét mã QR/Barcode phiếu ban đầu |
| **Chụp Ảnh** | `Phím Cách (Space)` | **1 Giậm** (Single Tap) | *"Chụp"* / *"Chụp ảnh"* | — |
| **Xóa Ảnh Vừa Chụp** | `Delete` / `Backspace` | **Giậm Giữ 1.5s** (Long Press) | *"Xóa"* / *"Xóa ảnh"* | — |
| **Hoàn thành / Lưu** | `F2` / `Ctrl + S` | — | *"Hoàn thành"* / *"Bệnh nhân tiếp"* | — |

---

## 4. QUY TRÌNH NGHIỆP VỤ VÒNG ĐỜI PHIÊN KHÁM (END-TO-END WORKFLOW)

### 🔵 BƯỚC 1: Chế độ Chờ, Tra Cứu Dạng Lưới & Kiểm duyệt (Standby, Grid Search & Validation Mode)
1. **Bắt đầu:** Bác sĩ bấm nút GUI / bấm `F1` / đọc lệnh *"Tạo phiên làm việc mới"*. Camera và hệ thống chuyển sang **Standby QR Scan Mode**.
2. **Tra cứu Hồ sơ Cũ dạng Lưới (Grid Search):**
   - Kích hoạt: Nút GUI **"🔍 F5 Tìm hồ sơ"**, phím **`F5`**, Giọng nói *"Tìm kiếm hồ sơ"*, hoặc **Quét mã QR/Barcode trên phiếu ban đầu**.
   - Bộ lọc Optional: *Mã hồ sơ/phiếu*, *Họ tên* (không dấu), *Năm sinh*, *Giới tính*.
   - Kết quả Lưới (Grid Cards): Thẻ thông tin BN kèm ngày khám trước và số ảnh.
3. **Kiểm duyệt (Validation):** Viền xanh lá (Valid) khi đủ 4 trường bắt buộc.
4. **Khởi tạo Phiên:** Nút **"Bắt đầu phiên chụp"** khả dụng. Khi kích hoạt $\rightarrow$ Chuyển sang Bước 2.

### 🟢 BƯỚC 2: Chụp Ảnh Rảnh Tay Màn Hình Rộng 100% (Widescreen Live Capture Mode)
1. **Chụp Ảnh:** 1 Giậm bàn đạp / Voice *"Chụp ảnh"* / `Space`.
   - Camera nháy viền xanh nhạt + Phát âm thanh shutter.
   - Ảnh lưu ngầm đĩa đệm (< 150ms) và đẩy lên thanh Filmstrip ở dưới.
   - Diện tích camera mở rộng toàn màn hình (100% Widescreen), không bị chia cắt bởi ô Baseline.
2. **Xóa Ảnh Vừa Chụp:** Giậm giữ bàn đạp (Long press) / Voice *"Xóa ảnh"* / `Delete`.
   - Đưa ảnh gần nhất trên Filmstrip vào thùng rác tạm.
   - Hiển thị Toast Notification *"Đã xóa ảnh #X"* mà không làm gián đoạn live stream camera.

### 🟡 BƯỚC 3: Hoàn Thành Phiên Khám & Reset (Session Completion & Reset Mode)
1. **Kích hoạt:** Bấm nút GUI / Phím `F2` / Voice *"Hoàn thành"* (hoặc *"Bệnh nhân tiếp"*).
2. **Xử lý:** Chốt danh sách ảnh, ghi CSDL SQLite (`patients`, `photos`, `audit_logs`), xuất file báo cáo PDF (nếu bật).
3. **Reset:** Xóa sạch dữ liệu hiển thị trên màn hình, quay về **Trạng thái Chờ Bắt Đầu Phiên Mới** cho bệnh nhân tiếp theo.
