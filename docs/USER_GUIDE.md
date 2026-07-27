# HƯỚNG DẪN SỬ DỤNG VÀ VẬN HÀNH HỆ THỐNG CHỤP ẢNH BỆNH ÁN

Tài liệu này hướng dẫn chi tiết cách khởi chạy, cấu hình phần cứng và vận hành giao diện 4 Tab của phần mềm chụp ảnh bệnh nhân rảnh tay.

---

## 1. Hướng Dẫn Khởi Chạy

### Khởi chạy phần mềm
Mở cửa sổ **PowerShell** tại thư mục ứng dụng (`c:\Users\vinhd\Desktop\VietAnh`) và chạy:
```powershell
.venv\Scripts\python main.py
```

### 2. Thoát Ứng dụng An toàn
* Bên dưới thanh Sidebar điều hướng bên trái có nút bấm màu đỏ **🚪  Thoát Ứng Dụng**.
* Khi bấm nút này (hoặc bấm dấu nút **X** ở góc trên phải màn hình), phần mềm sẽ hiện hộp thoại xác nhận và tự động thu dọn tài nguyên, đóng luồng camera, mic và CSDL một cách an toàn.

---

## 2. Quy Trình Vận Hành Với Giao Diện 4 Tab

### [ Tab 1 ] Chụp Ảnh Bệnh Nhân & So Sánh Màn Hình Đôi
1. **Chọn Người Thao Tác (Ca làm việc):** Ở đầu ca làm việc, Bác sĩ/Kỹ thuật viên chọn tên mình trên thanh thông tin để phần mềm tự động gán tên người chụp vào từng bức ảnh.
2. **Quét Mã Vạch Bệnh Án:** Đưa phiếu khám chứa mã vạch/QR trước camera. Máy kêu "Tít" và tự động load bệnh án.
3. **So Sánh Màn Hình Đôi (Split-Screen):** Màn hình hiển thị luồng Camera trực tiếp bên trái $\leftrightarrow$ Ảnh mốc đợt 1 bên phải để bác sĩ nhìn đối chiếu căn đúng tư thế chụp.
4. **Chụp ảnh:** 
   * Giậm chân lên bàn đạp chân (`F13`).
   * Hô từ **"Chụp"** trước microphone.
   * Hoặc bấm nút **CHỤP ẢNH** màu xanh trên màn hình.

### [ Tab 2 ] Tra Cứu & Báo Cáo Bệnh Án
* Nhập Mã BA hoặc Họ tên vào ô tìm kiếm.
* Chuyển đổi giữa góc nhìn **Dạng Timeline theo Ngày khám** và **Dạng Lưới Ảnh Tổng hợp**.
* Bấm nút **Xuất Báo Cáo PDF / In Phiếu Ảnh** để in hoặc xuất file báo cáo y tế.

### [ Tab 3 ] Quản Lý Nhân Viên & Nhật Ký Kiểm Toán (Audit Logs)
* **Chọn Ca Làm Việc:** Chọn nhân viên trực tiếp thao tác hiện tại.
* **Danh Mục Nhân Viên:** Khai báo danh sách Bác sĩ, Kỹ thuật viên, Điều dưỡng.
* **Nhật Ký Kiểm Toán (Audit Logs):** Tra cứu lịch sử vận hành (Ai đã quét mã nào, chụp ảnh nào, lúc mấy giờ, qua bàn đạp hay giọng nói).

### [ Tab 4 ] Cài Đặt Hệ Thống & Giao Diện
* **Chọn Camera Vật Lý Thật:** Danh sách tự động quét hiển thị chính xác tên thương hiệu phần cứng thật (ví dụ: `Logi Webcam C920e (Cổng Index 0)`).
* **Chọn Microphone Giọng Nói:** Chọn giữa Micro Venfish, Tai nghe Bluetooth, Micro C920e stereo hoặc Jack 3.5mm AUX.
* **🔍 Nút QUÉT PHẦN CỨNG (Scan Hardware):**
  * Ngay khi bấm nút, phần mềm hiển thị **Bảng Tiến Trình Loading Progress Modal** mượt mà không gây treo màn hình.
  * Tự động quét kiểm tra chính xác **4 phần cứng vật lý chính** (Camera, Micro, Bàn đạp chân, Cổng COM).
  * **Lưu CSDL Tự Động:** Kết quả quét được tự động lưu vào CSDL SQLite (`app.db`). Trong các lần khởi động tiếp theo, phần mềm tự động nạp lại cấu hình mượt mà trong $<5\text{ms}$ mà không cần mất thời gian quét lại.
* **🛠️ Hệ Thống Nút TEST PHẦN CỨNG TƯƠNG TÁC TRỰC TIẾP:**
  * **[ 🛠️ Test Camera ]**: Mở cửa sổ xem video trực tiếp + **Thử Quét Mã QR/Mã Vạch**. Đưa mã vạch trước camera $\rightarrow$ Máy kêu "Tít" và báo badge xanh `Đã Quét Mã: [ PHCN2647781 ] - OK`.
  * **[ 🛠️ Test Microphone ]**: Mở thanh đo âm lượng RMS (0-100%) + **Thử Hô Lệnh Giọng Nói**. Nói các từ `"Chụp"`, `"Xóa"`, `"Tiếp"`, `"Xem"` $\rightarrow$ Cửa sổ báo badge xanh `Đã Nhận Lệnh: "CHỤP" - OK`.
  * **[ 🛠️ Test Bàn Đạp Chân ]**: Mở bảng danh sách 4 cử chỉ (1 giậm, 2 giậm, 3 giậm, nhấn giữ). Giậm chân lên bàn đạp $\rightarrow$ Cửa sổ tự động tích `[✓]` xanh tương ứng vào cử chỉ vừa giậm.
  * **[ 🛠️ Test Cổng COM ]**: Gửi tín hiệu kiểm tra kết nối RS232/USB Serial $\rightarrow$ Báo `Phản Hồi Cổng COM1: OK`.
* **Đổi Chế Độ Màu Giao Diện:** Chuyển đổi giữa **Dark Slate (Mặc định)** và **Light Clinical (Sáng Y tế)**.
