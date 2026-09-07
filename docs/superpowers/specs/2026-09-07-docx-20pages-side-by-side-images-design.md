# Thiết Kế Kỹ Thuật: Bố Cục Ảnh Hàng Ngang (Side-by-Side) & Tối Ưu Báo Cáo 20 Trang
*Chuẩn hóa tài liệu Thuyết minh sáng kiến M7 — Bệnh viện Quân y 354*

## 1. Mục Tiêu & Bối Cảnh
* **Vấn đề hiện tại:** Tài liệu sau khi chuẩn hóa hiện dài 23 trang. Các cụm ảnh (Ảnh 3 gồm 2 ảnh, Ảnh 7 gồm 3 ảnh) đang được xếp dọc nối tiếp nhau, chiếm nhiều chiều cao và đẩy các trang lân cận bị trống nhiều (nhiều trang chỉ có 4–9 dòng). Phần kết luận và chữ ký đang nằm ở trang 23.
* **Mục tiêu người dùng:**
  1. Gom các vị trí có 2–3 ảnh vào chung 1 hàng (side-by-side).
  2. Tối ưu tổng số trang của tài liệu về đúng **20 trang** tròn trọn vẹn, chuyên nghiệp.

---

## 2. Thiết Kế Bố Cục Ảnh Hàng Ngang (Side-by-Side Layout)

### 2.1. Cụm Ảnh 3 (2 ảnh) — Phần cứng thiết bị ghi hình
* **Các ảnh thành phần:**
  * `Ảnh 3.2.jpg`: Webcam Logitech C920e độ phân giải Full HD (Ảnh vuông 1:1).
  * `Ảnh 3.jpg`: Vị trí lắp đặt webcam cố định trong hộp chụp (Ảnh đứng 3:4).
* **Giải pháp bố cục:**
  * Tạo bảng 2 hàng 2 cột, không viền (`w:val="none"`), căn giữa trang, chiều rộng tổng 16.5 cm.
  * Mỗi cột rộng ~8.25 cm.
  * Hàng 1 (Ảnh): Cột 1 chứa Ảnh 3a (rộng ~5.5 cm), Cột 2 chứa Ảnh 3b (rộng ~5.5 cm). Cả 2 ảnh căn giữa ô.
  * Hàng 2 (Chú thích): Cột 1 ghi *"Ảnh 3a: Webcam Logitech C920e độ phân giải Full HD"*, Cột 2 ghi *"Ảnh 3b: Vị trí lắp đặt trong hộp chụp"*. Phông Times New Roman 10pt, nghiêng, căn giữa ô.
  * Thiết lập thuộc tính `w:cantSplit` cho các hàng để đảm bảo ảnh và chú thích không bị tách trang.

### 2.2. Cụm Ảnh 7 (3 ảnh) — Quy trình và giao diện phần mềm
* **Các ảnh thành phần:**
  * `Ảnh 7.1.jpg`: Thao tác tiếp nhận và chụp lưu mẫu (Ảnh đứng 3:4).
  * `Ảnh 7.2.jpg`: Giao diện tiếp nhận thông tin (Ảnh đứng 3:4).
  * `Ảnh 7.3.jpg`: Hồ sơ bằng chứng số (Ảnh ngang 4:3).
* **Giải pháp bố cục:**
  * Tạo bảng 2 hàng 3 cột, không viền (`w:val="none"`), căn giữa trang, chiều rộng tổng 16.5 cm.
  * Mỗi cột rộng 5.5 cm.
  * Hàng 1 (Ảnh): Cột 1 chứa Ảnh 7a (rộng ~4.8 cm), Cột 2 chứa Ảnh 7b (rộng ~4.8 cm), Cột 3 chứa Ảnh 7c (rộng ~4.8 cm). Cả 3 ảnh căn giữa ô.
  * Hàng 2 (Chú thích): Cột 1 ghi *"Ảnh 7a: Tiếp nhận và chụp lưu mẫu"*, Cột 2 ghi *"Ảnh 7b: Giao diện tiếp nhận"*, Cột 3 ghi *"Ảnh 7c: Hồ sơ bằng chứng số"*. Phông Times New Roman 10pt, nghiêng, căn giữa ô.

---

## 3. Chiến Lược Tối Ưu Bố Cục Để Đạt Chuẩn Đúng 20 Trang

Để tài liệu co gọn từ 23 trang về đúng **20 trang** mà vẫn tuân thủ 100% Nghị định 30/2020/NĐ-CP:
1. **Ghép hàng ảnh:** Tiết kiệm trực tiếp 2 trang (từ 23 xuống 21 trang).
2. **Kích thước ảnh đơn (Ảnh 1, 2, 4, 5, 6):** Điều chỉnh từ 8.5–9.0 cm về 6.0–6.5 cm (vừa vặn, sắc nét, không chiếm quá nửa trang in).
3. **Giãn dòng & khoảng cách đoạn:**
   * Giãn dòng: Đặt `1.15 lines` (NĐ 30/2020 quy định từ 1.0 đến 1.5 lines).
   * Spacing after đoạn thân bài: `Pt(1.5)` (thay vì `Pt(2)`).
   * Spacing đề mục cấp 1, 2, 3: `space_before = Pt(4)`, `space_after = Pt(2)`.
4. **Phân bổ trang 20 (Trang kết):**
   * Toàn bộ 2 đoạn văn kết luận của **Mục 5 (Khả năng áp dụng và nhân rộng)**.
   * Dòng địa danh ngày tháng: *Hà Nội, ngày 25 tháng 8 năm 2025* (in nghiêng, căn phải).
   * Khối chữ ký trang trọng: **ĐẠI DIỆN NHÓM TÁC GIẢ** / **Nguyễn Việt Anh**.
   * Không còn tình trạng trang mồ côi (trang 21).

---

## 4. Kế Hoạch Kiểm Thử & Xác Minh (Verification)
1. **Unit Test:**
   * Kiểm tra hàm chèn bảng ảnh 2 cột và 3 cột: Đảm bảo bảng không viền, các ô chứa đúng ảnh và chú thích, không phát sinh viền đen.
2. **Kiểm tra số trang thực tế:**
   * Chuyển đổi đối soát file `.docx` sang `.pdf` bằng headless LibreOffice và kiểm tra `pdfinfo`: Số trang phải đạt chính xác **20 trang**.
3. **Kiểm tra Typography & Trực quan:**
   * Không có lỗi tràn trang mồ côi.
   * Tất cả ảnh rõ nét, không bị bóp méo tỷ lệ (aspect ratio).
