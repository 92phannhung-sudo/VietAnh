import sqlite3
import unicodedata

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

class PatientSearchService:
    def __init__(self, db_path="patients.db"):
        self.db_path = db_path

    def search(self, patient_id="", full_name="", birth_year="", gender=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT patient_id, full_name, birth_year, gender FROM patients WHERE 1=1"
        params = []

        if patient_id:
            query += " AND patient_id LIKE ?"
            params.append(f"%{patient_id.strip()}%")

        if birth_year:
            query += " AND birth_year LIKE ?"
            params.append(f"%{birth_year.strip()}%")

        if gender:
            query += " AND LOWER(gender) = LOWER(?)"
            params.append(gender.strip())

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        name_needle = remove_accents(full_name.strip()) if full_name else ""

        for r in rows:
            p_id, p_name, p_year, p_gender = r[0], r[1], r[2], r[3]
            if name_needle:
                p_name_unaccent = remove_accents(p_name)
                if name_needle not in p_name_unaccent:
                    continue

            results.append({
                "patient_id": p_id,
                "full_name": p_name,
                "birth_year": p_year,
                "gender": p_gender
            })

        return results
