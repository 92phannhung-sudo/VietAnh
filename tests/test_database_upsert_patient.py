"""Tests for database.upsert_patient (photo FK prerequisite)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestUpsertPatient(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        self.photos_dir = Path(self._tmpdir.name) / "photos"
        self.photos_dir.mkdir()

        import config
        import database

        self.config = config
        self.database = database
        self._prev_db = config.DB_PATH
        config.DB_PATH = self.db_path
        self._photos_patch = patch.object(config, "get_photos_dir", return_value=self.photos_dir)
        self._photos_patch.start()
        database.initialize_db()

    def tearDown(self):
        self._photos_patch.stop()
        self.config.DB_PATH = self._prev_db
        self._tmpdir.cleanup()

    def test_upsert_creates_then_updates(self):
        ok = self.database.upsert_patient("XN999", name="A", birth_year=1990, gender="Nam")
        self.assertTrue(ok)
        row = self.database.get_patient("XN999")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "A")

        ok = self.database.upsert_patient("XN999", name="B", birth_year=1991, gender="Nữ")
        self.assertTrue(ok)
        row = self.database.get_patient("XN999")
        self.assertEqual(row["name"], "B")
        self.assertEqual(row["birth_year"], 1991)

    def test_add_photo_succeeds_after_upsert(self):
        self.database.upsert_patient("XN888", name="C", birth_year=2000, gender="Nam")
        rel = "photos/XN888/x.jpg"
        (self.photos_dir / "XN888").mkdir(parents=True, exist_ok=True)
        (self.photos_dir / "XN888" / "x.jpg").write_bytes(b"fake")
        self.assertTrue(self.database.add_photo("XN888", rel))
        photos = self.database.get_patient_photos("XN888")
        self.assertEqual(len(photos), 1)

    def test_add_photo_fails_without_patient(self):
        self.assertFalse(self.database.add_photo("MISSING", "photos/MISSING/x.jpg"))


if __name__ == "__main__":
    unittest.main()
