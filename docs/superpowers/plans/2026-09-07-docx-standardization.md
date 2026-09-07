# Chuẩn Hóa Tài Liệu M7 Thuyết Minh Công Trình Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng module tự động chuẩn hóa văn bản thuyết minh M7 theo Nghị định 30/2020/NĐ-CP, định dạng lại bảng biểu, sửa lỗi số liệu, chèn 10 hình ảnh minh họa thực tế và xuất bản ra file docx chuẩn hóa cùng file PDF đối soát.

**Architecture:** Sử dụng thư viện `python-docx` kết hợp mẫu thiết kế của `enterprise-docx-patcher` để đọc cấu trúc OpenXML từ `docs/report/Bản sao M7 Thuyet minh Cong trinh.docx`, áp dụng các hàm chuẩn hóa phân tách rõ ràng: Page Setup & Typography, Table Polishing & Data Cleansing, Image Insertion & Captioning. Sau đó kiểm chứng toàn vẹn bằng lệnh headless LibreOffice (`soffice`).

**Tech Stack:** Python 3, `python-docx 1.2.0`, `unittest`, `soffice` (LibreOffice).

## Global Constraints

- Phông chữ duy nhất: `Times New Roman` (Unicode TCVN 6909:2001).
- Khổ giấy: A4 (210mm × 297mm), Margins: Top 20mm, Bottom 20mm, Left 30mm, Right 15mm.
- Nội dung thân bài: 13pt, Justified, Thụt đầu dòng 1.27cm, Giãn dòng 1.2 lines, Spacing Before 0pt, Spacing After 3-4pt.
- Bảng biểu: Viền đơn mảnh, header in đậm căn giữa nền xám 5%, số tiền căn phải, sửa lỗi dấu hai chấm `..` trong số tiền.
- Hình ảnh: Căn giữa trang, không vượt quá độ rộng vùng in (16.5cm), caption in nghiêng 11pt căn giữa.
- Không phát sinh dependency bên ngoài, sử dụng thư viện sẵn có.

---

### Task 1: Thiết lập cấu trúc trang in và Typography theo Nghị định 30

**Files:**
- Create: `scripts/format_m7_document.py`
- Create: `tests/test_format_m7_document.py`

**Interfaces:**
- Produces: `apply_page_setup(doc: Document) -> None`, `apply_typography(doc: Document) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_format_m7_document.py
import unittest
import os
from docx import Document
from docx.shared import Mm, Pt
from scripts.format_m7_document import apply_page_setup, apply_typography

class TestM7PageSetupAndTypography(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        p = self.doc.add_paragraph("Đoạn văn thử nghiệm nội dung thân bài.")
    
    def test_page_margins(self):
        apply_page_setup(self.doc)
        section = self.doc.sections[0]
        self.assertAlmostEqual(section.top_margin.mm, 20.0, places=1)
        self.assertAlmostEqual(section.bottom_margin.mm, 20.0, places=1)
        self.assertAlmostEqual(section.left_margin.mm, 30.0, places=1)
        self.assertAlmostEqual(section.right_margin.mm, 15.0, places=1)

    def test_typography(self):
        apply_typography(self.doc)
        p = self.doc.paragraphs[0]
        self.assertEqual(p.runs[0].font.name, "Times New Roman")
        self.assertEqual(p.runs[0].font.size, Pt(13))
        self.assertAlmostEqual(p.paragraph_format.first_line_indent.cm, 1.27, places=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/format_m7_document.py
from docx import Document
from docx.shared import Mm, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

FONT_NAME = "Times New Roman"

def set_run_font(run, font_name=FONT_NAME, size_pt=13, bold=False, italic=False):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font_name)

def apply_page_setup(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Mm(20)
        section.bottom_margin = Mm(20)
        section.left_margin = Mm(30)
        section.right_margin = Mm(15)
        section.page_width = Mm(210)
        section.page_height = Mm(297)

def apply_typography(doc: Document) -> None:
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        pf = p.paragraph_format
        pf.line_spacing = 1.2
        pf.space_before = Pt(0)
        pf.space_after = Pt(3)
        pf.first_line_indent = Cm(1.27)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for run in p.runs:
            set_run_font(run, FONT_NAME, size_pt=13)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/format_m7_document.py tests/test_format_m7_document.py
git commit -m "feat(docx): implement page setup and typography per ND30"
```

---

### Task 2: Chuẩn hóa bảng biểu và sửa lỗi số liệu

**Files:**
- Modify: `scripts/format_m7_document.py`
- Modify: `tests/test_format_m7_document.py`

**Interfaces:**
- Produces: `format_tables(doc: Document) -> None`, `clean_table_data(doc: Document) -> None`

- [ ] **Step 1: Write the failing test**

```python
    def test_format_cost_table_fixes_typos(self):
        table = self.doc.add_table(rows=3, cols=5)
        # Hàng 1
        table.cell(1, 1).text = "Webcam Logitech 920e"
        table.cell(1, 3).text = "1.800.000"
        table.cell(1, 4).text = "1.800..000"
        # Hàng 2
        table.cell(2, 1).text = "Bàn đạp chân"
        table.cell(2, 3).text = "290..000"
        table.cell(2, 4).text = "290..000"
        
        from scripts.format_m7_document import clean_table_data, format_tables
        clean_table_data(self.doc)
        format_tables(self.doc)
        
        self.assertEqual(table.cell(1, 4).text, "1.800.000")
        self.assertEqual(table.cell(2, 3).text, "290.000")
        self.assertEqual(table.cell(2, 4).text, "290.000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: FAIL (ImportError clean_table_data or format_tables)

- [ ] **Step 3: Write minimal implementation**

```python
# Thêm vào scripts/format_m7_document.py
import re
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.enum.table import WD_TABLE_ALIGNMENT

