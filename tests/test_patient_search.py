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
            INSERT INTO patients (patient_id, full_name, birth_year, gender)
            VALUES ('BN123', 'Nguyễn Văn A', '1987', 'Nam'),
                   ('BN456', 'Trần Thị B', '1992', 'Nữ')
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
        
        # Filter by Patient ID
        res = service.search(patient_id="123")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient_id"], "BN123")

        # Filter by Name (unaccented / fuzzy matching)
        res_name = service.search(full_name="van a")
        self.assertEqual(len(res_name), 1)
        self.assertEqual(res_name[0]["full_name"], "Nguyễn Văn A")

        # Filter by Birth Year & Gender
        res_bg = service.search(birth_year="1992", gender="Nữ")
        self.assertEqual(len(res_bg), 1)
        self.assertEqual(res_bg[0]["patient_id"], "BN456")

if __name__ == "__main__":
    unittest.main()
