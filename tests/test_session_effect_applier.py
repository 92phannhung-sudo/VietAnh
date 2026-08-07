"""Unit tests for SessionEffectApplier."""

import unittest

from src.patient_session_controller import Hotkey, PatientSessionController
from src.session_effect_applier import SessionEffectApplier


class TestSessionEffectApplier(unittest.TestCase):
    def test_f1_triggers_power_on_hook(self):
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
        ctrl = PatientSessionController()
        out = ctrl.handle(Hotkey("F1"))
        applier.apply(out.effects, out.view)
        self.assertIn("on", calls)

    def test_f4_triggers_persist_and_power_off(self):
        calls = []
        applier = SessionEffectApplier(
            on_power_on=lambda: calls.append("on"),
            on_power_off=lambda: calls.append("off"),
            on_capture=lambda: calls.append("cap"),
            on_delete_last=lambda: calls.append("del"),
            on_open_search=lambda view: calls.append("open"),
            on_refresh_search=lambda view: calls.append("refresh"),
            on_close_search=lambda: calls.append("close"),
            on_persist_clear=lambda: calls.append("persist"),
            on_warn=lambda view: calls.append("warn"),
        )
        ctrl = PatientSessionController()
        ctrl.handle(Hotkey("F1"))
        out = ctrl.handle(Hotkey("F4"))
        applier.apply(out.effects, out.view)
        self.assertIn("persist", calls)
        self.assertIn("off", calls)


if __name__ == "__main__":
    unittest.main()
