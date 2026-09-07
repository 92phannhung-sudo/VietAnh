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

    return False, 0, "JUSTIFY"

def apply_typography(doc: Document) -> None:
    """Áp dụng quy chuẩn chữ và đoạn văn bản."""
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
            
        is_hd, level, align = is_title_or_heading(t)
        pf = p.paragraph_format
        
        if is_hd:
            if level == 0:  # Tiêu đề lớn
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(6)
                pf.space_after = Pt(6)
                pf.line_spacing = 1.2
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=14, bold=True)
            elif level in (1, 2, 3):  # Đề mục
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(6)
                pf.space_after = Pt(3)
                pf.line_spacing = 1.2
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=13, bold=True)
            elif level == 4:  # Chú thích ảnh
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pf.first_line_indent = Cm(0)
                pf.space_before = Pt(2)
                pf.space_after = Pt(6)
                pf.line_spacing = 1.15
                for r in p.runs:
                    set_run_font(r, FONT_NAME, size_pt=11, italic=True)
        else:
            # Thân bài
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf.first_line_indent = Cm(1.27)
            pf.space_before = Pt(0)
            pf.space_after = Pt(3)
            pf.line_spacing = 1.2
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

def format_tables(doc: Document) -> None:
    """Chuẩn hóa toàn bộ bảng biểu trong tài liệu theo quy chuẩn hành chính."""
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    
    for table_idx, table in enumerate(doc.tables):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Kiểm tra xem có phải bảng chữ ký (thường là bảng cuối, 1 hàng, 2 cột)
        is_signature_table = (len(table.rows) == 1 and len(table.columns) == 2 and "ĐẠI DIỆN" in table.text)
        
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
        for row_idx, row in enumerate(table.rows):
            is_header = (row_idx == 0)
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

