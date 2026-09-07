# Kế Hoạch Triển Khai: Bố Cục Ảnh Hàng Ngang (Side-by-Side) & Chuẩn Hóa Báo Cáo 20 Trang

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triển khai tính năng gom các cụm 2-3 ảnh vào cùng 1 hàng ngang (side-by-side) bằng bảng ẩn viền và tinh chỉnh khoảng cách để toàn bộ tài liệu M7 đạt chính xác 20 trang theo Nghị định 30/2020/NĐ-CP.

**Architecture:** Bổ sung hàm `insert_side_by_side_image_table` vào `scripts/format_m7_document.py` sử dụng bảng 2 hàng (hàng 1 ảnh, hàng 2 caption) có thuộc tính không viền (`tcBorders: none`) và khóa trang `cantSplit`. Tinh chỉnh `apply_typography` với `line_spacing = 1.15` và `space_after = Pt(1.5)` để toàn bộ nội dung Phần 5 và bảng chữ ký kết thúc trọn vẹn tại trang 20.

**Tech Stack:** Python 3, `python-docx 1.2.0`, OpenXML (`docx.oxml`), `unittest`, LibreOffice headless (`soffice`), `pdfinfo`.

---

### Task 1: Hàm tạo bảng ảnh hàng ngang ẩn viền & Cập nhật chèn cụm ảnh 3 và 7

**Files:**
- Modify: `scripts/format_m7_document.py`
- Test: `tests/test_format_m7_document.py`

**Interfaces:**
- Produces: `insert_side_by_side_image_table(doc, paragraph, img_items, total_width_cm=16.5)`
  - `img_items`: List các tuple `(img_path, caption_text, width_cm)`

- [ ] **Step 1: Viết failing test cho `insert_side_by_side_image_table`**
  - Trong `tests/test_format_m7_document.py`: thêm `test_insert_side_by_side_image_table` kiểm tra tạo bảng 2 cột không viền cho Ảnh 3a và 3b.

- [ ] **Step 2: Chạy test để xác nhận Red (Failure)**
  - Lệnh: `python3 -m unittest tests/test_format_m7_document.py`
  - Kết quả mong đợi: FAIL do chưa có hàm `insert_side_by_side_image_table`.

- [ ] **Step 3: Triển khai hàm `insert_side_by_side_image_table` và cập nhật `insert_images_and_captions`**
  - Viết hàm `set_cell_no_border(cell)` và `insert_side_by_side_image_table`.
  - Cập nhật cấu hình chèn ảnh:
    - Ảnh 1: rộng 6.5cm
    - Ảnh 2: rộng 5.5cm
    - Cụm Ảnh 3: Bảng 2 cột (Ảnh 3a: 5.5cm, Ảnh 3b: 5.5cm)
    - Ảnh 4: rộng 6.5cm
    - Ảnh 5: rộng 6.5cm
    - Ảnh 6: rộng 6.2cm
    - Cụm Ảnh 7: Bảng 3 cột (Ảnh 7a: 4.8cm, Ảnh 7b: 4.8cm, Ảnh 7c: 4.8cm)

- [ ] **Step 4: Chạy test để xác nhận Green (Pass)**
  - Lệnh: `python3 -m unittest tests/test_format_m7_document.py`
  - Kết quả mong đợi: PASS.

- [ ] **Step 5: Git commit lẻ**
  - Lệnh: `git commit -m "feat(format): add side-by-side image table formatting for multi-image clusters"`

---

### Task 2: Tinh chỉnh Typography và Spacing hướng tới mục tiêu đúng 20 trang

**Files:**
- Modify: `scripts/format_m7_document.py`
- Test: `tests/test_format_m7_document.py`

**Interfaces:**
- Updates: `apply_typography(doc: Document)`
  - Thân bài: `line_spacing = 1.15`, `space_before = Pt(0)`, `space_after = Pt(1.5)`
  - Tiêu đề cấp 0: `line_spacing = 1.15`, `space_before = Pt(4)`, `space_after = Pt(4)`
  - Đề mục cấp 1, 2, 3: `line_spacing = 1.15`, `space_before = Pt(4)`, `space_after = Pt(2)`
  - Tiêu đề Bước (cấp 5): `line_spacing = 1.15`, `space_before = Pt(3)`, `space_after = Pt(1)`

- [ ] **Step 1: Viết test kiểm tra các tham số typography mới**
  - Cập nhật `test_typography` trong `tests/test_format_m7_document.py` kiểm tra `line_spacing == 1.15` và `space_after.pt == 1.5`.

- [ ] **Step 2: Chạy test để xác nhận Red (Failure)**
  - Lệnh: `python3 -m unittest tests/test_format_m7_document.py`
  - Kết quả mong đợi: FAIL do typography cũ dùng 1.2.

- [ ] **Step 3: Cập nhật hàm `apply_typography`**
  - Sửa `line_spacing` và `space_after` trong `scripts/format_m7_document.py`.

- [ ] **Step 4: Chạy test để xác nhận Green (Pass)**
  - Lệnh: `python3 -m unittest tests/test_format_m7_document.py`
  - Kết quả mong đợi: PASS.

- [ ] **Step 5: Git commit lẻ**
  - Lệnh: `git commit -m "perf(format): fine-tune typography spacing to achieve 20-page target"`

---

### Task 3: Tái tạo tài liệu M7 Word, Kiểm tra trang in 20 trang, Cập nhật nhật ký & Bàn giao

**Files:**
- Modify: `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx`
- Modify: `docs/superpowers/plans/WORK_LOG.md`
- Modify: `walkthrough.md`

- [ ] **Step 1: Chạy script chuẩn hóa toàn trình**
  - Lệnh: `python3 scripts/format_m7_document.py`
  - Kết quả mong đợi: Hoàn tất cập nhật `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx`.

- [ ] **Step 2: Kiểm tra số trang qua LibreOffice và pdfinfo**
  - Lệnh: `soffice --headless --convert-to pdf docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx --outdir /tmp && pdfinfo /tmp/M7_Thuyet_minh_Cong_trinh_ChuanHoa.pdf | grep "Pages:"`
  - Kết quả mong đợi: `Pages: 20`.

- [ ] **Step 3: Kiểm tra cấu trúc trang cuối (Trang 20)**
  - Kiểm tra text trang 20 chứa kết luận Mục 5 + Ngày tháng + Khối chữ ký.

- [ ] **Step 4: Chạy toàn bộ test suite dự án**
  - Lệnh: `python3 -m unittest discover -s tests`
  - Kết quả mong đợi: 62+ tests PASS.

- [ ] **Step 5: Cập nhật WORK_LOG.md, commit và push lên remote**
  - Lệnh: `git commit -m "chore(report): finalize 20-page document with side-by-side images"`
  - `git push origin main`
