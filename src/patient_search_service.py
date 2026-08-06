"""Patient Search Service - Fuzzy search across patient records in SQLite."""

import sqlite3
import unicodedata
from typing import List, Dict


def remove_accents(input_str: str) -> str:
    """Remove Vietnamese diacritics for unaccented fuzzy matching."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


class PatientSearchService:
    """Search patients by optional filters: ID, name (unaccented), birth_year, gender."""

    def __init__(self, db_path: str = "patients.db"):
        self.db_path = str(db_path)

    def search(self, patient_id: str = "", full_name: str = "", birth_year: str = "", gender: str = "") -> List[Dict[str, str]]:
        """Return list of patient dicts matching all provided (non-empty) filters."""
        query = "SELECT patient_id, full_name, birth_year, gender FROM patients WHERE 1=1"
        params: list = []

        if patient_id:
            query += " AND patient_id LIKE ?"
            params.append(f"%{patient_id.strip()}%")
        if birth_year:
            query += " AND birth_year LIKE ?"
            params.append(f"%{birth_year.strip()}%")
        if gender:
            query += " AND LOWER(gender) = LOWER(?)"
            params.append(gender.strip())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        results: List[Dict[str, str]] = []
        name_needle = remove_accents(full_name.strip()) if full_name else ""

        for p_id, p_name, p_year, p_gender in rows:
            if name_needle and name_needle not in remove_accents(p_name or ""):
                continue
            results.append({
                "patient_id": p_id,
                "full_name": p_name,
                "birth_year": p_year,
                "gender": p_gender,
            })

        return results
