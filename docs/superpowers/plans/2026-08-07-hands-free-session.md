# Hands-Free Session Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the app so all clinical session decisions go through `PatientSessionController.handle(event)`, matching `docs/SPEC_HANDS_FREE_SESSION_V1.md` (Voice Intake Mode, F5 search, Tab 2 rules, §12 UX).

**Architecture:** Design A — one pure domain door `handle(SessionEvent) → SessionOutcome{view, effects}`. `MainWindow` becomes an effect executor + Qt adapter. `MultiModalDispatcher` / pedal / voice / barcode stop owning lifecycle. Search grid and Cockpit bind to `SessionView`.

**Tech Stack:** Python 3.10+, PySide6, unittest (no Qt in domain tests), existing OpenCV camera + sherpa-onnx voice threads, SQLite via `database.py` / `PatientSearchService`.

## Global Constraints

- Spec: `docs/SPEC_HANDS_FREE_SESSION_V1.md` + `docs/PATIENT_SESSION_CONTROLLER_SPEC.md` + `CONTEXT.md` + ADR 0002.
- Pedal = capture only; never delete/view/next via pedal.
- Voice never writes `patient_id`.
- Barcode in Intake/Ready opens/filters search grid — never auto-capture, never writes Cockpit directly.
- F2 = begin capture; F4 = end session → Standby; no PDF/F10.
- Lexicon voice phrases = global Settings only (no per-staff override in v1).
- Domain module must stay Qt-free (`src/patient_session_controller.py`).
- Prefer TDD; run `python3 -m unittest tests.test_patient_session_controller -v` after domain changes.
- Do not commit unless the user asks (repo rule).

## File map

| File | Responsibility |
|---|---|
| `src/patient_session_controller.py` | FSM + events/view/effects (exists; extend as needed) |
| `tests/test_patient_session_controller.py` | Domain FSM tests (exists; extend) |
| `src/session_effect_applier.py` | Map `Effect` → MainWindow side effects (new) |
| `main.py` | Create controller; route inputs → `handle`; apply outcomes |
| `src/ui_clinical_cockpit.py` | Bind demography/affordances/badges from `SessionView` |
| `src/ui_patient_grid.py` | Recent/filtered/empty-new-patient; 1-hit Enter; voice filter hooks |
| `src/patient_search_service.py` | Exact id; name substring unaccented; recent N newest-first |
| `src/voice_lexicon_store.py` | Load/save global lexicon JSON under APPDATA (new) |
| `hardware_test_dialogs.py` / Tab4 settings UI in `main.py` | Lexicon editor section; remove PDF button |
| `docs/USER_GUIDE.md` (later task) | Align hotkeys with F1/F2/F4 |

---

### Task 1: Verify & freeze domain skeleton (already largely done)

**Files:**
- Verify: `src/patient_session_controller.py`
- Verify: `tests/test_patient_session_controller.py`

**Interfaces:**
- Produces: `PatientSessionController.handle(event: SessionEvent) -> SessionOutcome`, `snapshot() -> SessionView`, enums `Phase`, `Effect`, `Field`, events `Hotkey`, `VoiceUtterance`, `BarcodeScan`, `PedalGesture`, `UiFieldEdit`, `UiUnlock`, `LoadRecord`, `SearchFilterEdit`, `ConfirmNewPatientId`, `CloseSearch`, `LexiconUpdate`

- [x] **Step 1: Run existing domain tests**

```bash
python3 -m unittest tests.test_patient_session_controller -v
```

Expected: `Ran 21 tests` … `OK`

- [x] **Step 2: If any fail, fix only domain module until green** — do not touch `main.py` in this task.

- [x] **Step 3: Mark Task 1 complete** (no commit unless user requests).

---

### Task 2: Session effect applier (pure helper + unit tests)

**Files:**
- Create: `src/session_effect_applier.py`
- Create: `tests/test_session_effect_applier.py`

