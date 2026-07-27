# SYSTEM SPECIFICATION: ACTION MAPPING & MULTI-GESTURE ENGINE

## 1. Executive Summary
This document specifies the technical architecture, data models, Finite State Machine (FSM), and voice grammar rules for the **Extensible Multi-Gesture & Voice Action Mapping System**. 

The system decouples physical hardware triggers (USB Foot Pedal gestures, Vosk offline voice keywords) from logical clinical actions (Photo Capture, Photo Deletion, Patient Switch, Fullscreen Review), allowing each medical staff member to customize their own interaction profile.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------------------+
|                               HARDWARE LAYER                                      |
|   [ USB Foot Pedal (F13) ]                   [ AI Microphone / Voice Clarity ]    |
+--------------------------+----------------------------------+---------------------+
                           |                                  |
                           v                                  v
+------------------------------------------+ +--------------------------------------+
|  Pedal Gesture FSM Engine                | |  Vosk Voice Grammar Engine           |
|  - Key Debounce Filter (<150ms)          | |  - Grammar: ["chụp","xóa",...]      |
|  - Timer Window (600-800ms)              | |  - Cooldown Guard (2.5s)            |
|  - Emits: SINGLE_TAP, DOUBLE_TAP, etc.   | |  - Emits: Keyword Events            |
+--------------------------+---------------+ +----------------+---------------------+
                           |                                  |
                           +----------------+-----------------+
                                            |
                                            v
+-----------------------------------------------------------------------------------+
|  Action Mapper & Per-Staff Profile Dispatcher                                      |
|  - Queries SQLite `staff_action_mappings` by active `staff_id`                     |
|  - Dispatches mapped Trigger -> Logical Action ID                                 |
+-------------------------------------------+---------------------------------------+
                                            |
                                            v
+-----------------------------------------------------------------------------------+
|  Action Registry & Handlers (Python Decorators)                                   |
|  - ACTION_CAPTURE      -> MainWindow.trigger_photo_capture()                     |
|  - ACTION_DELETE_LAST  -> database.delete_photo(last_id)                          |
|  - ACTION_NEXT_PATIENT -> MainWindow.reset_for_next_patient()                    |
|  - ACTION_VIEW_PHOTO   -> MainWindow.open_last_photo_fullscreen()                 |
+-----------------------------------------------------------------------------------+
```

---

## 3. Action Registry Specification

Actions are registered in Python code using a centralized `@register_action` decorator pattern. Adding new actions in future iterations requires zero GUI rewrites.

### Initial Registered Actions

| Action ID | Display Label | Description | Default Handlers |
| :--- | :--- | :--- | :--- |
| `ACTION_CAPTURE` | Chụp ảnh Bệnh nhân | Captures a high-resolution frame from Logitech C920e camera. | `SINGLE_TAP`, Voice `"chụp"` |
| `ACTION_DELETE_LAST` | Xóa ảnh vừa chụp | Deletes the most recent photo taken in the current session. | `DOUBLE_TAP`, Voice `"xóa"` |
| `ACTION_NEXT_PATIENT` | Chuyển bệnh án mới | Clears active patient form and waits for new barcode scan. | `TRIPLE_TAP`, Voice `"tiếp"` |
| `ACTION_VIEW_PHOTO` | Xem lại ảnh | Opens the baseline or last photo in fullscreen preview mode. | `LONG_PRESS`, Voice `"xem"` |

---

## 4. Pedal Gesture Finite State Machine (FSM)

To prevent Windows auto-repeat key lag and accurately distinguish between single, double, and triple pedal taps, the pedal thread operates a **Timer-Based State Machine**.

```
                       +-------------------+
                       |    IDLE STATE     |
                       +---------+---------+
                                 |
                         [ Key Press Event ]
                                 v
                       +-------------------+
                       |    TAP DETECTED   |  <--- Start Window Timer (600ms)
                       +---------+---------+
                                 |
         +-----------------------+-----------------------+
         |                                               |
 [ Timer Expires (No 2nd Key) ]                 [ 2nd Key Press Received ]
         |                                               |
         v                                               v
  Emit: SINGLE_TAP                              +------------------+
                                                | DOUBLE_TAP STATE | <--- Restart Window Timer
                                                +--------+---------+
                                                         |
                                 +-----------------------+-----------------------+
                                 |                                               |
                         [ Timer Expires ]                              [ 3rd Key Press ]
                                 |                                               |
                                 v                                               v
                          Emit: DOUBLE_TAP                                Emit: TRIPLE_TAP
