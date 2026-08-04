# CONTEXT - GLOSSARY & DOMAIN MODEL
*Dự án Hệ thống Chụp ảnh Bệnh án Điện tử (354 EMR Workstation)*

## 1. Các Khái niệm Miền (Domain Terms)

### Parallel Multi-Modal Control (Điều khiển Đa Phương thức Song song)
Khả năng hệ thống lắng nghe và phản hồi đồng thời 3 kênh điều khiển ngầm trên toàn bộ ứng dụng:
1. **Bàn phím & Đầu đọc Mã vạch (Keyboard & Barcode Scanner):** Phím tắt F1-F12, phím điều hướng và quét mã vạch HID.
2. **Bàn đạp chân (USB Foot Pedal):** Động cơ FSM xử lý các thao tác giậm chân (1 giậm, giậm giữ long press).
3. **Giọng nói tiếng Việt Offline (Offline Voice AI):** Luồng ASR nhận diện câu lệnh giọng nói tiếng Việt liên tục.

### Standby QR & Input Mode (Chế độ Chờ Bắt Đầu Phiên Mới)
Trạng thái hệ thống đứng chờ để nạp thông tin Bệnh nhân qua 3 hình thức:
- Quét mã QR/Barcode (CCCD, BHYT, Phiếu khám HIS).
- Nhập thủ công bằng Bàn phím.
- Nhập bằng Giọng nói Tiếng Việt (Tên, Năm sinh, Giới tính, Mã phiếu).
Hệ thống bắt buộc phải kiểm duyệt hợp lệ (Validate) đầy đủ các trường dữ liệu trước khi chuyển sang chế độ chụp ảnh.

### Clinical Capture Engine (Động cơ Chụp & So Sánh Lâm Sàng)
Chế độ chụp rảnh tay với độ trễ < 150ms:
- **Kích hoạt Chụp:** 1 Giậm / Giọng nói *"Chụp ảnh"* / Phím `Space`. Chớp viền xanh nhạt + phát hiệu ứng âm thanh shutter.
- **Lưu & Phim cuộn:** Lưu ngầm vào đĩa và đẩy ảnh mới lên thanh cuộn Filmstrip dưới cùng.
- **So sánh Baseline:** Tự động hiển thị ảnh mới chụp song song với Ảnh Baseline cũ (nếu là bệnh nhân tái khám).

### Deletion & Trash Lifecycle (Luồng Xóa & Thùng Rác Tạm)
- **Kích hoạt Xóa:** Giậm giữ bàn đạp (Long press) / Giọng nói *"Xóa ảnh"* / Phím `Delete`.
- **Thao tác:** Di chuyển ảnh gần nhất trên Filmstrip vào thùng rác tạm mà không làm ngắt luồng live camera. Hiển thị Toast Notification nhẹ *"Đã xóa ảnh #X"*.

### Session Lifecycle & Report Export (Vòng đời Phiên Khám & Xuất Báo Cáo)
Quy trình chốt phiên làm việc khi bấm nút GUI / bấm `F2` / đọc *"Hoàn thành"*:
1. Chốt danh sách ảnh và đồng bộ CSDL SQLite (`patients`, `photos`, `audit_logs`).
2. Xuất báo cáo PDF kết quả chụp ảnh bệnh nhân (nếu được bật).
3. Tự động xóa dữ liệu khỏi màn hình và trở về **Chế độ Chờ Bắt Đầu Phiên Mới** cho bệnh nhân tiếp theo.
