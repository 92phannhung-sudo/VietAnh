import os
import sqlite3
import tempfile
import unittest
from src.patient_search_service import PatientSearchService


class TestPatientSearch(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_file = os.path.join(self.tmp_dir.name, "test_patients.db")
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE patients (
                patient_id TEXT PRIMARY KEY,
                full_name TEXT,
                birth_year TEXT,
                gender TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO patients (patient_id, full_name, birth_year, gender, created_at)
            VALUES
                ('BN001', 'Nguyễn Văn A', '1987', 'Nam', '2024-01-01 10:00:00'),
                ('BN001X', 'Phạm Văn X', '1980', 'Nam', '2024-01-02 10:00:00'),
                ('BN123', 'Nguyễn Văn A', '1987', 'Nam', '2024-01-03 10:00:00'),
                ('BN456', 'Trần Thị B', '1992', 'Nữ', '2024-01-04 10:00:00')
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_search_with_optional_filters(self):
        service = PatientSearchService(db_path=self.db_file)

        res = service.search(patient_id="BN123")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient_id"], "BN123")

        res_name = service.search(full_name="van a")
        self.assertEqual(len(res_name), 2)
        ids = {r["patient_id"] for r in res_name}
        self.assertEqual(ids, {"BN001", "BN123"})

        res_bg = service.search(birth_year="1992", gender="Nữ")
        self.assertEqual(len(res_bg), 1)
        self.assertEqual(res_bg[0]["patient_id"], "BN456")

    def test_exact_patient_id_not_like(self):
        service = PatientSearchService(db_path=self.db_file)
        res = service.search(patient_id="BN001")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient_id"], "BN001")
        self.assertEqual(service.search_exact_id("BN001")[0]["patient_id"], "BN001")
        self.assertEqual(service.search(patient_id="BN001X")[0]["patient_id"], "BN001X")

    def test_recent_orders_newest_first(self):
        service = PatientSearchService(db_path=self.db_file)
        recent = service.recent(limit=3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(
            [r["patient_id"] for r in recent],
            ["BN456", "BN123", "BN001X"],
        )

    def test_production_schema_id_name(self):
        """Production DB uses id/name columns — service must still return patient_id/full_name keys."""
        prod_db = os.path.join(self.tmp_dir.name, "prod.db")
        conn = sqlite3.connect(prod_db)
        conn.execute("""
            CREATE TABLE patients (
                id TEXT PRIMARY KEY,
                name TEXT,
                birth_year INTEGER,
                gender TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO patients VALUES ('XN001', 'Lê C', 1990, 'Nữ', '2024-06-01 00:00:00')"
        )
        conn.commit()
        conn.close()
        service = PatientSearchService(db_path=prod_db)
        res = service.search(patient_id="XN001")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient_id"], "XN001")
        self.assertEqual(res[0]["full_name"], "Lê C")
        self.assertEqual(service.recent(1)[0]["patient_id"], "XN001")


if __name__ == "__main__":
    unittest.main()
