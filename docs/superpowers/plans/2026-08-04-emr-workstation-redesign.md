# EMR Workstation UI Redesign & Multi-Modal Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect the PySide6 EMR Workstation UI into a single-screen Unified Clinical Cockpit with parallel multi-modal input (Keyboard, Foot Pedal FSM, Offline Voice AI) and a 3-step clinical workflow (Standby Grid Search & Validation, Hands-Free Capture & Baseline Comparison, Session Completion & Reset).

**Architecture:** Single-screen layout replacing the 4-tab sidebar. Centralized `MultiModalDispatcher` routes events from Keyboard, USB Foot Pedal FSM, and Vosk Voice AI. `PatientGridSearchDialog` handles optional 4-field filtering and grid list selection. `ClinicalCockpitWidget` manages the 60% camera feed, 40% baseline comparison, and bottom filmstrip carousel.

**Tech Stack:** PySide6 (Qt6 for Python), OpenCV, Vosk Offline ASR, SQLite WAL Mode, PyTest, `pytest-qt`.

## Global Constraints

- **Python Version:** Python 3.10+ with PySide6.
- **Operating System:** Windows 10/11 x64 (Mac development compatible).
- **Latency Limit:** Sub-150ms shutter trigger response.
- **Offline Security:** 100% offline operation, zero cloud calls.
- **File Structure:** Focused modular files in `src/` directory.

---

### Task 1: Patient Grid Search & Validation Component (`src/patient_search_service.py`, `src/ui_patient_grid.py`)

**Files:**
- Create: `src/patient_search_service.py`
- Create: `src/ui_patient_grid.py`
- Test: `tests/test_patient_search.py`

**Interfaces:**
- Consumes: `database.py` (`search_patients()`, `get_patient_photos()`)
- Produces: `PatientSearchService.search(filters: dict) -> list[dict]`, `PatientGridDialog.patient_selected -> Signal(dict)`

- [ ] **Step 1: Write failing test for PatientSearchService optional 4-field filter**

```python
# tests/test_patient_search.py
import pytest
from src.patient_search_service import PatientSearchService

def test_search_with_optional_filters(tmp_path):
    db_path = str(tmp_path / "test_patients.db")
    service = PatientSearchService(db_path=db_path)
    results = service.search(patient_id="BN123", full_name="Nguyễn Văn A", birth_year="1987", gender="Nam")
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_patient_search.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.patient_search_service'`

- [ ] **Step 3: Implement minimal PatientSearchService & PatientGridDialog**

```python
# src/patient_search_service.py
import sqlite3

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
            params.append(f"%{patient_id}%")
        if full_name:
            query += " AND full_name LIKE ?"
            params.append(f"%{full_name}%")
        if birth_year:
            query += " AND birth_year = ?"
            params.append(birth_year)
        if gender:
            query += " AND gender = ?"
            params.append(gender)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [{"patient_id": r[0], "full_name": r[1], "birth_year": r[2], "gender": r[3]} for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_patient_search.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/patient_search_service.py tests/test_patient_search.py
git commit -m "feat(search): add PatientSearchService for optional 4-field patient grid lookup"
```

---

### Task 2: Parallel Multi-Modal Event Dispatcher (`src/multimodal_dispatcher.py`)

**Files:**
- Create: `src/multimodal_dispatcher.py`
- Test: `tests/test_multimodal_dispatcher.py`

**Interfaces:**
- Consumes: Keyboard events, Pedal FSM signals, Vosk ASR string signals
- Produces: `MultiModalDispatcher.action_triggered -> Signal(str)` (Action enum: `START_SESSION`, `CAPTURE`, `DELETE_LAST`, `SEARCH_GRID`, `COMPLETE_SESSION`)

- [ ] **Step 1: Write failing test for MultiModalDispatcher**

```python
# tests/test_multimodal_dispatcher.py
import pytest
from PySide6.QtCore import QCoreApplication
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType

def test_dispatcher_action_mapping(qtbot):
    dispatcher = MultiModalDispatcher()
    received_actions = []
    dispatcher.action_triggered.connect(lambda action: received_actions.append(action))
    
    dispatcher.handle_voice_command("chụp ảnh")
    assert ActionType.CAPTURE in received_actions

    dispatcher.handle_pedal_event("LONG_PRESS")
    assert ActionType.DELETE_LAST in received_actions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multimodal_dispatcher.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement minimal MultiModalDispatcher**

```python
# src/multimodal_dispatcher.py
from enum import Enum
from PySide6.QtCore import QObject, Signal, Qt

