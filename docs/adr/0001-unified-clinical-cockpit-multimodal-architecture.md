# ADR 0001: Kiến trúc Giao diện Tập trung Unified Clinical Cockpit & Điều khiển Đa Phương thức Song song

* **Trạng thái:** Accepted
* **Ngày quyết định:** 2026-08-04
* **Bối cảnh:** Bác sĩ tại phòng khám y tế (354 Hospital) cần chụp ảnh bệnh nhân rảnh tay nhanh chóng, không bị gián đoạn do chuyển tab hoặc thao tác chuột rườm rà. Hệ thống cũ phân chia làm 4 Tab ngang độc lập gây tốn thao tác nhấp chuột.

## Quyết định Kiến trúc

1. **Chuyển sang Giao diện Màn hình Đơn Tập trung (Unified Clinical Cockpit):**
   Gộp toàn bộ luồng Quét/Nhập Bệnh Nhân, Camera Live Feed 1080p, So sánh Ảnh Baseline cũ, Gắn thẻ vùng lâm sàng và Thanh cuộn ảnh vừa chụp (Filmstrip) vào **1 màn hình duy nhất**. Loại bỏ hoàn toàn việc phải nhấp chuột chuyển tab trong ca khám.

2. **Cơ chế Điều khiển Đa Phương thức Song song (Parallel Multi-Modal Control):**
   Hệ thống duy trì đồng thời 3 kênh điều khiển ngầm ở mọi thời điểm:
   - **Bàn phím / Barcode Scanner:** Phím `Space` (Chụp), `Delete` (Xóa), `F1` (Tạo phiên mới), `F2` (Hoàn thành phiên).
   - **Bàn đạp chân USB (Foot Pedal FSM):** 1 Giậm (Chụp ảnh), Giậm giữ Long Press (Xóa ảnh gần nhất).
   - **Giọng nói tiếng Việt Offline (Vosk ASR Engine):** Lắng nghe ngầm câu lệnh *"Chụp ảnh"*, *"Xóa ảnh"*, *"Tạo phiên làm việc mới"*, *"Hoàn thành"*, *"Bệnh nhân tiếp"*.

3. **Luồng Chuyển Trạng thái Vòng đời Phiên Bệnh Nhân (Patient Session State Machine):**
   - **Trạng thái 1: Standby QR & Input Mode (Chờ nạp BN):** Lắng nghe quét QR/CCCD/BHYT, nhập tay hoặc nhập bằng giọng nói. Validate hợp lệ 4 trường dữ liệu (Mã phiếu, Họ tên, Năm sinh, Giới tính) trước khi cho phép bắt đầu.
   - **Trạng thái 2: Active Capture & Baseline Mode (Đang chụp & So sánh):** Chụp ngầm < 150ms, chớp viền xanh + hiệu ứng âm thanh shutter, hiển thị ngay lên Filmstrip và màn hình so sánh Baseline.
   - **Trạng thái 3: Session Completion & Reset Mode (Chốt phiên & Reset):** Lưu CSDL SQLite, xuất PDF (nếu bật) và tự động dọn dẹp màn hình quay về Trạng thái 1.

## Hậu quả & Đánh đổi

* **Tích cực:** Tốc độ khám chữa bệnh tăng đáng kể (0-click workflow trong lúc chụp), thao tác rảnh tay mượt mà.
* **Cần lưu ý:** Cần quản lý đồng bộ trạng thái (State Threading) giữa PySide6 Qt GUI thread, OpenCV camera thread, Vosk speech thread và Global keyboard/pedal hooks để tránh xung đột sự kiện (Race conditions).