**Interfaces:**
- Consumes: `Effect`, `SessionView` from `patient_session_controller`
- Produces: `class SessionEffectApplier` with `apply(effects: Sequence[Effect], view: SessionView) -> None` calling injected callbacks

- [x] **Step 1: Write failing test**

```python
# tests/test_session_effect_applier.py
import unittest
from src.patient_session_controller import Effect, SessionView, Phase, Demography, SearchView, Affordances
from src.session_effect_applier import SessionEffectApplier

class TestSessionEffectApplier(unittest.TestCase):
    def test_capture_and_persist_call_hooks(self):
        calls = []
        applier = SessionEffectApplier(
            on_power_on=lambda: calls.append("on"),
            on_power_off=lambda: calls.append("off"),
            on_capture=lambda: calls.append("cap"),
            on_delete_last=lambda: calls.append("del"),
            on_open_search=lambda view: calls.append(("open", view.search.mode.value)),
            on_refresh_search=lambda view: calls.append("refresh"),
            on_close_search=lambda: calls.append("close"),
            on_persist_clear=lambda: calls.append("persist"),
            on_warn=lambda view: calls.append(("warn", view.notice)),
        )
        # minimal view stub — use controller.snapshot() in real wiring
        from src.patient_session_controller import PatientSessionController, Hotkey
        ctrl = PatientSessionController()
        out = ctrl.handle(Hotkey("F1"))
        applier.apply(out.effects, out.view)
        self.assertIn("on", calls)
```

- [x] **Step 2: Run test — expect FAIL** (`ModuleNotFoundError: session_effect_applier`)

```bash
python3 -m unittest tests.test_session_effect_applier -v
```

- [x] **Step 3: Implement minimal applier**

```python
# src/session_effect_applier.py
from collections.abc import Callable, Sequence
from src.patient_session_controller import Effect, SessionView

class SessionEffectApplier:
    def __init__(
        self,
        *,
        on_power_on: Callable[[], None],
        on_power_off: Callable[[], None],
        on_capture: Callable[[], None],
        on_delete_last: Callable[[], None],
        on_open_search: Callable[[SessionView], None],
        on_refresh_search: Callable[[SessionView], None],
        on_close_search: Callable[[], None],
        on_persist_clear: Callable[[], None],
        on_warn: Callable[[SessionView], None],
    ) -> None:
        self._hooks = {
            Effect.POWER_DEVICES_ON: lambda v: on_power_on(),
            Effect.POWER_DEVICES_OFF: lambda v: on_power_off(),
            Effect.CAPTURE_FRAME: lambda v: on_capture(),
            Effect.DELETE_LAST: lambda v: on_delete_last(),
            Effect.OPEN_SEARCH_GRID: on_open_search,
            Effect.REFRESH_SEARCH_RESULTS: on_refresh_search,
            Effect.CLOSE_SEARCH_GRID: lambda v: on_close_search(),
            Effect.PERSIST_AND_CLEAR: lambda v: on_persist_clear(),
            Effect.WARN: on_warn,
        }

    def apply(self, effects: Sequence[Effect], view: SessionView) -> None:
        for fx in effects:
            hook = self._hooks.get(fx)
            if hook:
                hook(view)
```

- [x] **Step 4: Run tests — expect PASS**

```bash
python3 -m unittest tests.test_session_effect_applier tests.test_patient_session_controller -q
```

---

### Task 3: Wire MainWindow inputs → `handle` (pedal, hotkeys, capture/delete)

**Files:**
- Modify: `main.py` (MainWindow `__init__`, `on_pedal_gesture_detected`, `keyPressEvent`, photo capture/delete paths)
- Modify: `src/ui_clinical_cockpit.py` (stop owning session open/close as source of truth; prefer binding from view)

**Interfaces:**
- Consumes: `PatientSessionController`, `SessionEffectApplier`, `Hotkey`, `PedalGesture`
- Produces: `MainWindow.session_ctrl`, `MainWindow._dispatch_session(event)`, `MainWindow._apply_session_outcome(outcome)`

