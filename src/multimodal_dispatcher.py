"""Unified MultiModal Event Dispatcher — routes Keyboard, Pedal, and Voice inputs to ActionType signals."""

from enum import Enum
from PySide6.QtCore import QObject, Signal, Qt


class ActionType(Enum):
    """Clinical actions triggered by any input modality."""
    START_SESSION = "START_SESSION"
    CAPTURE = "CAPTURE"
    DELETE_LAST = "DELETE_LAST"
    SEARCH_GRID = "SEARCH_GRID"
    COMPLETE_SESSION = "COMPLETE_SESSION"


# Lookup tables replace repeated if/elif chains (Fowler: Repeated Switches)
VOICE_MAP = {
    "chụp": ActionType.CAPTURE,
    "chụp ảnh": ActionType.CAPTURE,
    "xóa": ActionType.DELETE_LAST,
    "xóa ảnh": ActionType.DELETE_LAST,
    "tìm": ActionType.SEARCH_GRID,
    "tìm kiếm": ActionType.SEARCH_GRID,
    "tra cứu": ActionType.SEARCH_GRID,
    "tạo phiên": ActionType.START_SESSION,
    "bắt đầu phiên": ActionType.START_SESSION,
    "bắt đầu": ActionType.START_SESSION,
    "hoàn thành": ActionType.COMPLETE_SESSION,
    "tiếp theo": ActionType.COMPLETE_SESSION,
    "bệnh nhân tiếp": ActionType.COMPLETE_SESSION,
}

PEDAL_MAP = {
    "SINGLE_TAP": ActionType.CAPTURE,
    "LONG_PRESS": ActionType.DELETE_LAST,
}

KEY_MAP = {
    Qt.Key_Space: ActionType.CAPTURE,
    Qt.Key_Delete: ActionType.DELETE_LAST,
    Qt.Key_Backspace: ActionType.DELETE_LAST,
    Qt.Key_F1: ActionType.START_SESSION,
    Qt.Key_F2: ActionType.COMPLETE_SESSION,
    Qt.Key_F5: ActionType.SEARCH_GRID,
}


class MultiModalDispatcher(QObject):
    """Dispatches clinical actions from any of the 3 parallel input channels."""

    action_triggered = Signal(ActionType)

    def handle_voice_command(self, text: str) -> None:
        """Match Vietnamese voice keywords against VOICE_MAP lookup table."""
        if not text:
            return
        text_lower = text.lower().strip()
        # Try exact match first, then substring match
        action = VOICE_MAP.get(text_lower)
        if action is None:
            for keyword, act in VOICE_MAP.items():
                if keyword in text_lower:
                    action = act
                    break
        if action is not None:
            self.action_triggered.emit(action)

    def handle_pedal_event(self, gesture: str) -> None:
        """Map pedal FSM gesture string to action via PEDAL_MAP."""
        action = PEDAL_MAP.get(gesture)
        if action is not None:
            self.action_triggered.emit(action)

    def handle_key_event(self, key_val: int) -> None:
        """Map Qt key code to action via KEY_MAP."""
        action = KEY_MAP.get(key_val)
        if action is not None:
            self.action_triggered.emit(action)