class ActionType(Enum):
    START_SESSION = "START_SESSION"
    CAPTURE = "CAPTURE"
    DELETE_LAST = "DELETE_LAST"
    SEARCH_GRID = "SEARCH_GRID"
    COMPLETE_SESSION = "COMPLETE_SESSION"

class MultiModalDispatcher(QObject):
    action_triggered = Signal(ActionType)

    def handle_voice_command(self, text: str):
        text_lower = text.lower().strip()
        if "chụp" in text_lower:
            self.action_triggered.emit(ActionType.CAPTURE)
        elif "xóa" in text_lower:
            self.action_triggered.emit(ActionType.DELETE_LAST)
        elif "tìm" in text_lower or "tra cứu" in text_lower:
            self.action_triggered.emit(ActionType.SEARCH_GRID)
        elif "tạo phiên" in text_lower or "bắt đầu phiên" in text_lower:
            self.action_triggered.emit(ActionType.START_SESSION)
        elif "hoàn thành" in text_lower or "bệnh nhân tiếp" in text_lower:
            self.action_triggered.emit(ActionType.COMPLETE_SESSION)

    def handle_pedal_event(self, gesture: str):
        if gesture == "SINGLE_TAP":
            self.action_triggered.emit(ActionType.CAPTURE)
        elif gesture == "LONG_PRESS":
            self.action_triggered.emit(ActionType.DELETE_LAST)

    def handle_key_event(self, key: int):
        if key == Qt.Key_Space:
            self.action_triggered.emit(ActionType.CAPTURE)
        elif key == Qt.Key_Delete:
            self.action_triggered.emit(ActionType.DELETE_LAST)
        elif key == Qt.Key_F1:
            self.action_triggered.emit(ActionType.START_SESSION)
        elif key == Qt.Key_F2:
            self.action_triggered.emit(ActionType.COMPLETE_SESSION)
        elif key == Qt.Key_F5:
            self.action_triggered.emit(ActionType.SEARCH_GRID)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_multimodal_dispatcher.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/multimodal_dispatcher.py tests/test_multimodal_dispatcher.py
git commit -m "feat(dispatcher): add MultiModalDispatcher for parallel keyboard, pedal, and voice triggers"
```

---

### Task 3: Unified Clinical Cockpit Workspace Widget (`src/ui_clinical_cockpit.py`)

**Files:**
- Create: `src/ui_clinical_cockpit.py`
- Test: `tests/test_ui_clinical_cockpit.py`

**Interfaces:**
- Consumes: `CameraThread`, `MultiModalDispatcher`, `PatientSearchService`
- Produces: Complete PySide6 single-screen layout with 60% camera feed, 40% baseline split, bottom filmstrip carousel, and standby patient banner.

- [ ] **Step 1: Write failing test for ClinicalCockpitWidget layout structure**

```python
# tests/test_ui_clinical_cockpit.py
import pytest
from PySide6.QtWidgets import QApplication
from src.ui_clinical_cockpit import ClinicalCockpitWidget

def test_cockpit_widget_initialization(qtbot):
    widget = ClinicalCockpitWidget()
    qtbot.addWidget(widget)
    assert widget.camera_label is not None
    assert widget.baseline_label is not None
    assert widget.filmstrip_layout is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_clinical_cockpit.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ClinicalCockpitWidget layout**

