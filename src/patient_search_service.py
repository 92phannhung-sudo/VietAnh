"""Patient Search Service — exact id, unaccented name, recent N."""

from __future__ import annotations

import sqlite3
import unicodedata
from datetime import datetime
from typing import Dict, List, Tuple


def remove_accents(input_str: str) -> str:
    """Remove Vietnamese diacritics for unaccented fuzzy matching."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize("NFD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


def format_patient_created_at(raw: str | None) -> str:
    """Display created_at as dd/mm/yyyy HH:mm (Vietnamese clinical UI)."""
    if raw is None or not str(raw).strip():
        return "—"
    s = str(raw).strip().replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0]
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if "%H" in fmt:
                return dt.strftime("%d/%m/%Y %H:%M")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return s


class PatientSearchService:
    """Search patients by optional filters: ID (exact), name (unaccented), birth_year, gender."""

    def __init__(self, db_path: str = "patients.db"):
        self.db_path = str(db_path)

    def _column_map(self, conn: sqlite3.Connection) -> Tuple[str, str, str, str, str]:
        """Return (id, name, birth_year, gender, created_at) column names for schema."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(patients)")}
        if "patient_id" in cols:
            created = "created_at" if "created_at" in cols else "patient_id"
            return ("patient_id", "full_name", "birth_year", "gender", created)
        created = "created_at" if "created_at" in cols else "id"
        return ("id", "name", "birth_year", "gender", created)

    def _row_to_dict(self, row: tuple) -> Dict[str, str]:
        p_id, p_name, p_year, p_gender = row[0], row[1], row[2], row[3]
        created_raw = row[4] if len(row) > 4 else None
        return {
            "patient_id": "" if p_id is None else str(p_id),
            "full_name": "" if p_name is None else str(p_name),
            "birth_year": "" if p_year is None else str(p_year),
            "gender": "" if p_gender is None else str(p_gender),
            "created_at": "" if created_raw is None else str(created_raw),
            "created_at_display": format_patient_created_at(
                "" if created_raw is None else str(created_raw)
            ),
        }

    def search_exact_id(self, patient_id: str) -> List[Dict[str, str]]:
        """Return at most one patient with exact id match."""
        needle = (patient_id or "").strip()
        if not needle:
            return []
        return self.search(patient_id=needle)

    def recent(self, limit: int = 50) -> List[Dict[str, str]]:
        """Newest patients first (by created_at when available)."""
        limit = max(1, int(limit))
        with sqlite3.connect(self.db_path) as conn:
            id_c, name_c, by_c, gen_c, created_c = self._column_map(conn)
            query = (
                f"SELECT {id_c}, {name_c}, {by_c}, {gen_c}, {created_c} FROM patients "
                f"ORDER BY {created_c} DESC LIMIT ?"
            )
            rows = conn.execute(query, (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(
        self,
        patient_id: str = "",
        full_name: str = "",
        birth_year: str = "",
        gender: str = "",
    ) -> List[Dict[str, str]]:
        """Return list of patient dicts matching all provided (non-empty) filters.

        - patient_id: exact match (not LIKE)
        - full_name: unaccented substring
        - birth_year / gender: exact when provided
        """
        with sqlite3.connect(self.db_path) as conn:
            id_c, name_c, by_c, gen_c, created_c = self._column_map(conn)
            query = (
                f"SELECT {id_c}, {name_c}, {by_c}, {gen_c}, {created_c} "
                f"FROM patients WHERE 1=1"
            )
            params: list = []

            if patient_id:
                query += f" AND {id_c} = ?"
                params.append(patient_id.strip())
            if birth_year:
                query += f" AND CAST({by_c} AS TEXT) = ?"
                params.append(str(birth_year).strip())
            if gender:
                query += f" AND LOWER({gen_c}) = LOWER(?)"
                params.append(gender.strip())

            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        results: List[Dict[str, str]] = []
        name_needle = remove_accents(full_name.strip()) if full_name else ""

        for row in rows:
            item = self._row_to_dict(row)
            if name_needle and name_needle not in remove_accents(item["full_name"] or ""):
                continue
            results.append(item)

        results.sort(
            key=lambda r: r.get("created_at") or "",
            reverse=True,
        )
        return results