```

### FSM Timing Parameters
* **Debounce Rejection Threshold**: $150 \text{ ms}$ (Presses occurring $<150\text{ms}$ apart are ignored as key bounce).
* **Multi-Tap Window Timeout**: $600 \text{ ms}$ (Configurable per staff profile from $400\text{ms}$ to $900\text{ms}$).
* **Long Press Duration Threshold**: $1500 \text{ ms}$ ($1.5 \text{ seconds}$ continuous key hold).

---

## 5. Vosk Voice Grammar Restriction Specification

To achieve $>99\%$ voice recognition accuracy and zero false triggers in noisy clinical environments, the Vosk engine enforces strict **Grammar Array Restrictions**.

### Grammar Configuration
```python
# Vosk Grammar Constraint Array
VOICE_GRAMMAR_JSON = '["chụp", "xóa", "tiếp", "xem", "[unk]"]'
```

### Operational Rules
1. **Unknown Word Suppression**: Any acoustic speech matching words outside the 4 keywords is classified as `[unk]` and discarded.
2. **Instant Partial Result Trigger**: `rec.PartialResult()` triggers action execution within $<80\text{ms}$ upon detecting `"chụp"` or `"xóa"`.
3. **Cooldown Timer Guard**: A $2.5\text{ second}$ mute cooldown is enforced after an action is triggered to prevent conversation echo.

---

## 6. SQLite Database Schema (Per-Staff Configuration)

Per-staff trigger mappings are stored in SQLite table `staff_action_mappings`.

```sql
CREATE TABLE IF NOT EXISTS staff_action_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT NOT NULL,
    trigger_source TEXT NOT NULL,  -- 'PEDAL_GESTURE' or 'VOICE_KEYWORD'
    trigger_value TEXT NOT NULL,   -- 'SINGLE_TAP', 'DOUBLE_TAP', 'LONG_PRESS', 'chụp', 'xóa'
    action_id TEXT NOT NULL,       -- 'ACTION_CAPTURE', 'ACTION_DELETE_LAST', etc.
    updated_at TEXT NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE,
    UNIQUE(staff_id, trigger_source, trigger_value)
);
```

---

| **Voice Accuracy** | Vosk Grammar Array Restriction | Open-vocabulary recognition | Eliminates false triggers from background medical conversations. |
| **User Settings** | SQLite Per-Staff Profile Table | Global `config.json` | Each doctor/KTV maintains their preferred pedal gestures and voice keywords. |

---

## 8. Hardware Discovery, SQLite Caching & Async Loading Modal

### 8.1 Real Device Friendly Naming (`QMediaDevices`)
* Queries `PySide6.QtMultimedia.QMediaDevices.videoInputs()` and `audioInputs()` directly to retrieve physical friendly names (e.g. `Logi Webcam C920e`, `Microphone (2- High Definition Audio Device)`) instead of generic index strings.

### 8.2 SQLite Hardware Device Cache Table (`hardware_devices`)
```sql
CREATE TABLE IF NOT EXISTS hardware_devices (
    device_type TEXT NOT NULL,
    device_name TEXT NOT NULL,
    device_index INTEGER DEFAULT 0,
    device_info TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_type, device_name, device_index)
);
```

### 8.3 Non-Blocking Async Hardware Scanner (`HardwareScannerThread`)
* Runs hardware probes on a background `QThread` (`HardwareScannerThread`).
* Displays a native `QProgressDialog` loading modal showing step-by-step progress (*"Đang kiểm tra Camera vật lý..."*, *"Đang kiểm tra Microphone..."*, *"Đang kiểm tra Cổng COM..."*).
* Automatically persists exactly 4 clean physical component entries into SQLite cache upon completion.
* On application startup, cached devices load directly into Tab 4 in $<5\text{ms}$ without GUI freezes.

---

## 9. Interactive Hardware Test Dialog Specifications

### 9.1 Camera Test Dialog (`CameraTestDialog`)
* **Live Video Preview & Real-Time QR Parsing**: Shows live 1080p stream from selected camera index. Continuously passes frames to `barcode_parser.py`.
* **Success Criteria**: When a QR code or barcode is shown to the camera, plays audio beep cue and displays: `Mã Quét: [ PHCN2647781 ] | Status: OK`.

### 9.2 Microphone Test Dialog (`MicrophoneTestDialog`)
* **Audio Level Gauge & Vosk AI Command Verification**: Renders live RMS Volume Bar ($0..100\%$) and runs Vosk speech recognizer listening for `["chụp", "xóa", "tiếp", "xem"]`.
* **Success Criteria**: Speaking any command displays green badge: `Đã Nhận Lệnh: "CHỤP" | Status: OK`.

### 9.3 Foot Pedal Test Dialog (`PedalTestDialog`)
* **Interactive 4-Gesture Checklist**: Renders dynamic checklist (`Single Tap`, `Double Tap`, `Triple Tap`, `Long Press`).
* **Success Criteria**: Stepping on physical pedal dynamically checks off `[✓]` the corresponding gesture in real time with audio beep.

### 9.4 COM Serial Port Test Dialog (`COMPortTestDialog`)
* **Handshake Verification**: Sends test packet `Ping 0x06` (Baudrate 9600) to RS232/USB Serial port.
* **Success Criteria**: Displays connection status: `Phản Hồi Cổng COM1: OK`.
