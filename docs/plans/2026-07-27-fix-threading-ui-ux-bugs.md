# Fix Threading, Concurrency Conflicts, Logic & UI/UX Issues Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix memory leakage, race conditions, double triggers in voice/pedal controls, SQLite connection leaks, main thread blocking, and enhance UI/UX workflows in Patient Capture Workstation.

**Architecture:** Use explicit QImage memory copying, deduplicate signals in voice/pedal modules, adopt context managers for database connections, eliminate unsafe thread terminations (`QThread.terminate`), wrap COM port checking in a QThread, and add a native PySide6 image preview dialog.

**Tech Stack:** Python 3.10+, PySide6, OpenCV, PyAudio, Vosk Speech AI, SQLite (WAL mode), pyzbar.

---

### Task 1: Fix `QImage` Memory Leak & Safe Camera Thread Termination

**Files:**
- Modify: `main.py:83-178`

**Step 1: Inspect camera frame signal emission & thread stop method**
Verify `qt_image = QImage(rgb_frame.data, ...)` and `self.terminate()` usage in `CameraThread`.

**Step 2: Add `.copy()` to `QImage` and implement cooperative `stop()`**
Modify `CameraThread.run()` to emit `QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()`.
Modify `CameraThread.stop()` to set `self._running = False`, wait for thread exit safely without calling `self.terminate()`.

---

### Task 2: Fix Voice Detector & Pedal FSM Double Trigger Bugs

**Files:**
- Modify: `voice_detector.py:239-267`
- Modify: `main.py:1015-1040`

**Step 1: Remove redundant `capture_signal.emit()` in `voice_detector.py`**
In `VoiceDetectorThread.run()`, remove `self.capture_signal.emit()` when a keyword is recognized.

**Step 2: Remove redundant manual key processing in `MainWindow.keyPressEvent`**
In `main.py`, remove manual invocation of `self.pedal_fsm.process_raw_key()` inside `keyPressEvent()` so that global keyboard hook handles pedal presses exclusively once.

---

### Task 3: SQLite Connection Context Manager & Leak Fixes

**Files:**
- Modify: `database.py:150-394`

**Step 1: Wrap DB queries with `with get_db_connection() as conn:`**
Ensure all database functions (`get_patient`, `create_patient`, `update_patient`, `add_photo`, `delete_photo`, `get_patient_photos`) release SQLite connection handles even if exceptions occur.

---

### Task 4: Fix Hardware Test Dialog GUI Freezing & Native Image Preview Dialog

**Files:**
- Modify: `hardware_test_dialogs.py:270-330`
- Modify: `main.py:1285-1310`

**Step 1: Implement non-blocking COM Port Test in `hardware_test_dialogs.py`**
Run PowerShell check asynchronously or using `QTimer` without blocking the main GUI loop.

**Step 2: Create `ImagePreviewDialog` in `hardware_test_dialogs.py`**
Build a native modal viewer with zoom and keyboard navigation to replace `os.startfile()`.

---

### Task 5: Fix OTA Updater Batch Script Executable Detection

**Files:**
- Modify: `updater.py:114-127`

**Step 1: Update batch script generator for PyInstaller `.exe` builds**
Detect `getattr(sys, 'frozen', False)` and set proper executable launch command in `updater.bat`.

---

### Task 6: UI/UX Enhancements for Clinical Workflow

**Files:**
- Modify: `main.py:440-565`

**Step 1: Add "Set as Baseline Comparison Photo" in Gallery Context Menu**
Allow doctors to pick any thumbnail from the gallery strip to compare against live camera feed.

**Step 2: Add Clear/Next Patient Button**
Add an explicit "Hoàn thành & Sang bệnh nhân mới" action in Tab 1 top banner.
