from enum import Enum

class ActionType(Enum):
    START_SESSION = "START_SESSION"
    CAPTURE = "CAPTURE"
    DELETE_LAST = "DELETE_LAST"
    SEARCH_GRID = "SEARCH_GRID"
    COMPLETE_SESSION = "COMPLETE_SESSION"

try:
    from PySide6.QtCore import QObject, Signal, Qt
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    class QObject:
        pass
    class Signal:
        def __init__(self, *args):
            self._callbacks = []
        def connect(self, callback):
            self._callbacks.append(callback)
        def emit(self, val):
            for cb in self._callbacks:
                cb(val)
    class Qt:
        Key_Space = 32
        Key_Delete = 16777219
        Key_Backspace = 16777219
        Key_F1 = 16777264
        Key_F2 = 16777265
        Key_F5 = 16777268

class MultiModalDispatcher(QObject):
    if HAS_PYSIDE6:
        action_triggered = Signal(ActionType)
    else:
        def __init__(self):
            super().__init__()
            self.action_triggered = Signal(ActionType)

    def handle_voice_command(self, text: str):
        if not text:
            return
        text_lower = text.lower().strip()
        if "chụp" in text_lower:
            self.action_triggered.emit(ActionType.CAPTURE)
        elif "xóa" in text_lower:
            self.action_triggered.emit(ActionType.DELETE_LAST)
        elif "tìm" in text_lower or "tra cứu" in text_lower:
            self.action_triggered.emit(ActionType.SEARCH_GRID)
        elif "tạo phiên" in text_lower or "bắt đầu phiên" in text_lower:
            self.action_triggered.emit(ActionType.START_SESSION)
        elif "hoàn thành" in text_lower or "tiếp theo" in text_lower or "bệnh nhân tiếp" in text_lower:
            self.action_triggered.emit(ActionType.COMPLETE_SESSION)

    def handle_pedal_event(self, gesture: str):
        if gesture == "SINGLE_TAP":
            self.action_triggered.emit(ActionType.CAPTURE)
        elif gesture == "LONG_PRESS":
            self.action_triggered.emit(ActionType.DELETE_LAST)

    def handle_key_event(self, key_val: int):
        if key_val == Qt.Key_Space:
            self.action_triggered.emit(ActionType.CAPTURE)
        elif key_val == Qt.Key_Delete or key_val == Qt.Key_Backspace:
            self.action_triggered.emit(ActionType.DELETE_LAST)
        elif key_val == Qt.Key_F1:
            self.action_triggered.emit(ActionType.START_SESSION)
        elif key_val == Qt.Key_F2:
            self.action_triggered.emit(ActionType.COMPLETE_SESSION)
        elif key_val == Qt.Key_F5:
            self.action_triggered.emit(ActionType.SEARCH_GRID)