- [x] **Step 1: Add controller + applier in `MainWindow.__init__` after services**

```python
from src.patient_session_controller import (
    PatientSessionController, Hotkey, PedalGesture, VoiceUtterance,
    BarcodeScan, UiFieldEdit, Field, Effect,
)
from src.session_effect_applier import SessionEffectApplier

self.session_ctrl = PatientSessionController()
self.session_applier = SessionEffectApplier(
    on_power_on=self._session_power_on,
    on_power_off=self._session_power_off,
    on_capture=lambda: self.trigger_photo_capture(source="SESSION_CTRL"),
    on_delete_last=self.delete_latest_photo,
    on_open_search=self._session_open_search,
    on_refresh_search=self._session_refresh_search,
    on_close_search=self._session_close_search,
    on_persist_clear=self._session_persist_and_clear,
    on_warn=self._session_warn,
)
```

Implement the `_session_*` methods: power on/off = resume/pause camera barcode + voice + pedal arm; open/refresh/close search = stub that logs until Task 4; persist = existing reset/DB commit path; warn = `status_bar.showMessage(view.notice or "", 4000)`.

- [x] **Step 2: Add dispatcher helper**

```python
def _dispatch_session(self, event):
    outcome = self.session_ctrl.handle(event)
    self.session_applier.apply(outcome.effects, outcome.view)
    self._bind_session_view(outcome.view)
    return outcome
```

`_bind_session_view` updates cockpit fields from `view.demography`, enables F2 from `view.affordances.begin_capture`, sets badge text from `view.phase` / `view.notice` (minimal in this task; full §12 in Task 5).

- [x] **Step 3: Replace pedal handler body**

In `on_pedal_gesture_detected`, **remove** dual `multimodal_dispatcher` + `action_registry` capture/delete. Use:

```python
def on_pedal_gesture_detected(self, gesture):
    # Only SINGLE_TAP (or any) maps to capture-only event
    self._dispatch_session(PedalGesture())
```

- [x] **Step 4: Map F1/F2/F4/F5/Space/Delete in `keyPressEvent` (when not typing in plain QLineEdit)**

```python
from PySide6.QtCore import Qt
key_map = {
    Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F4: "F4", Qt.Key_F5: "F5",
    Qt.Key_Space: "Space", Qt.Key_Delete: "Delete",
}
if event.key() in key_map:
    # Skip Space/Delete if focus is a text field (except when Locked and Space is capture — still prefer session ctrl)
    self._dispatch_session(Hotkey(key_map[event.key()]))
    return
```

- [x] **Step 5: Manual smoke (dev machine)**

Run: `.venv/Scripts/python main.py` (Windows) or project venv.

Check: F1 arms; without 4 fields F2 warns; fill fields → Ready → F2 → Space/pedal captures; F4 returns Standby.

- [x] **Step 6: Run unit tests still green**

```bash
python3 -m unittest tests.test_patient_session_controller tests.test_session_effect_applier -q
```

---

### Task 4: Search service + PatientGridDialog per spec

**Files:**
- Modify: `src/patient_search_service.py`
- Modify: `src/ui_patient_grid.py`
- Modify: `tests/test_patient_search.py`
- Modify: `main.py` (`_session_open_search`, barcode path → `BarcodeScan`)

**Interfaces:**
- Consumes: `SearchView`, `SearchMode`, `LoadRecord`, `ConfirmNewPatientId`, `SearchFilterEdit`, `CloseSearch`
- Produces: `PatientSearchService.recent(limit=50)`, `search_exact_id`, updated `search(...)` matching spec rules

- [x] **Step 1: Extend search tests**

```python
def test_exact_patient_id_not_like(self):
    # insert BN001 and BN001X — query BN001 returns only BN001
    ...

def test_recent_orders_newest_first(self):
    ...
```

- [x] **Step 2: Implement `recent` + exact id match** (name remains unaccented substring; birth_year/gender exact when provided).

