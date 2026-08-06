import unittest
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType

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

if __name__ == "__main__":
    unittest.main()
