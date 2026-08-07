import json
import os
import tempfile
import unittest
from pathlib import Path

from src.patient_session_controller import _DEFAULT_LEXICON
from src.voice_lexicon_store import load_lexicon, save_lexicon


class TestVoiceLexiconStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "voice_lexicon.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_missing_returns_defaults(self):
        data = load_lexicon(self.path)
        self.assertIn("chụp", data)
        self.assertEqual(data["chụp"], _DEFAULT_LEXICON["chụp"])

    def test_round_trip(self):
        phrases = {"chụp ảnh": "capture", "mở phiên": "start_session"}
        save_lexicon(self.path, phrases)
        loaded = load_lexicon(self.path)
        self.assertEqual(loaded["chụp ảnh"], "capture")
        self.assertEqual(loaded["mở phiên"], "start_session")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["chụp ảnh"], "capture")


if __name__ == "__main__":
    unittest.main()
