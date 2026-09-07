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
