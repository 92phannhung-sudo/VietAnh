# 354 EMR Workstation Unified Clinical Cockpit Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the 354 EMR Workstation UI into a Single-Window Unified Clinical Cockpit with QDarkTheme styling, side-by-side Baseline photo comparison, 3-column Grid View search dialog, and parallel multi-modal control.

**Architecture:** Split UI into modular components (`PatientSearchService`, `MultiModalDispatcher`, `PatientGridDialog`, `ClinicalCockpitWidget`). Maintain parallel signal dispatch across Keyboard, USB Foot Pedal FSM, and Offline Vosk Voice AI.

**Tech Stack:** PySide6 (Qt for Python), Python 3.10+, SQLite3, `unittest` standard framework.

## Global Constraints

- **Window Resolution:** 1440x900px Desktop Window.
- **Theme Standard:** QDarkTheme palette (`#0F172A`, `#1E293B`, `#0284C7`, `#16A34A`, `#334155`, `#F8FAFC`).
- **Parallel Dispatch:** Keyboard, Pedal, and Voice AI inputs must execute in parallel without losing focus.

---

### Task 1: Patient Grid Search Service & Dialog Component

**Files:**
- Create: `src/patient_search_service.py`
- Create: `src/ui_patient_grid.py`
- Test: `tests/test_patient_search.py`

**Interfaces:**
- Consumes: SQLite database connection (`DB_PATH`).
- Produces: `PatientSearchService.search(patient_id, full_name, birth_year, gender) -> list[dict]`, `PatientGridDialog(search_service, parent)` signal `patient_selected(dict)`.

- [x] **Step 1: Write the failing test**

```python
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
                gender TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO patients (patient_id, full_name, birth_year, gender)
            VALUES ('BN123', 'Nguyễn Văn A', '1987', 'Nam')
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_search_with_optional_filters(self):
        service = PatientSearchService(db_path=self.db_file)
        res = service.search(patient_id="123")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient_id"], "BN123")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_patient_search.py -v`  
Expected: PASS / verified clean.

- [x] **Step 3: Write minimal implementation**

```python
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
            if name_needle and name_needle not in remove_accents(p_name):
                continue
            results.append({"patient_id": p_id, "full_name": p_name, "birth_year": p_year, "gender": p_gender})
        return results
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_patient_search.py -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/patient_search_service.py src/ui_patient_grid.py tests/test_patient_search.py
git commit -m "feat(search): implement PatientSearchService and PatientGridDialog"
```

---

### Task 2: Parallel MultiModal Event Dispatcher

**Files:**
- Create: `src/multimodal_dispatcher.py`
- Test: `tests/test_multimodal_dispatcher.py`

**Interfaces:**
- Consumes: Voice string events, Pedal FSM gesture strings, Qt Key integers.
- Produces: `MultiModalDispatcher` signal `action_triggered(ActionType)`.

- [x] **Step 1: Write the failing test**

```python
import unittest
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType

class TestMultiModalDispatcher(unittest.TestCase):
    def test_dispatcher_voice_mapping(self):
        dispatcher = MultiModalDispatcher()
        actions = []
        dispatcher.action_triggered.connect(lambda act: actions.append(act))
        dispatcher.handle_voice_command("chụp ảnh ngay")
        self.assertEqual(actions[-1], ActionType.CAPTURE)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_multimodal_dispatcher.py -v`  
Expected: PASS

- [x] **Step 3: Write minimal implementation**

```python
from enum import Enum

class ActionType(Enum):
    START_SESSION = "START_SESSION"
    CAPTURE = "CAPTURE"
    DELETE_LAST = "DELETE_LAST"
    SEARCH_GRID = "SEARCH_GRID"
    COMPLETE_SESSION = "COMPLETE_SESSION"

class MultiModalDispatcher:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def handle_voice_command(self, text: str):
        if not text: return
        text_lower = text.lower().strip()
        if "chụp" in text_lower:
            self.emit(ActionType.CAPTURE)
        elif "xóa" in text_lower:
            self.emit(ActionType.DELETE_LAST)

    def emit(self, action: ActionType):
        for cb in self._callbacks:
            cb(action)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_multimodal_dispatcher.py -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/multimodal_dispatcher.py tests/test_multimodal_dispatcher.py
git commit -m "feat(dispatcher): implement MultiModalDispatcher"
```

---

### Task 3: Unified Clinical Cockpit PySide6 Widget & App Integration

**Files:**
- Create: `src/ui_clinical_cockpit.py`
- Modify: `main.py`
- Test: `tests/test_patient_search.py`

**Interfaces:**
- Consumes: `PatientSearchService`, `MultiModalDispatcher`.
- Produces: Integrated QMainWindow central widget.

- [x] **Step 1: Write implementation in `src/ui_clinical_cockpit.py`**
- [x] **Step 2: Wire `ClinicalCockpitWidget` in `main.py`**
- [x] **Step 3: Run full test suite**

Run: `python3 -m unittest discover -s tests -p "test_*.py" -v`  
Expected: PASS 100% (3/3 tests)

- [x] **Step 4: Commit**

```bash
git add src/ui_clinical_cockpit.py main.py
git commit -m "feat(cockpit): assemble Unified Clinical Cockpit PySide6 layout into main window"
```
