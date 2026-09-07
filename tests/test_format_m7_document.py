import unittest
from docx import Document
from docx.shared import Mm, Pt, Cm
from scripts.format_m7_document import apply_page_setup, apply_typography

class TestM7PageSetupAndTypography(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.p = self.doc.add_paragraph("Đoạn văn thử nghiệm nội dung thân bài thuyết minh sáng kiến.")
    
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

if __name__ == '__main__':
    unittest.main()