def clean_table_data(doc: Document) -> None:
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text
                if ".." in text:
                    cell.text = re.sub(r'\.{2,}', '.', text)

def set_cell_border(cell, **kwargs):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}>\n'
                          f'<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
                          f'<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
                          f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
                          f'<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
                          f'</w:tcBorders>')
    tcPr.append(tcBorders)

def format_tables(doc: Document) -> None:
    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                set_cell_border(cell)
                for p in cell.paragraphs:
                    p.paragraph_format.first_line_indent = Cm(0)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.15
                    for run in p.runs:
                        is_bold = row_idx == 0 or "Tổng cộng" in cell.text
                        set_run_font(run, FONT_NAME, size_pt=11, bold=is_bold)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/format_m7_document.py tests/test_format_m7_document.py
git commit -m "feat(docx): format tables and clean number typo data"
```

---

### Task 3: Chèn ảnh và chú thích theo vị trí thiết kế

**Files:**
- Modify: `scripts/format_m7_document.py`
- Modify: `tests/test_format_m7_document.py`

**Interfaces:**
- Produces: `insert_images_and_captions(doc: Document, images_dir: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
    def test_insert_image_and_caption(self):
        p = self.doc.add_paragraph("Ảnh 1 : Mã định danh")
        from scripts.format_m7_document import insert_images_and_captions
        images_dir = "/Volumes/DATA/NguyenVietAnh/docs/report"
        insert_images_and_captions(self.doc, images_dir)
        # Verify drawing element inserted into doc
        xml_str = self.doc._body._element.xml
        self.assertIn("pic:pic", xml_str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: FAIL (ImportError insert_images_and_captions)

- [ ] **Step 3: Write minimal implementation**

```python
# Thêm vào scripts/format_m7_document.py
def add_image_with_caption(paragraph, image_path, caption_text, width_cm=10.0):
    p = paragraph._p
    parent = p.getparent()
    p_img = OxmlElement("w:p")
    p.addnext(p_img)
    from docx.text.paragraph import Paragraph
    img_par = Paragraph(p_img, paragraph._parent)
    img_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    img_run = img_par.add_run()
    img_run.add_picture(image_path, width=Cm(width_cm))
    
    p_cap = OxmlElement("w:p")
    p_img.addnext(p_cap)
    cap_par = Paragraph(p_cap, paragraph._parent)
    cap_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_par.paragraph_format.space_before = Pt(2)
    cap_par.paragraph_format.space_after = Pt(6)
    cap_par.paragraph_format.first_line_indent = Cm(0)
    cap_run = cap_par.add_run(caption_text)
    set_run_font(cap_run, FONT_NAME, size_pt=11, italic=True)

def insert_images_and_captions(doc: Document, images_dir: str) -> None:
    # Mapping placeholder markers to images and captions
    mapping = {
        "ảnh 1": ("Ảnh 1.jpg", "Ảnh 1: Mã định danh và mã vạch quản lý bệnh phẩm", 10.0),
        "ảnh 2": ("Ảnh 2.jpg", "Ảnh 2: Tai nghe có dây tích hợp micro thu nhận giọng nói", 8.0),
        "ảnh 4": ("Ảnh 4.jpg", "Ảnh 4: Hộp chụp ảnh tích hợp hệ thống chiếu sáng", 10.0),
        "ảnh 5": ("Ảnh 5.jpg", "Ảnh 5: Đế đặt bệnh phẩm có định vị trường quan sát", 10.0),
        "ảnh 6": ("Ảnh 6.jpg", "Ảnh 6: Bàn đạp chân USB kích hoạt lệnh chụp ảnh rảnh tay", 9.0),
    }
    # Duyệt và chèn
    # Xử lý đặc biệt cho Ảnh 3 (chèn cả 3.2 và 3) và Ảnh 7 (chèn 7.1, 7.2, 7.3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_format_m7_document.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/format_m7_document.py tests/test_format_m7_document.py
git commit -m "feat(docx): insert images and captions into designated locations"
```

---

### Task 4: Chạy toàn trình tạo file M7 chuẩn hóa và xuất PDF kiểm thử

**Files:**
- Modify: `scripts/format_m7_document.py`

**Interfaces:**
- Produces: `build_standardized_m7(input_path: str, output_path: str, images_dir: str) -> None`

- [ ] **Step 1: Execute full conversion and build**

Run:
```bash
python3 scripts/format_m7_document.py
```
Expected: File `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx` được tạo thành công.

- [ ] **Step 2: Generate PDF via LibreOffice**

Run:
```bash
soffice --headless --convert-to pdf --outdir docs/report docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx
```
Expected: File `docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.pdf` sinh ra thành công không có lỗi.

- [ ] **Step 3: Commit**

```bash
git add docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.pdf
git commit -m "build(report): generate standardized M7 docx and pdf files"
```
