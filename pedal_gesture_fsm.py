import time
import logging
from PySide6.QtCore import QObject, Signal, QTimer
import keyboard

logger = logging.getLogger("PatientApp")

class PedalGestureFSM(QObject):
    gesture_signal = Signal(str)  # Emits: 'SINGLE_TAP', 'DOUBLE_TAP', 'TRIPLE_TAP', 'LONG_PRESS'

    def __init__(self, target_key="f13", window_ms=600, debounce_ms=150, long_press_ms=1500):
        super().__init__()
        self.target_key = target_key.lower()
        self.window_ms = window_ms
        self.debounce_ms = debounce_ms
        self.long_press_ms = long_press_ms

        self.tap_count = 0
        self.last_press_time = 0
        self.key_down_time = 0
        self.is_key_down = False

        # QTimer for Multi-Tap Window Timeout
        self.window_timer = QTimer()
        self.window_timer.setSingleShot(True)
        self.window_timer.timeout.connect(self._on_window_timeout)

        self._hook = None

    def set_target_key(self, key_name):
        self.target_key = key_name.lower()
        self.register_hook()

    def register_hook(self):
        self.unregister_hook()
        try:
            self._hook = keyboard.hook(self._on_keyboard_event)
            logger.info(f"[PEDAL_FSM] Registered FSM keyboard hook for key: {self.target_key.upper()}")
        except Exception as e:
            logger.error(f"[PEDAL_FSM_ERROR] Error registering keyboard hook: {str(e)}")

    def unregister_hook(self):
        if self._hook:
            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
            self._hook = None

    def process_key_down(self):
        self.process_raw_key(self.target_key, "down")

    def process_key_up(self):
        self.process_raw_key(self.target_key, "up")

    def process_raw_key(self, key_name, event_type):
        """
        Process raw key event (called by global keyboard hook or Qt keyPressEvent).
        """
        if key_name.lower() != self.target_key:
            return

        current_time = time.time() * 1000.0  # in ms

        if event_type == "down":
            if self.is_key_down:
                # Ignore Windows auto-repeat KEY_DOWN events while held
                return
            
            self.is_key_down = True
            self.key_down_time = current_time

            # Debounce Rejection (<150ms)
            if (current_time - self.last_press_time) < self.debounce_ms:
                return

            self.last_press_time = current_time
            self.tap_count += 1

            # Start or restart window timer
            self.window_timer.stop()
            self.window_timer.start(self.window_ms)

        elif event_type == "up":
            if not self.is_key_down:
                return
            
            self.is_key_down = False
            hold_duration = current_time - self.key_down_time

            # Check Long Press (>1500ms)
            if hold_duration >= self.long_press_ms:
                self.window_timer.stop()
                self.tap_count = 0
                logger.info(f"[PEDAL_FSM] Gesture Recognized: LONG_PRESS ({hold_duration:.0f}ms)")
                self.gesture_signal.emit("LONG_PRESS")

    def _on_keyboard_event(self, event):
        if event.name.lower() == self.target_key:
            event_type = "down" if event.event_type == keyboard.KEY_DOWN else "up"
            self.process_raw_key(event.name, event_type)

    def _on_window_timeout(self):
        if self.tap_count == 1:
            logger.info("[PEDAL_FSM] Gesture Recognized: SINGLE_TAP")
            self.gesture_signal.emit("SINGLE_TAP")
        elif self.tap_count == 2:
            logger.info("[PEDAL_FSM] Gesture Recognized: DOUBLE_TAP")
            self.gesture_signal.emit("DOUBLE_TAP")
        elif self.tap_count >= 3:
            logger.info(f"[PEDAL_FSM] Gesture Recognized: TRIPLE_TAP ({self.tap_count} taps)")
            self.gesture_signal.emit("TRIPLE_TAP")
            
        self.tap_count = 0
