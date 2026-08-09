"""Unit tests for PatientSessionController FSM (no Qt dependency)."""

import unittest

from src.patient_session_controller import (
    Affordances,
    BarcodeScan,
    CloseSearch,
    ConfirmNewPatientId,
    Demography,
    Effect,
    Field,
    Hotkey,
    LoadRecord,
    PatientSessionController,
    PedalGesture,
    Phase,
    SearchFilterEdit,
    SearchMode,
    UiFieldEdit,
    UiUnlock,
    VoiceUtterance,
)


def _fill_gate(ctrl: PatientSessionController) -> None:
    ctrl.handle(UiFieldEdit(Field.PATIENT_ID, "BN001"))
    ctrl.handle(UiFieldEdit(Field.FULL_NAME, "Nguyen Van A"))
    ctrl.handle(UiFieldEdit(Field.BIRTH_YEAR, 1985))
    ctrl.handle(UiFieldEdit(Field.GENDER, "Nam"))


class TestPatientSessionController(unittest.TestCase):
    def setUp(self):
        self.ctrl = PatientSessionController()

    def test_starts_in_standby(self):
        view = self.ctrl.snapshot()
        self.assertEqual(view.phase, Phase.STANDBY)
        self.assertTrue(view.affordances.start_session)
        self.assertFalse(view.affordances.begin_capture)
        self.assertFalse(view.affordances.pedal_capture)
        self.assertEqual(view.affordances.voice_mode, "off")

    def test_f1_opens_intake_and_arms_devices(self):
        out = self.ctrl.handle(Hotkey("F1"))
        self.assertEqual(out.view.phase, Phase.INTAKE)
        self.assertIn(Effect.POWER_DEVICES_ON, out.effects)
        self.assertTrue(out.view.affordances.can_open_search)
        self.assertEqual(out.view.affordances.voice_mode, "intake_pattern")

    def test_clearing_patient_id_does_not_store_literal_none(self):
        """Regression: str(None) used to persist as patient_id='None' on UI."""
        self.ctrl.handle(Hotkey("F1"))
        self.ctrl.handle(UiFieldEdit(Field.PATIENT_ID, "BN001"))
        out = self.ctrl.handle(UiFieldEdit(Field.PATIENT_ID, None))
        self.assertIsNone(out.view.demography.patient_id)
        out = self.ctrl.handle(UiFieldEdit(Field.PATIENT_ID, "None"))
        self.assertIsNone(out.view.demography.patient_id)
        out = self.ctrl.handle(UiFieldEdit(Field.FULL_NAME, None))
        self.assertIsNone(out.view.demography.full_name)

    def test_gate_incomplete_stays_intake_f2_rejected(self):
        self.ctrl.handle(Hotkey("F1"))
        self.ctrl.handle(UiFieldEdit(Field.PATIENT_ID, "BN001"))
        self.ctrl.handle(UiFieldEdit(Field.FULL_NAME, "A"))
        out = self.ctrl.handle(Hotkey("F2"))
        self.assertEqual(out.view.phase, Phase.INTAKE)
        self.assertIn(Effect.WARN, out.effects)
        self.assertFalse(out.view.affordances.begin_capture)
        self.assertIn(Field.BIRTH_YEAR, out.view.missing_for_gate)
        self.assertIn(Field.GENDER, out.view.missing_for_gate)

    def test_full_gate_moves_to_ready_then_f2_locks(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.assertEqual(self.ctrl.snapshot().phase, Phase.READY)
        self.assertTrue(self.ctrl.snapshot().affordances.begin_capture)

        out = self.ctrl.handle(Hotkey("F2"))
        self.assertEqual(out.view.phase, Phase.LOCKED_CAPTURE)
        self.assertTrue(out.view.affordances.pedal_capture)
        self.assertEqual(out.view.affordances.voice_mode, "command")
        self.assertEqual(out.view.affordances.editable, frozenset())

    def test_pedal_and_space_capture_only_when_locked(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(PedalGesture())
        self.assertNotIn(Effect.CAPTURE_FRAME, out.effects)

        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(PedalGesture())
        self.assertIn(Effect.CAPTURE_FRAME, out.effects)
        out = self.ctrl.handle(Hotkey("Space"))
        self.assertIn(Effect.CAPTURE_FRAME, out.effects)

    def test_delete_only_when_locked(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(Hotkey("Delete"))
        self.assertNotIn(Effect.DELETE_LAST, out.effects)

        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(Hotkey("Delete"))
        self.assertIn(Effect.DELETE_LAST, out.effects)

    def test_f4_ends_to_standby(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(Hotkey("F4"))
        self.assertEqual(out.view.phase, Phase.STANDBY)
        self.assertIn(Effect.PERSIST_AND_CLEAR, out.effects)
        self.assertIn(Effect.POWER_DEVICES_OFF, out.effects)
        self.assertIsNone(out.view.demography.patient_id)

    def test_barcode_intake_opens_search_not_capture(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(BarcodeScan("PHCN123"))
        self.assertTrue(out.view.search.open)
        self.assertEqual(out.view.search.filter.patient_id, "PHCN123")
        self.assertEqual(out.view.search.mode, SearchMode.FILTERED)
        self.assertIn(Effect.OPEN_SEARCH_GRID, out.effects)
        self.assertNotIn(Effect.CAPTURE_FRAME, out.effects)
        self.assertIsNone(out.view.demography.patient_id)
        self.assertEqual(out.view.affordances.voice_mode, "search_filter")

    def test_barcode_locked_different_id_warns(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(BarcodeScan("OTHER"))
        self.assertEqual(out.view.demography.patient_id, "BN001")
        self.assertIn(Effect.WARN, out.effects)
        self.assertFalse(out.view.search.open)

    def test_load_record_replaces_and_closes_search(self):
        self.ctrl.handle(Hotkey("F1"))
        self.ctrl.handle(BarcodeScan("X"))
        out = self.ctrl.handle(
            LoadRecord(
                Demography(
                    patient_id="BN009",
                    full_name="Tran B",
                    birth_year=1990,
                    gender="Nữ",
                )
            )
        )
        self.assertFalse(out.view.search.open)
        self.assertIn(Effect.CLOSE_SEARCH_GRID, out.effects)
        self.assertEqual(out.view.demography.patient_id, "BN009")
        self.assertEqual(out.view.phase, Phase.READY)

    def test_load_record_rejected_when_locked(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(
            LoadRecord(Demography("ZZ", "Hack", 2000, "Nam"))
        )
        self.assertEqual(out.view.demography.patient_id, "BN001")
        self.assertIn(Effect.WARN, out.effects)

    def test_f5_opens_recent_search(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(Hotkey("F5"))
        self.assertTrue(out.view.search.open)
        self.assertEqual(out.view.search.mode, SearchMode.RECENT)
        self.assertIn(Effect.OPEN_SEARCH_GRID, out.effects)

    def test_f5_ignored_when_locked(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(Hotkey("F5"))
        self.assertFalse(out.view.search.open)
        self.assertIn(Effect.WARN, out.effects)

    def test_confirm_new_patient_id_from_empty_search(self):
        self.ctrl.handle(Hotkey("F1"))
        self.ctrl.handle(BarcodeScan("NEW99"))
        self.ctrl.handle(
            SearchFilterEdit(patient_id="NEW99", result_count=0)
        )
        out = self.ctrl.handle(ConfirmNewPatientId())
        self.assertEqual(out.view.demography.patient_id, "NEW99")
        self.assertIsNone(out.view.demography.full_name)
        self.assertFalse(out.view.search.open)
        self.assertEqual(out.view.phase, Phase.INTAKE)

    def test_voice_never_sets_patient_id(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(VoiceUtterance("mã bệnh nhân BN999"))
        self.assertIsNone(out.view.demography.patient_id)

    def test_voice_begin_capture_when_ready(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        out = self.ctrl.handle(VoiceUtterance("bắt đầu chụp"))
        self.assertEqual(out.view.phase, Phase.LOCKED_CAPTURE)

    def test_voice_end_aliases(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(VoiceUtterance("chuyển bệnh nhân mới"))
        self.assertEqual(out.view.phase, Phase.STANDBY)
        self.assertIn(Effect.PERSIST_AND_CLEAR, out.effects)

    def test_correction_unlock_name_then_relock(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(UiUnlock(frozenset({Field.FULL_NAME})))
        self.assertEqual(out.view.phase, Phase.CORRECTION)
        self.assertIn(Field.FULL_NAME, out.view.affordances.editable)

        out = self.ctrl.handle(UiFieldEdit(Field.FULL_NAME, "Nguyen Van B"))
        self.assertEqual(out.view.demography.full_name, "Nguyen Van B")
        self.assertEqual(out.view.phase, Phase.LOCKED_CAPTURE)
        self.assertEqual(out.view.affordances.editable, frozenset())

    def test_correction_multi_field_stays_open_until_all_edited(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        self.ctrl.handle(
            UiUnlock(frozenset({Field.FULL_NAME, Field.BIRTH_YEAR}))
        )
        out = self.ctrl.handle(UiFieldEdit(Field.FULL_NAME, "Tran Thi C"))
        self.assertEqual(out.view.phase, Phase.CORRECTION)
        self.assertIn(Field.BIRTH_YEAR, out.view.affordances.editable)

        out = self.ctrl.handle(UiFieldEdit(Field.BIRTH_YEAR, 1985))
        self.assertEqual(out.view.phase, Phase.LOCKED_CAPTURE)
        self.assertEqual(out.view.demography.birth_year, 1985)

    def test_f2_closes_search_grid(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F5"))
        out = self.ctrl.handle(Hotkey("F2"))
        self.assertEqual(out.view.phase, Phase.LOCKED_CAPTURE)
        self.assertFalse(out.view.search.open)
        self.assertIn(Effect.CLOSE_SEARCH_GRID, out.effects)

    def test_ui_field_edit_ignored_when_locked(self):
        self.ctrl.handle(Hotkey("F1"))
        _fill_gate(self.ctrl)
        self.ctrl.handle(Hotkey("F2"))
        out = self.ctrl.handle(UiFieldEdit(Field.FULL_NAME, "Hacked"))
        self.assertEqual(out.view.demography.full_name, "Nguyen Van A")
        self.assertIn(Effect.WARN, out.effects)

    def test_close_search(self):
        self.ctrl.handle(Hotkey("F1"))
        self.ctrl.handle(Hotkey("F5"))
        out = self.ctrl.handle(CloseSearch())
        self.assertFalse(out.view.search.open)
        self.assertIn(Effect.CLOSE_SEARCH_GRID, out.effects)

    def test_f1_from_intake_ends_session(self):
        self.ctrl.handle(Hotkey("F1"))
        out = self.ctrl.handle(Hotkey("F1"))
        self.assertEqual(out.view.phase, Phase.STANDBY)
        self.assertIn(Effect.POWER_DEVICES_OFF, out.effects)


if __name__ == "__main__":
    unittest.main()
