import unittest

# Guard: skip entire module if PySide6 is not installed
try:
    from PySide6.QtCore import Qt
    from src.multimodal_dispatcher import MultiModalDispatcher, ActionType
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 not installed — skipping Qt-dependent tests")
class TestMultiModalDispatcher(unittest.TestCase):
    def test_dispatcher_voice_mapping(self):
        dispatcher = MultiModalDispatcher()
        actions = []
        dispatcher.action_triggered.connect(lambda act: actions.append(act))

        dispatcher.handle_voice_command("chụp ảnh ngay")
        self.assertEqual(actions[-1], ActionType.CAPTURE)

        dispatcher.handle_voice_command("xóa ảnh này")
        self.assertEqual(actions[-1], ActionType.DELETE_LAST)

        dispatcher.handle_voice_command("tìm kiếm hồ sơ bệnh nhân")
        self.assertEqual(actions[-1], ActionType.SEARCH_GRID)

        dispatcher.handle_voice_command("tạo phiên làm việc mới")
        self.assertEqual(actions[-1], ActionType.START_SESSION)

        dispatcher.handle_voice_command("bệnh nhân tiếp theo")
        self.assertEqual(actions[-1], ActionType.COMPLETE_SESSION)

    def test_dispatcher_pedal_mapping(self):
        dispatcher = MultiModalDispatcher()
        actions = []
        dispatcher.action_triggered.connect(lambda act: actions.append(act))

        dispatcher.handle_pedal_event("SINGLE_TAP")
        self.assertEqual(actions[-1], ActionType.CAPTURE)

        dispatcher.handle_pedal_event("LONG_PRESS")
        self.assertEqual(actions[-1], ActionType.DELETE_LAST)

    def test_dispatcher_key_mapping(self):
        dispatcher = MultiModalDispatcher()
        actions = []
        dispatcher.action_triggered.connect(lambda act: actions.append(act))

        dispatcher.handle_key_event(Qt.Key_Space)
        self.assertEqual(actions[-1], ActionType.CAPTURE)

        dispatcher.handle_key_event(Qt.Key_Delete)
        self.assertEqual(actions[-1], ActionType.DELETE_LAST)

        dispatcher.handle_key_event(Qt.Key_F1)
        self.assertEqual(actions[-1], ActionType.START_SESSION)

        dispatcher.handle_key_event(Qt.Key_F2)
        self.assertEqual(actions[-1], ActionType.COMPLETE_SESSION)

        dispatcher.handle_key_event(Qt.Key_F5)
        self.assertEqual(actions[-1], ActionType.SEARCH_GRID)

if __name__ == "__main__":
    unittest.main()
