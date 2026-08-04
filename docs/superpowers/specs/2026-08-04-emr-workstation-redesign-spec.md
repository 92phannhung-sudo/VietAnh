# THIẾT KẾ ĐẶC TẢ TÁI THIẾT KẾ GIAO DIỆN VÀ LUỒNG NGHIỆP VỤ HỆ THỐNG CHỤP ẢNH BỆNH ÁN ĐIỆN TỬ
*Dự án: 354 EMR Workstation (Offline Patient Photo Capture System)*
*Ngày hoàn thành đặc tả:* 2026-08-04  
*Trạng thái:* Chờ duyệt (User Review Gate)

---

## 1. MỤC TIÊU VÀ TỔNG QUAN TÁI THIẾT KẾ

### 1.1. Mục tiêu Cốt lõi
Chuyển đổi từ giao diện 4-Tab phân mảnh hiện tại sang **Bảng điều khiển Y tế Tập trung (Unified Clinical Cockpit)** trên 1 màn hình đơn duy nhất. Tối ưu hóa toàn bộ luồng nghiệp vụ lâm sàng từ A-Z với tiêu chí **0-Click trong khi chụp ảnh**, cho phép Bác sĩ / Kỹ thuật viên vận hành 100% rảnh tay qua Bàn đạp chân USB và Giọng nói Tiếng Việt Offline.

---

## 2. BỐ CỤC GIAO DIỆN TẬP TRUNG (UNIFIED CLINICAL COCKPIT)

Màn hình làm việc chính được chia làm 4 khu vực chức năng chính:

