#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/format_m7_document.py
Chuẩn hóa tài liệu thuyết minh M7 theo Nghị định 30/2020/NĐ-CP
"""

import os
import re
from docx import Document
from docx.shared import Mm, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

FONT_NAME = "Times New Roman"

def set_run_font(run, font_name=FONT_NAME, size_pt=13, bold=False, italic=False):
    """Thiết lập phông chữ Times New Roman và kiểu dáng cho một run."""
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
    """Căn lề A4 theo Nghị định 30/2020/NĐ-CP: Top 20mm, Bottom 20mm, Left 30mm, Right 15mm."""
    for section in doc.sections:
        section.top_margin = Mm(20)
        section.bottom_margin = Mm(20)
        section.left_margin = Mm(30)
        section.right_margin = Mm(15)
        section.page_width = Mm(210)
        section.page_height = Mm(297)

def is_title_or_heading(text: str) -> tuple[bool, int, str]:
    """
    Xác định loại tiêu đề:
    returns (is_heading, level, alignment)
    """
    t = text.strip()
    if not t:
        return False, 0, "NONE"
    
    # Tiêu đề chính
    if t.upper() == "THUYẾT MINH CÔNG TRÌNH":
        return True, 0, "CENTER"
    if t.startswith("Ứng dụng bằng chứng số trong kiểm soát và truy xuất"):
        return True, 0, "CENTER"
    
    # Mục cấp 1: "1. ", "2. ", "3. ", "4. ", "5. "
    if re.match(r'^[1-9]\.\s+', t):
        return True, 1, "LEFT"
    
    # Mục cấp 2: "1.1", "2.1", "2.3.1", ...
    if re.match(r'^[1-9]\.[0-9]+(\.[0-9]+)*\b', t):
        return True, 2, "LEFT"
        
    # Mục cấp 3: "a) ", "b) ", "c) ", "d) ", "đ) ", "e) ", "g) "
    if re.match(r'^[a-zđ]\)\s+', t):
        return True, 3, "LEFT"
        
    # Chú thích ảnh
    if re.match(r'^(Ảnh|ảnh|Hình|hình)\s+\d+', t):
        return True, 4, "CENTER"

    # Bước quy trình: "Bước 1. ", "Bước 2. ", ...
    if re.match(r'^Bước\s+\d+\.', t, re.IGNORECASE):
        return True, 5, "LEFT"

    return False, 0, "JUSTIFY"

def split_soft_break_paragraphs(doc: Document) -> None:
    """
    Tách các đoạn văn bản có chứa ký tự xuống dòng mềm (\\n hoặc <w:br/>) thành các đoạn văn riêng biệt.
    Điều này triệt tiêu hoàn toàn lỗi stretched justification (kéo dãn khoảng cách chữ) khi căn lề Justify.
    """
    from docx.text.paragraph import Paragraph
    for p in list(doc.paragraphs):
        if "\n" in p.text:
            lines = [line.strip() for line in p.text.split("\n") if line.strip()]
            if len(lines) <= 1:
                if lines:
                    p.text = lines[0]
                continue
            
            p.text = lines[0]
            curr_p = p
            for line in lines[1:]:
                p_new = OxmlElement("w:p")
                curr_p._p.addnext(p_new)
                new_para = Paragraph(p_new, curr_p._parent)
                new_para.text = line
                curr_p = new_para

def remove_redundant_empty_paragraphs(doc: Document) -> None:
    """Loại bỏ các đoạn văn bản trống thừa gây giãn cách và tràn trang không cần thiết."""
    for p in list(doc.paragraphs):
        # Không xóa nếu đoạn có chứa hình ảnh
        has_pic = any("pic:pic" in r._r.xml for r in p.runs)
        if not has_pic and not p.text.strip():
            p._p.getparent().remove(p._p)

def apply_typography(doc: Document, line_spacing: float = 1.2, body_space_after: float = 2.0, heading_space_before: float = 3.0) -> None:
    """Áp dụng quy chuẩn chữ và đoạn văn bản, kiểm soát ngắt trang mồ côi (keep_with_next)."""
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
            
        is_hd, level, align = is_title_or_heading(t)
        pf = p.paragraph_format
        
        if is_hd:
            pf.keep_with_next = True  # Luôn giữ tiêu đề đi liền với nội dung tiếp theo
            if level == 0:  # Tiêu đề lớn
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(4)
                pf.space_after = Pt(4)
                pf.line_spacing = line_spacing
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=14, bold=True)
            elif level in (1, 2, 3):  # Đề mục
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(heading_space_before)
                pf.space_after = Pt(2)
                pf.line_spacing = line_spacing
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=13, bold=True)
            elif level == 4:  # Chú thích ảnh
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(1)
                pf.space_after = Pt(3)
                pf.line_spacing = 1.1
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=10, italic=True)
            elif level == 5:  # Bước quy trình
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pf.first_line_indent = Cm(1.27)
                pf.space_before = Pt(3)
                pf.space_after = Pt(1)
                pf.line_spacing = line_spacing
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=13, bold=True)
        else:
            # Thân bài
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf.first_line_indent = Cm(1.27)
            pf.space_before = Pt(0)
            pf.space_after = Pt(body_space_after)
            pf.line_spacing = line_spacing
            for r in p.runs:
                set_run_font(r, FONT_NAME, size_pt=13)

def clean_table_data(doc: Document) -> None:
    """Làm sạch dữ liệu bảng biểu, sửa các lỗi gõ sai số liệu như dấu hai chấm '.'."""
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        if ".." in r.text:
                            r.text = re.sub(r'\.{2,}', '.', r.text)
                if ".." in cell.text:
                    # Trường hợp cell text trực tiếp
                    cell.text = re.sub(r'\.{2,}', '.', cell.text)

def set_cell_border(cell, color="000000", sz="4", val="single"):
    """Đặt viền đơn cho ô bảng."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn('w:tcBorders'))
    if tcBorders is not None:
        tcPr.remove(tcBorders)
    borders_xml = (
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(parse_xml(borders_xml))

def set_cell_shading(cell, color_hex="F2F2F2"):
    """Đặt màu nền nhẹ cho ô (thường dùng cho header bảng)."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is not None:
        tcPr.remove(shd)
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'))

def set_table_col_widths(table, widths_cm):
    """Cập nhật độ rộng chuẩn xác cho bảng bằng tblGrid và tcW của từng ô."""
    table.autofit = False
    tblPr = table._tbl.tblPr
    tblGrid = table._tbl.find(qn('w:tblGrid'))
    if tblGrid is not None:
        table._tbl.remove(tblGrid)
        
    new_tblGrid = OxmlElement('w:tblGrid')
    for w_cm in widths_cm:
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(int(w_cm * 567)))
        new_tblGrid.append(gridCol)
    tblPr.addnext(new_tblGrid)
    
    for row in table.rows:
        for col_idx, cell in enumerate(row.cells):
            if col_idx < len(widths_cm):
                w_dxa = int(widths_cm[col_idx] * 567)
                cell.width = Cm(widths_cm[col_idx])
                tcPr = cell._tc.get_or_add_tcPr()
                tcW = tcPr.find(qn('w:tcW'))
                if tcW is None:
                    tcW = OxmlElement('w:tcW')
                    tcPr.append(tcW)
                tcW.set(qn('w:w'), str(w_dxa))
                tcW.set(qn('w:type'), 'dxa')

def format_tables(doc: Document) -> None:
    """Chuẩn hóa toàn bộ bảng biểu trong tài liệu theo quy chuẩn hành chính."""
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    
    for table_idx, table in enumerate(doc.tables):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl_text = " ".join(cell.text for row in table.rows for cell in row.cells)
        is_signature_table = (len(table.rows) == 1 and len(table.columns) == 2 and "ĐẠI DIỆN" in tbl_text)
        
        if is_signature_table:
            # Bảng chữ ký: không để viền
            for row in table.rows:
                for cell in row.cells:
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                    for p in cell.paragraphs:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p.paragraph_format.first_line_indent = Cm(0)
                        p.paragraph_format.space_before = Pt(2)
                        p.paragraph_format.space_after = Pt(2)
                        for r in p.runs:
                            is_bold = "ĐẠI DIỆN" in r.text or "Nguyễn Việt Anh" in r.text
                            set_run_font(r, FONT_NAME, size_pt=13, bold=is_bold)
            continue
            
        # Bảng dữ liệu thông thường (Bảng Tác giả, Bảng Giá thành)
        if len(table.columns) == 5:
            # Bảng Giá thành: STT (1.5cm), Hạng mục (5.5cm), SL (2.0cm), Đơn giá (3.2cm), Thành tiền (3.5cm)
            set_table_col_widths(table, [1.5, 5.5, 2.0, 3.2, 3.5])
        elif len(table.columns) == 7:
            # Bảng Tác giả: TT (1.0cm), Tên công trình (3.5cm), Cấp bậc họ tên (4.5cm), Ngày sinh (2.0cm), SĐT (2.0cm), Email (2.0cm), Trình độ (1.2cm)
            set_table_col_widths(table, [1.0, 3.5, 4.5, 2.0, 2.0, 2.0, 1.2])
            
        for row_idx, row in enumerate(table.rows):
            is_header = (row_idx == 0)
            
            # Chống ngắt hàng qua trang và lặp header
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
            if is_header:
                trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
                
            for col_idx, cell in enumerate(row.cells):
                set_cell_border(cell)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    
                if is_header:
                    set_cell_shading(cell, "F2F2F2")
                    
                is_total_row = "Tổng cộng" in row.cells[1].text or "Tổng cộng" in row.cells[0].text if len(row.cells) > 1 else False
                
                for p in cell.paragraphs:
                    p.paragraph_format.first_line_indent = Cm(0)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.15
                    
                    # Căn lề nội dung ô
                    t_cell = cell.text.strip()
                    if is_header:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    elif is_total_row:
                        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if col_idx >= 3 else WD_ALIGN_PARAGRAPH.CENTER
                    elif col_idx in (0, 2) and re.match(r'^\d+$', t_cell): # STT hoặc số lượng
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    elif any(c.isdigit() for c in t_cell) and ("." in t_cell or len(t_cell) > 5) and col_idx >= 3:
                        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT # Số tiền
                    else:
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        
                    for r in p.runs:
                        bold = is_header or is_total_row
                        set_run_font(r, FONT_NAME, size_pt=11, bold=bold)

def find_image_file(images_dir: str, pattern: str) -> str:
    """Tìm file ảnh theo tên không phân biệt hoa thường và chuẩn Unicode NFC/NFD."""
    import unicodedata
    norm_pattern = unicodedata.normalize('NFC', pattern).lower()
    if not os.path.exists(images_dir):
        return ""
    for fname in os.listdir(images_dir):
        if unicodedata.normalize('NFC', fname).lower() == norm_pattern:
            return os.path.join(images_dir, fname)
    for fname in os.listdir(images_dir):
        if norm_pattern in unicodedata.normalize('NFC', fname).lower():
            return os.path.join(images_dir, fname)
    return ""

def insert_paragraph_after(paragraph, text="", size_pt=11, italic=True, bold=False):
    """Tạo một đoạn văn bản mới ngay sau đoạn văn bản hiện tại."""
    from docx.text.paragraph import Paragraph
    p_new = OxmlElement("w:p")
    paragraph._p.addnext(p_new)
    new_para = Paragraph(p_new, paragraph._parent)
    new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = new_para.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(2)
    pf.space_after = Pt(6)
    if text:
        r = new_para.add_run(text)
        set_run_font(r, FONT_NAME, size_pt=size_pt, italic=italic, bold=bold)
    return new_para

def put_image_in_paragraph(paragraph, img_path: str, width_cm: float = 10.0):
    """Đặt ảnh căn giữa vào đoạn văn bản và giữ liền với chú thích."""
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = paragraph.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(4)
    pf.space_after = Pt(2)
    pf.keep_with_next = True  # Giữ ảnh luôn đi cùng chú thích ở dưới
    r = paragraph.add_run()
    r.add_picture(img_path, width=Cm(width_cm))

def set_cell_no_border(cell):
    """Xóa toàn bộ viền ô để tạo bảng ẩn không viền (dùng cho ảnh xếp hàng ngang)."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn('w:tcBorders'))
    if tcBorders is not None:
        tcPr.remove(tcBorders)
    borders_xml = (
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(parse_xml(borders_xml))

def set_table_no_borders(table):
    """Đặt toàn bộ viền bảng về none để ẩn hoàn toàn đường viền."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    tblPr = table._tbl.tblPr
    tblBorders = tblPr.find(qn('w:tblBorders'))
    if tblBorders is not None:
        tblPr.remove(tblBorders)
    borders_xml = (
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="none"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(parse_xml(borders_xml))

def insert_side_by_side_image_table(doc: Document, paragraph, img_items, total_width_cm: float = 16.5):
    """
    Tạo một bảng 2 hàng, N cột ẩn viền để đặt các ảnh và chú thích cạnh nhau trên cùng 1 hàng:
    - Hàng 0: Các ảnh (căn giữa trong ô)
    - Hàng 1: Các chú thích tương ứng (căn giữa trong ô, 10pt, nghiêng)
    """
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    cols = len(img_items)
    col_w_cm = total_width_cm / cols
    table = doc.add_table(rows=2, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_no_borders(table)
    paragraph._p.addnext(table._tbl)

    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    for c_i, (img_path, cap_text, w_cm) in enumerate(img_items):
        c_img = table.cell(0, c_i)
        c_cap = table.cell(1, c_i)
        set_cell_no_border(c_img)
        set_cell_no_border(c_cap)
        c_img.width = Cm(col_w_cm)
        c_cap.width = Cm(col_w_cm)

        # Ô ảnh
        p0 = c_img.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p0.paragraph_format.first_line_indent = Cm(0)
        p0.paragraph_format.space_before = Pt(2)
        p0.paragraph_format.space_after = Pt(2)
        p0.paragraph_format.keep_with_next = True
        r0 = p0.add_run()
        r0.add_picture(img_path, width=Cm(w_cm))

        # Ô chú thích
        p1 = c_cap.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.first_line_indent = Cm(0)
        p1.paragraph_format.space_before = Pt(1)
        p1.paragraph_format.space_after = Pt(3)
        p1.paragraph_format.line_spacing = 1.1
        r1 = p1.add_run(cap_text)
        set_run_font(r1, FONT_NAME, size_pt=10, italic=True)

    paragraph.text = ""
    return table

def insert_images_and_captions(doc: Document, images_dir: str) -> None:
    """
    Quét và chèn 10 hình ảnh vào các vị trí đánh dấu trong tài liệu:
    - Ảnh 1: Mã định danh (đơn)
    - Ảnh 2: Tai nghe (đơn)
    - Ảnh 3: Bảng 2 ảnh side-by-side (Ảnh 3a Webcam + Ảnh 3b Vị trí lắp)
    - Ảnh 4: Hộp chụp ảnh (đơn)
    - Ảnh 5: Đế đặt bệnh phẩm (đơn)
    - Ảnh 6: Bàn đạp chân (đơn)
    - Ảnh 7: Bảng 3 ảnh side-by-side (Ảnh 7a Tiếp nhận + Ảnh 7b Giao diện + Ảnh 7c Bằng chứng số)
    """
    import unicodedata
    
    configs = [
        (
            re.compile(r'^(Ảnh|ảnh)\s+1\b', re.IGNORECASE),
            [
                ("Ảnh 1_crop.jpg", "Ảnh 1a: Tem mã định danh GPB-ID", 5.2),
                ("Ảnh 1.2_crop.jpg", "Ảnh 1b: Phiếu chỉ định có mã vạch", 5.2)
            ]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+2\b', re.IGNORECASE),
            [("Ảnh 2.jpg", "Ảnh 2: Tai nghe có dây tích hợp micro thu nhận giọng nói", 5.2)]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+3\b', re.IGNORECASE),
            [
                ("Ảnh 3.2.jpg", "Ảnh 3a: Webcam Logitech C920e Full HD", 5.2),
                ("Ảnh 3.jpg", "Ảnh 3b: Vị trí lắp đặt trong hộp chụp", 5.2)
            ]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+4\b', re.IGNORECASE),
            [("Ảnh 4.jpg", "Ảnh 4: Hộp chụp ảnh tích hợp hệ thống chiếu sáng", 6.0)]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+5\b', re.IGNORECASE),
            [("Ảnh 5.jpg", "Ảnh 5: Đế đặt bệnh phẩm có định vị trường quan sát", 6.0)]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+6\b', re.IGNORECASE),
            [("Ảnh 6.jpg", "Ảnh 6: Bàn đạp chân USB kích hoạt lệnh chụp ảnh rảnh tay", 5.8)]
        ),
        (
            re.compile(r'^(Ảnh|ảnh)\s+7\b', re.IGNORECASE),
            [
                ("Ảnh 7.1.jpg", "Ảnh 7a: Tiếp nhận và chụp lưu mẫu", 4.8),
                ("Ảnh 7.2.jpg", "Ảnh 7b: Giao diện tiếp nhận thông tin", 4.8),
                ("Ảnh 7.3.jpg", "Ảnh 7c: Hồ sơ bằng chứng số", 4.8)
            ]
        ),
    ]

    for p in list(doc.paragraphs):
        t = unicodedata.normalize('NFC', p.text.strip())
        if not t:
            continue
            
        for marker_re, img_items in configs:
            if marker_re.search(t):
                # Kiểm tra xem có nhiều ảnh cần xếp hàng ngang không
                resolved_items = []
                for img_pattern, caption_text, width_cm in img_items:
                    img_path = find_image_file(images_dir, img_pattern)
                    if img_path and os.path.exists(img_path):
                        resolved_items.append((img_path, caption_text, width_cm))

                if not resolved_items:
                    break

                if len(resolved_items) > 1:
                    # Gom các ảnh thành bảng ẩn viền nằm ngang
                    insert_side_by_side_image_table(doc, p, resolved_items)
                else:
                    # Ảnh đơn
                    img_path, caption_text, width_cm = resolved_items[0]
                    put_image_in_paragraph(p, img_path, width_cm)
                    insert_paragraph_after(p, caption_text, size_pt=11, italic=True)
                break

def clean_empty_rows_in_author_table(doc: Document) -> None:
    """Xóa các hàng thừa/trống trong Bảng tác giả (Table 0)."""
    if not doc.tables:
        return
    t0 = doc.tables[0]
    # Duyệt từ dưới lên để xóa an toàn
    for row in list(t0.rows)[1:]:
        # Nếu cột họ tên (cột 2) và ngày sinh (cột 3) đều trống thì xóa hàng
        if len(row.cells) > 3:
            name_text = row.cells[2].text.strip()
            dob_text = row.cells[3].text.strip()
            if not name_text and not dob_text:
                t0._tbl.remove(row._tr)

def format_date_paragraph(doc: Document) -> None:
    """Căn phải và in nghiêng dòng ngày tháng địa điểm cuối tài liệu (chuẩn mốc 2026)."""
    for p in doc.paragraphs:
        t = p.text.strip()
        if re.search(r'^(Hà Nội|Hà nội),\s*ngày\s+\d+\s+tháng\s+\d+\s+năm\s+\d+', t):
            p.text = "Hà Nội, ngày 25 tháng 8 năm 2026"
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            for r in p.runs:
                set_run_font(r, FONT_NAME, size_pt=13, italic=True)

def standardize_author_and_date_info(doc: Document) -> None:
    """
    Chuẩn hóa thông tin nhân thân tác giả và chính tả đơn vị:
    - Sửa thông tin đồng tác giả Nguyễn Phúc Đẳng (sinh 2002, SĐT 0866085675, email nguyenphucdang15032002@gmail.com).
    - Chuẩn hóa viết hoa 'Tổng cục Hậu cần - Kỹ thuật'.
    """
    for p in doc.paragraphs:
        if "tổng cục Hậu cần - Kỹ thuật" in p.text:
            p.text = p.text.replace("tổng cục Hậu cần - Kỹ thuật", "Tổng cục Hậu cần - Kỹ thuật")
            
    if doc.tables:
        t0 = doc.tables[0]
        for row in list(t0.rows)[1:]:
            cells = row.cells
            if len(cells) >= 7:
                author_info = cells[2].text
                if "Nguyễn Phúc Đẳng" in author_info:
                    cells[3].text = "15/03/2002"
                    cells[4].text = "0866085675"
                    cells[5].text = "nguyenphucdang15032002@gmail.com"
                    cells[6].text = "ĐH"
                elif "Nguyễn Việt Anh" in author_info:
                    cells[5].text = "nguyenvietanh0609@gmail.com"

def build_standardized_m7(input_path: str, output_path: str, images_dir: str) -> str:
    """Thực thi toàn bộ quy trình chuẩn hóa tài liệu M7 và lưu file."""
    import shutil
    import subprocess
    
    # Ưu tiên đọc từ file sao lưu gốc nếu có để đảm bảo lặp lại sạch sẽ các marker
    backup_file = os.path.join(images_dir, "Bản sao M7 Thuyet minh Cong trinh_ORIGINAL_BACKUP.docx")
    src_file = backup_file if os.path.exists(backup_file) else input_path

    print(f"[*] Đang đọc file nguồn: {src_file}")
    doc = Document(src_file)

    print("[*] 1. Căn lề khổ giấy A4 theo Nghị định 30/2020/NĐ-CP...")
    apply_page_setup(doc)

    print("[*] 2. Dọn dẹp hàng trống, chuẩn hóa thông tin tác giả và bảng biểu...")
    clean_empty_rows_in_author_table(doc)
    standardize_author_and_date_info(doc)
    clean_table_data(doc)
    format_tables(doc)

    print("[*] 3. Chèn hình ảnh và chú thích vào đúng vị trí...")
    insert_images_and_captions(doc, images_dir)

    print("[*] 4. Tách các đoạn chứa soft break và loại bỏ đoạn trống thừa...")
    split_soft_break_paragraphs(doc)
    remove_redundant_empty_paragraphs(doc)
    apply_typography(doc, line_spacing=1.2, body_space_after=2.0, heading_space_before=3.0)
    format_date_paragraph(doc)

    print(f"[*] Đang lưu file chuẩn hóa: {output_path}")
    doc.save(output_path)
    
    # Đồng bộ sang các file bản sao để người dùng mở file nào cũng thấy kết quả chuẩn xác
    target_copies = [
        os.path.join(images_dir, "Bản sao M7 Thuyet minh Cong trinh.docx"),
        os.path.join(images_dir, "Bản sao M7 Thuyet minh Cong trinh (2).docx"),
    ]
    for target_copy in target_copies:
        if os.path.exists(os.path.dirname(target_copy)) and os.path.abspath(output_path) != os.path.abspath(target_copy):
            shutil.copyfile(output_path, target_copy)
            print(f"[+] Đã đồng bộ sang: {target_copy}")

    # Xuất PDF đối soát
    pdf_out = os.path.splitext(output_path)[0] + ".pdf"
    out_dir = os.path.dirname(output_path)
    try:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", output_path, "--outdir", out_dir], stdout=subprocess.DEVNULL, check=True)
        print(f"[+] Đã xuất file PDF đối soát: {pdf_out}")
    except Exception as e:
        print(f"[!] Cảnh báo khi xuất PDF: {e}")

    print("[+] Hoàn tất tạo file Word chuẩn hóa!")
    return output_path

if __name__ == '__main__':
    base_dir = "/Volumes/DATA/NguyenVietAnh"
    in_file = os.path.join(base_dir, "docs/report/Bản sao M7 Thuyet minh Cong trinh.docx")
    out_file = os.path.join(base_dir, "docs/report/M7_Thuyet_minh_Cong_trinh_ChuanHoa.docx")
    img_dir = os.path.join(base_dir, "docs/report")

    build_standardized_m7(in_file, out_file, img_dir)



