"""Regression tests for Vietnamese birth-year voice parsing."""

import unittest

from src.patient_voice_parser import (
    parse_patient_speech,
    fill_pending_field,
    detect_pending_field,
    incomplete_birth_year_prefix,
    complete_truncated_birth_year,
    _normalize_year,
    _viet_words_to_digits,
)


class TestBirthYearVoiceParse(unittest.TestCase):
    def test_full_digit_words_1999(self):
        out = parse_patient_speech("năm sinh một chín chín chín")
        self.assertIsNotNone(out)
        self.assertEqual(out["birth_year"], "1999")

    def test_formal_words_1999(self):
        out = parse_patient_speech("năm sinh một nghìn chín trăm chín mươi chín")
        self.assertIsNotNone(out)
        self.assertEqual(out["birth_year"], "1999")

    def test_digits_1999(self):
        out = parse_patient_speech("năm sinh 1999")
        self.assertIsNotNone(out)
        self.assertEqual(out["birth_year"], "1999")

    def test_truncated_199_does_not_become_1990(self):
        """ASR often drops the last 'chín' → 'một chín chín'. Must NOT invent 1990."""
        conv = _viet_words_to_digits("năm sinh một chín chín")
        self.assertEqual(conv, "năm sinh 199")
        self.assertIsNone(_normalize_year("199"))
        out = parse_patient_speech("năm sinh một chín chín")
        self.assertTrue(
            out is None or out.get("birth_year") != "1990",
            f"must not invent 1990, got {out}",
        )

    def test_truncated_199_detected_as_incomplete_prefix(self):
        prefix = incomplete_birth_year_prefix("năm sinh một chín chín")
        self.assertEqual(prefix, "199")

    def test_complete_truncated_with_final_digit(self):
        self.assertEqual(complete_truncated_birth_year("199", "chín"), "1999")
        self.assertEqual(complete_truncated_birth_year("199", "9"), "1999")
        self.assertEqual(complete_truncated_birth_year("199", "không"), "1990")
        self.assertIsNone(complete_truncated_birth_year("199", "lương thế vinh"))

    def test_hai_nghin_2000(self):
        out = parse_patient_speech("năm sinh hai nghìn")
        self.assertEqual(out["birth_year"], "2000")

    def test_pending_year_then_digits(self):
        self.assertEqual(detect_pending_field("năm sinh"), "birth_year")
        filled = fill_pending_field("birth_year", "một chín chín chín")
        self.assertEqual(filled["birth_year"], "1999")

    def test_pending_year_truncated_does_not_pad(self):
        filled = fill_pending_field("birth_year", "một chín chín")
        self.assertTrue(
            filled is None or filled.get("birth_year") != "1990",
            f"pending fill must not invent 1990, got {filled}",
        )


if __name__ == "__main__":
    unittest.main()