```
+---------------------------------------------------------------------------------------------------+
| TOP BAR: [🏥 354 EMR] | 👤 Bác sĩ: BS. Nguyễn Văn A | 🦶 Pedal: OK | 🎙️ Voice: OK | 📷 Camera: 1080p |
+---------------------------------------------------------------------------------------------------+
| STANDBY / PATIENT BANNER: Mã BN: [__________] | Họ Tên: [__________] | Năm Sinh: [____] | Nam/Nữ  |
+--------------------------------------------------+------------------------------------------------+
| LEFT PANEL (60%): LIVE CAMERA STREAM 1080p       | RIGHT PANEL (40%): BASELINE COMPARISON PANEL   |
|                                                  |                                                |
| - Live feed Logitech C920e                       | - Baseline Photo (Khám lần trước 15/07/2026)   |
| - Flash green border cue on capture (<150ms)     | - Side-by-side với Ảnh vừa chụp mới nhất        |
| - Voice waveform / Pedal trigger overlay         | - Thẻ nhãn phân loại (Da liễu, Tai Mũi Họng)   |
|                                                  |                                                |
+--------------------------------------------------+------------------------------------------------+
| BOTTOM PANEL: FILMSTRIP THUMBNAIL CAROUSEL & ACTION TOOLBAR                                       |
| [Ảnh #1]  [Ảnh #2]  [Ảnh #3]  | [F1 Tạo/Bắt đầu phiên mới]  [F2 Hoàn thành & Lưu]  [Delete Xóa]  |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. CƠ CHẾ ĐIỀU KHIỂN ĐA PHƯƠNG THỨC SONG SONG (PARALLEL MULTI-MODAL CONTROL)

Hệ thống duy trì đồng thời 3 kênh đầu vào lắng nghe ngầm trên toàn bộ ứng dụng mà không cần chuyển tiêu điểm chuột:

| Thao tác Lâm sàng | ⌨️ Bàn Phím / Phím Tắt | 🦶 Bàn Đạp Chân (FSM) | 🎙️ Giọng Nói Offline (Vosk) |
| :--- | :--- | :--- | :--- |
| **Bắt đầu Phiên Mới** | `F1` | — | *"Tạo phiên làm việc mới"* / *"Bắt đầu phiên mới"* |
| **Chụp Ảnh** | `Phím Cách (Space)` | **1 Giậm** (Single Tap) | *"Chụp"* / *"Chụp ảnh"* |
| **Xóa Ảnh Vừa Chụp** | `Delete` / `Backspace` | **Giậm Giữ 1.5s** (Long Press) | *"Xóa"* / *"Xóa ảnh"* |
| **Hoàn thành / Lưu** | `F2` / `Ctrl + S` | — | *"Hoàn thành"* / *"Bệnh nhân tiếp"* |

---

## 4. QUY TRÌNH NGHIỆP VỤ VÒNG ĐỜI PHIÊN KHÁM (END-TO-END WORKFLOW)

### 🔵 BƯỚC 1: Chế độ Chờ & Kiểm duyệt Thông tin (Standby QR & Input Mode)
1. **Bắt đầu:** Bác sĩ bấm nút GUI / bấm `F1` / đọc lệnh *"Tạo phiên làm việc mới"*. Camera và hệ thống chuyển sang **Standby QR Scan Mode**.
2. **Nạp dữ liệu 3 Kênh:**
   - **Quét QR/Barcode:** Đưa thẻ BHYT / CCCD / Phiếu khám HIS trước camera $\rightarrow$ Tự động giải mã và điền 4 trường: *Mã hồ sơ/phiếu*, *Họ tên*, *Năm sinh*, *Giới tính*.
   - **Nhập bàn phím:** Nhập trực tiếp vào các ô dữ liệu.
   - **Nhập giọng nói (Voice Fill):** Nói câu hợp nhất (ví dụ: *"Bệnh nhân Nguyễn Văn A năm sinh 1987 nam mã phiếu 12345"*) $\rightarrow$ Động cơ AI Vosk trích xuất thực thể và tự động điền vào 4 ô.
3. **Kiểm duyệt (Validation):** Hiển thị viền xanh lá (Valid) khi nhập đủ 4 trường.
4. **Khởi tạo Phiên:** Nút **"Bắt đầu phiên chụp"** khả dụng. Khi kích hoạt $\rightarrow$ Khởi tạo thư mục bệnh nhân, tải Ảnh Baseline cũ (nếu có) và chuyển sang Bước 2.

### 🟢 BƯỚC 2: Chụp Ảnh Rảnh Tay & So Sánh Baseline (Clinical Capture & Baseline Mode)
1. **Chụp Ảnh:** 1 Giậm bàn đạp / Voice *"Chụp ảnh"* / `Space`.
   - Camera nháy viền xanh nhạt + Phát âm thanh shutter.
   - Ảnh lưu ngầm đĩa đệm (< 150ms) và đẩy lên thanh Filmstrip ở dưới.
   - Nếu là Bệnh nhân Cũ: Ảnh vừa chụp tự động hiển thị song song bên cạnh Ảnh Baseline cũ trên Panel bên phải.
2. **Xóa Ảnh Vừa Chụp:** Giậm giữ bàn đạp (Long press) / Voice *"Xóa ảnh"* / `Delete`.
   - Đưa ảnh gần nhất trên Filmstrip vào thùng rác tạm.
   - Hiển thị Toast Notification *"Đã xóa ảnh #X"* mà không làm gián đoạn live stream camera.

### 🟡 BƯỚC 3: Hoàn Thành Phiên Khám & Reset (Session Completion & Reset Mode)
1. **Kích hoạt:** Bấm nút GUI / Phím `F2` / Voice *"Hoàn thành"* (hoặc *"Bệnh nhân tiếp"*).
2. **Xử lý:** Chốt danh sách ảnh, ghi CSDL SQLite (`patients`, `photos`, `audit_logs`), xuất file báo cáo PDF (nếu bật).
3. **Reset:** Xóa sạch dữ liệu hiển thị trên màn hình, quay về **Trạng thái Chờ Bắt Đầu Phiên Mới** cho bệnh nhân tiếp theo.

---

## 5. TỰ RÀ SOÁT VÀ XÁC NHẬN ĐẶC TẢ (SPEC SELF-REVIEW)

- [x] **Placeholder Scan:** Đã xác định đầy đủ các trường, tham số và phím tắt chuẩn, không có TBD/TODO.
- [x] **Tính nhất quán:** Luồng giao diện Cockpit và bộ phím/lệnh đa phương thức đã đồng bộ hoàn toàn với các tệp ADR và CONTEXT.
- [x] **Phạm vi:** Đã khoanh vùng chính xác 3 bước lâm sàng khép kín cho 1 phiên làm việc bệnh nhân.
- [x] **Tính rõ ràng:** Các quy tắc Validation, thời gian trễ shutter (<150ms) và hành vi nút giậm giữ đã được mô tả tường minh.