- [x] **Step 3: Update `PatientGridDialog`**

Behavior:
- On open with `mode=recent`: call `recent(50)`, show cards.
- On open with filtered id: exact filter; if exactly 1 row, highlight it; **Enter/Space** emits `patient_selected`.
- If 0 rows and filter has `patient_id`: show “Chưa có hồ sơ [id]. Dùng mã này?” + button → emit signal `new_patient_id_confirmed(str)`.
- Dim parent / window title includes “ĐANG TÌM HỒ SƠ”.

- [x] **Step 4: Wire MainWindow barcode**

Where barcode success currently fills patient, replace with:

```python
self._dispatch_session(BarcodeScan(code))
```

`_session_open_search(view)`: create/show dialog; on select → `LoadRecord(Demography(...))`; on confirm new → `ConfirmNewPatientId` after ensuring filter patient_id set via `SearchFilterEdit(..., result_count=0)`.

- [x] **Step 5: Run**

```bash
python3 -m unittest tests.test_patient_search tests.test_patient_session_controller -v
```

Expected: PASS

---

### Task 5: Cockpit UX §12 (badges, F1/F2/F4 labels, missing gate, undo delete)

**Files:**
- Modify: `src/ui_clinical_cockpit.py`
- Modify: `main.py` (`_bind_session_view`, delete path, F1 confirm)

**Interfaces:**
- Consumes: `SessionView.phase`, `affordances`, `missing_for_gate`, `notice`
- Produces: visible labels matching spec §12.2–12.5, 12.7–12.8

- [x] **Step 1: Bind dynamic button copy**

| Affordance / phase | Button text |
|---|---|
| Standby | `F1 Mở phiên` |
| Active session | `F1 Đóng ca (Standby)` |
| Ready + begin_capture | enable `F2 · Bắt đầu chụp (khóa hồ sơ)` |
| else | disable F2; show `Thiếu: …` from `missing_for_gate` |
| end_session | `F4 · Kết thúc phiên (tắt thiết bị)` |

- [x] **Step 2: F1 confirm when leaving session with unsaved filmstrip photos**

Before `_dispatch_session(Hotkey("F1"))` when phase ≠ STANDBY and local photo count > 0: `QMessageBox` offering go to F4 vs cancel. (Shell-level; controller still ends on F1 if confirmed.)

- [x] **Step 3: Pill when Locked** — always-visible label `Đang ghi ảnh cho: {id} — {name}` (also when user switches to Tab 2).

- [x] **Step 4: Delete undo toast** — `delete_latest_photo` keeps path 5s; status bar action or single-shot timer restore if user triggers undo hook (minimal: `QTimer` + keep last deleted row metadata in memory).

- [x] **Step 5: Manual UI check against §12 checklist in spec.**

---

### Task 6: Voice → `VoiceUtterance` (replace keyword dual-dispatch)

**Files:**
- Modify: `main.py` (`on_voice_keyword_detected`, patient voice parse path)
- Optional: keep `patient_voice_parser` for demography extraction but feed results as `UiFieldEdit` only when `view.affordances.editable` allows — or pass raw text to `VoiceUtterance` and let controller parse (preferred for commands; demography patterns already in controller skeleton)

- [x] **Step 1: Change voice keyword slot**

```python
def on_voice_keyword_detected(self, keyword: str):
    if QApplication.activeModalWidget() is not None:
        # If search dialog open, still dispatch VoiceUtterance so controller uses search_filter mode
        pass
    self._dispatch_session(VoiceUtterance(keyword))
```

Remove parallel `multimodal_dispatcher.handle_voice_command` + hardcoded capture/delete for those keywords.

- [x] **Step 2: After end_session via voice alias “chuyển bệnh nhân mới”, ensure warn/toast**

In `_session_warn` / persist path: if notice empty and phase Standby after end, `status_bar.showMessage("Đã kết thúc phiên — nhấn F1 cho BN tiếp", 5000)`.

