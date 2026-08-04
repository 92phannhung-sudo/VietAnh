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
| [🔍 F5 Tìm Hồ Sơ] [📁 Lịch Sử Khám Dạng Lưới]                                                   |
+--------------------------------------------------+------------------------------------------------+
| LEFT PANEL (60%): LIVE CAMERA STREAM 1080p       | RIGHT PANEL (40%): BASELINE COMPARISON PANEL   |
|                                                  |                                                |
| - Live feed Logitech C920e                       | - Baseline Photo (Khám lần trước 15/07/2026)   |
| - Flash green border cue on capture (<150ms)     | - Side-by-side với Ảnh vừa chụp mới nhất        |
| - Voice waveform / Pedal trigger overlay         | - Thẻ nhãn phân loại (Da liễu, Tai Mũi Họng)   |
|                                                  |                                                |
+--------------------------------------------------+------------------------------------------------+
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
   - **Kích hoạt:** Nút GUI **"🔍 F5 Tìm hồ sơ"**, phím **`F5`**, Giọng nói *"Tìm kiếm hồ sơ"* / *"Tra cứu bệnh nhân"*, hoặc **Quét mã QR/Barcode trên phiếu ban đầu**.
   - **Thanh Bộ Lọc Tìm Kiếm (Optional Filter Bar):**
     - Cho phép lọc linh hoạt theo 4 trường tùy chọn: *Mã hồ sơ/phiếu*, *Họ tên* (hỗ trợ không dấu), *Năm sinh*, *Giới tính*.
   - **Giao diện Kết quả Dạng Lưới (Grid View):**
     - Hiển thị danh sách các hồ sơ bệnh án cũ dưới dạng ô Lưới (Grid Card). Mỗi thẻ hồ sơ bao gồm: Mã BN, Họ tên, Ngày khám gần nhất, Số lượng ảnh và **Thumbnail Ảnh Baseline mới nhất**.
   - **Thao tác Chọn:** Chọn 1 thẻ hồ sơ $\rightarrow$ Tự động nạp thông tin bệnh nhân + Ảnh Baseline cũ vào Cockpit và sẵn sàng cho phiên chụp mới.
3. **Nhập & Kiểm duyệt (Validation):** Khi thông tin bệnh nhân được nạp từ QR, Tìm kiếm Lưới hoặc Nhập tay/Giọng nói $\rightarrow$ Các ô hiển thị viền xanh lá (Valid) khi đủ 4 trường bắt buộc.
4. **Khởi tạo Phiên:** Nút **"Bắt đầu phiên chụp"** khả dụng. Khi kích hoạt $\rightarrow$ Khởi tạo thư mục bệnh nhân và chuyển sang Bước 2.

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

- [x] **Placeholder Scan:** Đã xác định đầy đủ bộ lọc optional (Mã BN, Họ tên, Năm sinh, Giới tính), phím tắt `F5`, quét QR phiếu ban đầu và Grid view.
- [x] **Tính nhất quán:** Luồng Tra cứu dạng Lưới, Giao diện Cockpit và Bộ lệnh Đa phương thức hoàn toàn đồng bộ với ADR và CONTEXT.
- [x] **Phạm vi:** Đã khoanh vùng chính xác quy trình 3 bước khép kín.
- [x] **Tính rõ ràng:** Đã làm rõ cơ chế lọc Optional và trả kết quả dạng Lưới danh sách hồ sơ cũ.
