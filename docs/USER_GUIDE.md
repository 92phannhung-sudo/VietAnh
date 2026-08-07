# HƯỚNG DẪN SỬ DỤNG VÀ VẬN HÀNH HỆ THỐNG CHỤP ẢNH BỆNH ÁN

Tài liệu này hướng dẫn chi tiết cách khởi chạy, cấu hình phần cứng và vận hành giao diện 4 Tab của phần mềm chụp ảnh bệnh nhân rảnh tay.

> **Luồng phiên Tab 1 (F1/F2/F4, Voice Intake, F5 lưới):** xem chi tiết trong `docs/SPEC_HANDS_FREE_SESSION_V1.md` và `CONTEXT.md`.

---

## 1. Hướng Dẫn Khởi Chạy

### Khởi chạy phần mềm
Mở cửa sổ **PowerShell** tại thư mục ứng dụng và chạy:
```powershell
.venv\Scripts\python main.py
```

### 2. Thoát Ứng dụng An toàn
* Bên dưới thanh Sidebar điều hướng bên trái có nút bấm màu đỏ **🚪  Thoát Ứng Dụng**.
* Khi bấm nút này (hoặc bấm dấu nút **X** ở góc trên phải màn hình), phần mềm sẽ hiện hộp thoại xác nhận và tự động thu dọn tài nguyên, đóng luồng camera, mic và CSDL một cách an toàn.

---

## 2. Quy Trình Vận Hành Với Giao Diện 4 Tab

### [ Tab 1 ] Clinical Cockpit — phiên khám rảnh tay

1. **F1 — Mở phiên:** bật camera / mic / pedal (thoát Standby).  
2. **Nhập hồ sơ** (một trong các cách):  
   * Quét barcode → mở **lưới tìm hồ sơ** (không tự ghi form). Chọn dòng hoặc confirm BN mới.  
   * **F5** → lưới hồ sơ gần đây / lọc theo mã–tên–năm sinh–giới tính.  
   * Gõ tay 4 field: Mã BN, Họ tên, Năm sinh, Giới tính.  
   * Nói pattern demography (họ tên / năm sinh / giới tính) — **giọng không ghi Mã BN**.  
3. Đủ 4 field → Ready. **F2 · Bắt đầu chụp** khóa hồ sơ (Locked Capture).  
4. **Chụp ảnh** (chỉ khi Locked):  
   * Bàn đạp chân = **chỉ chụp** (không xóa / không đổi BN).  
   * Phím **Space** hoặc nói **"chụp"**.  
5. **Xóa ảnh gần nhất:** phím **Delete** hoặc nói **"xóa"** (không dùng pedal). Có hoàn tác ~5 giây trên status bar.  
6. **F4 · Kết thúc phiên** → lưu hồ sơ, tắt thiết bị, về Standby. BN tiếp theo phải F1 lại.  
7. Alias thoại kết thúc: *"kết thúc phiên"*, *"hoàn thành"*, *"chuyển bệnh nhân mới"*.

### [ Tab 2 ] Thư mục bệnh án (xem / duyệt)

* Tìm theo Mã BA hoặc Họ tên để **lọc thư mục** (không thay F5 tìm hồ sơ phiên).  
* Mở thư mục BN → xem ảnh; **xóa từng ảnh** có hộp thoại xác nhận.  
* **Mở ở Tab Chụp:** chỉ khi đang có phiên và cùng BN (hoặc form trống); BN khác bị chặn — cần F4 rồi F1.  
* **Không xuất PDF** trong v1.

### [ Tab 3 ] Quản Lý Nhân Viên & Nhật Ký Kiểm Toán (Audit Logs)
* **Chọn Ca Làm Việc:** Chọn nhân viên trực tiếp thao tác hiện tại.
* **Danh Mục Nhân Viên:** Khai báo danh sách Bác sĩ, Kỹ thuật viên, Điều dưỡng.
* **Nhật Ký Kiểm Toán (Audit Logs):** Tra cứu lịch sử vận hành (Ai đã quét mã nào, chụp ảnh nào, lúc mấy giờ, qua bàn đạp hay giọng nói).

### [ Tab 4 ] Cài Đặt Hệ Thống & Giao Diện
* **Chọn Camera / Microphone / Pedal** và các nút Test phần cứng.  
* **Từ điển giọng nói toàn cục:** bảng phrase → intent; Lưu áp dụng cho mọi ca (không override theo nhân viên trong v1).  
* **Đổi theme** Dark Slate / Light Clinical; thư mục lưu ảnh; URL OTA (nếu bật).

---

## 3. Phím tắt phiên khám (tóm tắt)

| Phím | Hành động |
|---|---|
| F1 | Mở / đóng phiên (Standby ↔ Intake) |
| F2 | Bắt đầu chụp (khóa hồ sơ) khi Ready |
| F4 | Kết thúc phiên → Standby |
| F5 | Mở lưới tìm hồ sơ (Intake/Ready) |
| Space | Chụp (Locked) |
| Delete | Xóa ảnh gần nhất (Locked) |

---

## 4. Quy Trình Cài Đặt Offline Trọn Gói Cho Máy Bệnh Viện (Windows 10/11 x64)

### 🚀 Cài Đặt 1-Click (Dành Cho Máy Chưa Cài Python):
1. Giải nén tệp **`PatientCaptureApp_v1.0_Offline.zip`** (hoặc chép thư mục `PatientCaptureApp_v1.0_Offline` từ USB).
2. Nhấp chuột phải vào tệp **`install_admin.bat`** và chọn **`Run as administrator`** (Chạy dưới quyền Quản trị viên).
3. Kịch bản cài đặt tự động thực hiện:
   * Tạo thư mục cài đặt hệ thống tại `C:\Program Files\PatientCaptureApp`.
   * Kiểm tra cơ sở dữ liệu bệnh nhân cũ tại `%APPDATA%\PatientCaptureApp\patients.db`. **Nếu đã có dữ liệu cũ, hệ thống giữ nguyên 100% (KHÔNG GHI ĐÈ).**
   * Tự động tạo Icon lối tắt **"Chụp ảnh Bệnh nhân - BV 354"** ngoài Màn hình chính (Desktop) và Start Menu.
4. Nhấp đúp vào Icon ngoài Desktop để mở ứng dụng lập tức.

### 🗑️ Gỡ Bỏ Ứng Dụng:
Nhấp chuột phải vào tệp **`uninstall_admin.bat`** và chọn **`Run as administrator`**. Kịch bản sẽ xóa lối tắt, dọn dẹp thư mục cài đặt và hỏi ý kiến người dùng trước khi quyết định giữ lại hay xóa CSDL bệnh nhân.

### 📦 Quy Trình Đóng Gói Bản Cập Nhật Mới (Dành Cho Lập Trình Viên):
Mỗi khi chỉnh sửa mã nguồn Python, chạy duy nhất 1 lệnh:
```cmd
.venv\Scripts\python build_package.py
```
Toàn bộ phần mềm sẽ được biên dịch lại thành gói `PatientCaptureApp_v1.0_Offline.zip` mới trong thư mục `dist/` sẵn sàng sao chép sang USB.