- [x] **Step 3: Run domain voice-related unit tests + smoke F1→fill→voice bắt đầu chụp→chụp→chuyển bệnh nhân mới.**

---

### Task 7: Tab 2 folder browser rules (no PDF; delete confirm; block jump)

**Files:**
- Modify: `main.py` (`build_tab2_history`, `export_patient_report`, open-in-tab1 handlers)

- [x] **Step 1: Remove / hide `btn_export_report` (F10 PDF)** from Tab 2 UI and any F10 shortcut binding to export.

- [x] **Step 2: Photo delete on Level 2** — on delete action show `QMessageBox.question`; on Yes delete file + `database.delete_photo` if linked.

- [x] **Step 3: “Mở ở Tab Chụp”**

```python
def open_folder_in_capture(self, patient_id: str):
    view = self.session_ctrl.snapshot()
    current = view.demography.patient_id
    if view.phase.value == "standby":
        self.status_bar.showMessage("F1 mở phiên trước", 4000)
        return
    if current and current != patient_id:
        self.status_bar.showMessage(
            f"Đang khám [{current}] — F4 rồi F1 để đổi BN", 5000
        )
        return
    self.switch_tab(0)
```

- [x] **Step 4: Tab 2 search/barcode** — filter folder list only; do **not** call `BarcodeScan` session event while `stack.currentIndex()==1` (or dispatch a UI-only filter). Spec: browse-only.

---

### Task 8: Global voice lexicon Settings

**Files:**
- Create: `src/voice_lexicon_store.py`
- Modify: `main.py` Tab 4 settings section
- Modify: `PatientSessionController` construction to load lexicon
- Test: `tests/test_voice_lexicon_store.py`

- [x] **Step 1: Store API**

```python
# src/voice_lexicon_store.py
def load_lexicon(path: str) -> dict[str, str]: ...
def save_lexicon(path: str, phrases: dict[str, str]) -> None: ...
```

Default = copy of controller `_DEFAULT_LEXICON`. Path under `config` APPDATA dir, e.g. `voice_lexicon.json`.

- [x] **Step 2: Tab 4 simple table** phrase → intent; Save calls `save_lexicon` + `session_ctrl.handle(LexiconUpdate(phrases))`.

- [x] **Step 3: unittest round-trip load/save.**

---

### Task 9: Docs alignment (USER_GUIDE + deprecate stale hotkeys)

**Files:**
- Modify: `docs/USER_GUIDE.md`
- Modify: `README.md` hotkey blurb if present
- Add note at top of `docs/UI_UX_FLOW.md` / `docs/TECHNICAL_SPEC.md`: superseded by `SPEC_HANDS_FREE_SESSION_V1.md` for session/hotkeys/voice engine

- [x] **Step 1: Rewrite USER_GUIDE Tab1 flow** to F1 → search/barcode grid → F2 → pedal capture → F4; remove PDF; note pedal capture-only.

- [x] **Step 2: Add “Superseded” banners** on stale docs rather than rewriting everything.

---

## Spec coverage check

| Spec area | Task |
|---|---|
| PatientSessionController Design A | 1 (done), 2–3 |
| F1/F2/F4/Space/Delete/Pedal | 3, 5, 6 |
| Gate 4 fields / Ready / Locked | 1, 3, 5 |
| Barcode → search / LoadRecord / new patient | 4 |
| Voice Intake + lexicon global | 6, 8 |
| §12 UX banners/confirm/undo/pill | 5, 7 |
| Tab 2 no PDF / delete confirm / block jump | 7 |
| Docs | 9 |
| Correction unlock | already in domain tests; bind UI lock icon in Task 5 if missing |

## Placeholder scan

No TBD steps; commands and key code paths specified. HID keyboard-wedge barcode buffer (critique item) is **out of this plan** — track as follow-up if wedge types into QLineEdit.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-08-07-hands-free-session.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — continue in this session task-by-task with checkpoints  

Which approach?