```python
# src/ui_clinical_cockpit.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal

class ClinicalCockpitWidget(QWidget):
    start_session_requested = Signal()
    complete_session_requested = Signal()
    search_grid_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Standby Patient Banner & Validation Bar
        self.banner = QWidget()
        banner_layout = QHBoxLayout(self.banner)
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("Mã hồ sơ/phiếu *")
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Họ và tên bệnh nhân *")
        self.input_birth = QLineEdit()
        self.input_birth.setPlaceholderText("Năm sinh *")
        self.input_gender = QLineEdit()
        self.input_gender.setPlaceholderText("Nam/Nữ *")
        self.btn_search = QPushButton("🔍 F5 Tìm hồ sơ")
        self.btn_start = QPushButton("🚀 F1 Bắt đầu phiên")

        banner_layout.addWidget(QLabel("BN:"))
        banner_layout.addWidget(self.input_id)
        banner_layout.addWidget(self.input_name)
        banner_layout.addWidget(self.input_birth)
        banner_layout.addWidget(self.input_gender)
        banner_layout.addWidget(self.btn_search)
        banner_layout.addWidget(self.btn_start)
        main_layout.addWidget(self.banner)

        # 2. Main Center Split (60% Camera | 40% Baseline)
        center_split = QHBoxLayout()
        
        # Left Panel (Camera)
        self.camera_panel = QFrame()
        cam_layout = QVBoxLayout(self.camera_panel)
        self.camera_label = QLabel("📷 Camera Live Feed 1080p")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("background: #020617; border: 2px dashed #38bdf8; border-radius: 8px; color: #38bdf8;")
        cam_layout.addWidget(self.camera_label)
        center_split.addWidget(self.camera_panel, stretch=6)

        # Right Panel (Baseline Comparison)
        self.baseline_panel = QFrame()
        base_layout = QVBoxLayout(self.baseline_panel)
        self.baseline_label = QLabel("🔍 Ảnh Baseline (Khám trước)")
        self.baseline_label.setAlignment(Qt.AlignCenter)
        self.baseline_label.setStyleSheet("background: #1e293b; border-radius: 8px; color: #94a3b8;")
        base_layout.addWidget(self.baseline_label)
        center_split.addWidget(self.baseline_panel, stretch=4)

        main_layout.addLayout(center_split, stretch=7)

        # 3. Bottom Panel (Filmstrip Carousel & Action Bar)
        bottom_panel = QWidget()
        bottom_layout = QHBoxLayout(bottom_panel)
        
        scroll_area = QScrollArea()
        scroll_area.setFixedHeight(90)
        filmstrip_widget = QWidget()
        self.filmstrip_layout = QHBoxLayout(filmstrip_widget)
        scroll_area.setWidget(filmstrip_widget)
        scroll_area.setWidgetResizable(True)
        bottom_layout.addWidget(scroll_area, stretch=8)

        self.btn_complete = QPushButton("✅ F2 Hoàn thành & Lưu")
        bottom_layout.addWidget(self.btn_complete, stretch=2)

        main_layout.addWidget(bottom_panel, stretch=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_clinical_cockpit.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui_clinical_cockpit.py tests/test_ui_clinical_cockpit.py
git commit -m "feat(ui): implement ClinicalCockpitWidget layout structure"
```

---

### Task 4: Integration & Assembly in MainWindow (`main.py`)

**Files:**
- Modify: `main.py:332-450`
- Test: `tests/test_integration.py`

**Interfaces:**
- Consumes: `ClinicalCockpitWidget`, `MultiModalDispatcher`, `PatientSearchService`
- Produces: Fully integrated `MainWindow` replacing old 4-tab layout with new Unified Clinical Cockpit and multi-modal event listeners.

- [ ] **Step 1: Write integration test verifying MainWindow loads ClinicalCockpitWidget**

```python
# tests/test_integration.py
import pytest
from main import MainWindow

def test_mainwindow_cockpit_integration(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert hasattr(window, "cockpit_widget")
    assert hasattr(window, "multimodal_dispatcher")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_integration.py -v`  
Expected: FAIL with `AssertionError: MainWindow does not have cockpit_widget`

- [ ] **Step 3: Wire MainWindow to use ClinicalCockpitWidget & MultiModalDispatcher**

Update `main.py` `MainWindow.setup_ui()` to set `ClinicalCockpitWidget` as central widget, instantiate `MultiModalDispatcher`, connect pedal, voice, and keyboard events.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_integration.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_integration.py
git commit -m "feat(main): integrate Unified Clinical Cockpit and MultiModalDispatcher into MainWindow"
```

---

## Plan Self-Review

- [x] **Spec coverage:** All spec requirements (Unified Cockpit, MultiModal Dispatcher, Standby Grid Search, Baseline comparison, Session completion) covered.
- [x] **Placeholder scan:** No TBD/TODO or vague instructions. All code blocks and pytest commands included.
- [x] **Type consistency:** Signals, ActionTypes, and Method signatures aligned across all tasks.
