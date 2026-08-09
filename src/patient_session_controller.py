"""PatientSessionController — Design A single-door session FSM.

Pure domain module (no Qt). Callers send SessionEvent via handle() and apply
SessionOutcome.view + effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import FrozenSet, Optional, Sequence, Union


class Phase(Enum):
    STANDBY = "standby"
    INTAKE = "intake"
    READY = "ready"
    LOCKED_CAPTURE = "locked_capture"
    CORRECTION = "correction"


class Field(Enum):
    PATIENT_ID = "patient_id"
    FULL_NAME = "full_name"
    BIRTH_YEAR = "birth_year"
    GENDER = "gender"


class Effect(Enum):
    POWER_DEVICES_ON = "power_devices_on"
    POWER_DEVICES_OFF = "power_devices_off"
    CAPTURE_FRAME = "capture_frame"
    DELETE_LAST = "delete_last"
    OPEN_SEARCH_GRID = "open_search_grid"
    REFRESH_SEARCH_RESULTS = "refresh_search_results"
    CLOSE_SEARCH_GRID = "close_search_grid"
    PERSIST_AND_CLEAR = "persist_and_clear"
    WARN = "warn"


class SearchMode(Enum):
    RECENT = "recent"
    FILTERED = "filtered"
    EMPTY_NEW_PATIENT_PROMPT = "empty_new_patient_prompt"


# --- Events -----------------------------------------------------------------

@dataclass(frozen=True)
class Hotkey:
    key: str  # F1 F2 F4 F5 Space Delete


@dataclass(frozen=True)
class VoiceUtterance:
    text: str


@dataclass(frozen=True)
class BarcodeScan:
    code: str


@dataclass(frozen=True)
class PedalGesture:
    """Capture-only pedal contract."""
    kind: str = "capture"


@dataclass(frozen=True)
class UiFieldEdit:
    field: Field
    value: object


@dataclass(frozen=True)
class UiUnlock:
    fields: FrozenSet[Field]


@dataclass(frozen=True)
class Demography:
    patient_id: Optional[str] = None
    full_name: Optional[str] = None
    birth_year: Optional[int] = None
    gender: Optional[str] = None

    def gate_complete(self) -> bool:
        return bool(
            self.patient_id
            and self.full_name
            and self.birth_year is not None
            and self.gender
        )

    def missing_fields(self) -> FrozenSet[Field]:
        missing = []
        if not self.patient_id:
            missing.append(Field.PATIENT_ID)
        if not self.full_name:
            missing.append(Field.FULL_NAME)
        if self.birth_year is None:
            missing.append(Field.BIRTH_YEAR)
        if not self.gender:
            missing.append(Field.GENDER)
        return frozenset(missing)


@dataclass(frozen=True)
class LoadRecord:
    demography: Demography


@dataclass(frozen=True)
class SearchFilterEdit:
    patient_id: Optional[str] = None
    full_name: Optional[str] = None
    birth_year: Optional[str] = None
    gender: Optional[str] = None
    result_count: Optional[int] = None  # shell reports hit count after query


@dataclass(frozen=True)
class ConfirmNewPatientId:
    pass


@dataclass(frozen=True)
class CloseSearch:
    pass


@dataclass(frozen=True)
class LexiconUpdate:
    phrases: dict[str, str]


SessionEvent = Union[
    Hotkey,
    VoiceUtterance,
    BarcodeScan,
    PedalGesture,
    UiFieldEdit,
    UiUnlock,
    LoadRecord,
    SearchFilterEdit,
    ConfirmNewPatientId,
    CloseSearch,
    LexiconUpdate,
]


# --- View -------------------------------------------------------------------

@dataclass(frozen=True)
class SearchView:
    open: bool = False
    mode: SearchMode = SearchMode.RECENT
    filter: SearchFilterEdit = field(default_factory=SearchFilterEdit)


@dataclass(frozen=True)
class Affordances:
    start_session: bool
    begin_capture: bool
    end_session: bool
    pedal_capture: bool
    can_open_search: bool
    voice_mode: str
    editable: FrozenSet[Field]
    patient_id_voice_forbidden: bool = True


@dataclass(frozen=True)
class SessionView:
    phase: Phase
    demography: Demography
    search: SearchView
    affordances: Affordances
    missing_for_gate: FrozenSet[Field]
    notice: Optional[str] = None


@dataclass(frozen=True)
class SessionOutcome:
    view: SessionView
    effects: Sequence[Effect]


# --- Default lexicon (global; overridable via LexiconUpdate) ----------------

_DEFAULT_LEXICON: dict[str, str] = {
    "mở phiên": "start_session",
    "bắt đầu phiên": "start_session",
    "bắt đầu chụp": "begin_capture",
    "bắt đầu khám": "begin_capture",
    "chụp": "capture",
    "chụp ảnh": "capture",
    "xóa": "delete_last",
    "xóa ảnh": "delete_last",
    "kết thúc phiên": "end_session",
    "hoàn thành": "end_session",
    "chuyển bệnh nhân mới": "end_session",
    "bệnh nhân tiếp": "end_session",
    "tìm kiếm": "open_search",
    "tìm kiếm hồ sơ": "open_search",
    "tra cứu": "open_search",
    "sửa tên": "unlock_name",
    "sửa năm sinh": "unlock_birth_year",
    "sửa giới tính": "unlock_gender",
    "mở lại hồ sơ": "unlock_profile",
    "sửa thông tin": "unlock_profile",
    "đóng": "close_search",
    "bệnh nhân mới": "confirm_new_patient",
}


class PatientSessionController:
    """Owns session lifecycle + Voice Intake Mode routing."""

    def __init__(self, lexicon: Optional[dict[str, str]] = None) -> None:
        self._phase = Phase.STANDBY
        self._demo = Demography()
        self._search = SearchView()
        self._correction_fields: FrozenSet[Field] = frozenset()
        self._lexicon = dict(lexicon or _DEFAULT_LEXICON)
        self._notice: Optional[str] = None
        self._photo_count_hint = 0  # shell may track; used only for future F1 confirm

    def snapshot(self) -> SessionView:
        return self._build_view()

    def handle(self, event: SessionEvent) -> SessionOutcome:
        self._notice = None
        effects: list[Effect] = []

        if isinstance(event, LexiconUpdate):
            self._lexicon = dict(event.phrases) if event.phrases else dict(_DEFAULT_LEXICON)
            return SessionOutcome(view=self._build_view(), effects=[])

        if isinstance(event, Hotkey):
            effects.extend(self._on_hotkey(event.key))
        elif isinstance(event, PedalGesture):
            effects.extend(self._on_capture_request())
        elif isinstance(event, BarcodeScan):
            effects.extend(self._on_barcode(event.code))
        elif isinstance(event, UiFieldEdit):
            effects.extend(self._on_ui_field(event))
        elif isinstance(event, UiUnlock):
            effects.extend(self._on_unlock(event.fields))
        elif isinstance(event, LoadRecord):
            effects.extend(self._on_load_record(event.demography))
        elif isinstance(event, SearchFilterEdit):
            effects.extend(self._on_search_filter(event))
        elif isinstance(event, ConfirmNewPatientId):
            effects.extend(self._on_confirm_new_patient())
        elif isinstance(event, CloseSearch):
            effects.extend(self._on_close_search())
        elif isinstance(event, VoiceUtterance):
            effects.extend(self._on_voice(event.text))
        else:
            self._notice = "Unknown event"
            effects.append(Effect.WARN)

        return SessionOutcome(self._build_view(), tuple(effects))

    # --- builders -----------------------------------------------------------

    def _build_view(self) -> SessionView:
        missing = self._demo.missing_fields()
        gate_ok = self._demo.gate_complete()
        search_open = self._search.open

        if self._phase == Phase.STANDBY:
            voice_mode = "off"
            editable: FrozenSet[Field] = frozenset()
        elif search_open:
            voice_mode = "search_filter"
            editable = frozenset()
        elif self._phase == Phase.CORRECTION:
            voice_mode = "correction_pattern"
            editable = self._correction_fields
        elif self._phase == Phase.LOCKED_CAPTURE:
            voice_mode = "command"
            editable = frozenset()
        elif self._phase in (Phase.INTAKE, Phase.READY):
            voice_mode = "intake_pattern"
            editable = frozenset(Field)
        else:
            voice_mode = "off"
            editable = frozenset()

        affordances = Affordances(
            start_session=self._phase == Phase.STANDBY,
            begin_capture=self._phase == Phase.READY and gate_ok,
            end_session=self._phase != Phase.STANDBY,
            pedal_capture=self._phase == Phase.LOCKED_CAPTURE,
            can_open_search=self._phase in (Phase.INTAKE, Phase.READY),
            voice_mode=voice_mode,
            editable=editable,
        )
        return SessionView(
            phase=self._phase,
            demography=self._demo,
            search=self._search,
            affordances=affordances,
            missing_for_gate=missing,
            notice=self._notice,
        )

    def _refresh_phase_after_demo(self) -> None:
        if self._phase in (Phase.INTAKE, Phase.READY):
            self._phase = Phase.READY if self._demo.gate_complete() else Phase.INTAKE

    # --- handlers -----------------------------------------------------------

    def _on_hotkey(self, key: str) -> list[Effect]:
        key = key.strip()
        if key == "F1":
            if self._phase == Phase.STANDBY:
                return self._start_session()
            return self._end_session()
        if key == "F2":
            return self._begin_capture()
        if key == "F4":
            if self._phase == Phase.STANDBY:
                self._notice = "Chưa có phiên"
                return [Effect.WARN]
            return self._end_session()
        if key == "F5":
            return self._open_search_recent()
        if key == "Space":
            return self._on_capture_request()
        if key == "Delete":
            return self._on_delete_request()
        self._notice = f"Phím không hỗ trợ: {key}"
        return [Effect.WARN]

    def _start_session(self) -> list[Effect]:
        self._phase = Phase.INTAKE
        self._demo = Demography()
        self._search = SearchView()
        self._correction_fields = frozenset()
        return [Effect.POWER_DEVICES_ON]

    def _end_session(self) -> list[Effect]:
        self._phase = Phase.STANDBY
        self._demo = Demography()
        self._search = SearchView()
        self._correction_fields = frozenset()
        return [Effect.PERSIST_AND_CLEAR, Effect.POWER_DEVICES_OFF]

    def _begin_capture(self) -> list[Effect]:
        if self._phase != Phase.READY or not self._demo.gate_complete():
            self._notice = "Chưa đủ hồ sơ để bắt đầu chụp"
            return [Effect.WARN]
        effects: list[Effect] = []
        if self._search.open:
            self._search = replace(self._search, open=False)
            effects.append(Effect.CLOSE_SEARCH_GRID)
        self._phase = Phase.LOCKED_CAPTURE
        self._correction_fields = frozenset()
        return effects

    def _on_capture_request(self) -> list[Effect]:
        if self._phase != Phase.LOCKED_CAPTURE:
            self._notice = "Chưa bắt đầu chụp (F2)"
            return [Effect.WARN]
        return [Effect.CAPTURE_FRAME]

    def _on_delete_request(self) -> list[Effect]:
        if self._phase != Phase.LOCKED_CAPTURE:
            self._notice = "Chỉ xóa ảnh khi đang chụp"
            return [Effect.WARN]
        return [Effect.DELETE_LAST]

    def _open_search_recent(self) -> list[Effect]:
        if self._phase not in (Phase.INTAKE, Phase.READY):
            self._notice = "Chỉ tìm hồ sơ khi đang nhập liệu"
            return [Effect.WARN]
        self._search = SearchView(open=True, mode=SearchMode.RECENT, filter=SearchFilterEdit())
        return [Effect.OPEN_SEARCH_GRID]

    def _on_barcode(self, code: str) -> list[Effect]:
        code = (code or "").strip()
        if not code:
            return []
        if self._phase == Phase.STANDBY:
            self._notice = "Mở phiên (F1) trước khi quét mã"
            return [Effect.WARN]
        if self._phase in (Phase.LOCKED_CAPTURE, Phase.CORRECTION):
            if self._demo.patient_id and code != self._demo.patient_id:
                self._notice = (
                    f"Đang khám [{self._demo.patient_id}] — bỏ qua mã [{code}]. "
                    "F4 rồi F1 để đổi BN"
                )
                return [Effect.WARN]
            self._notice = "Mã trùng BN đang khám"
            return []
        # Intake / Ready → search filter exact id
        filt = SearchFilterEdit(patient_id=code)
        self._search = SearchView(open=True, mode=SearchMode.FILTERED, filter=filt)
        return [Effect.OPEN_SEARCH_GRID]

    def _on_ui_field(self, event: UiFieldEdit) -> list[Effect]:
        if self._phase == Phase.STANDBY:
            self._notice = "Chưa mở phiên"
            return [Effect.WARN]
        if self._phase == Phase.LOCKED_CAPTURE:
            self._notice = "Hồ sơ đang khóa"
            return [Effect.WARN]
        if self._phase == Phase.CORRECTION:
            if event.field not in self._correction_fields:
                self._notice = "Field chưa được mở khóa"
                return [Effect.WARN]
            if event.field == Field.PATIENT_ID:
                self._notice = "Không đổi Mã BN trong Correction"
                return [Effect.WARN]
            self._apply_field(event.field, event.value)
            remaining = self._correction_fields - {event.field}
            self._correction_fields = remaining
            if not remaining:
                self._phase = Phase.LOCKED_CAPTURE
            return []
        # Intake / Ready
        self._apply_field(event.field, event.value)
        self._refresh_phase_after_demo()
        return []

    def _apply_field(self, f: Field, value: object) -> None:
        if f == Field.PATIENT_ID:
            self._demo = replace(self._demo, patient_id=_clean_str(value))
        elif f == Field.FULL_NAME:
            self._demo = replace(self._demo, full_name=_clean_str(value))
        elif f == Field.BIRTH_YEAR:
            if value is None or value == "":
                year = None
            else:
                year = int(value)
            self._demo = replace(self._demo, birth_year=year)
        elif f == Field.GENDER:
            self._demo = replace(self._demo, gender=_clean_str(value))

    def _on_unlock(self, fields: FrozenSet[Field]) -> list[Effect]:
        if self._phase != Phase.LOCKED_CAPTURE:
            self._notice = "Chỉ mở khóa khi đang Locked Capture"
            return [Effect.WARN]
        allowed = frozenset(fields) - {Field.PATIENT_ID}
        if not allowed:
            self._notice = "Không mở khóa Mã BN"
            return [Effect.WARN]
        self._correction_fields = allowed
        self._phase = Phase.CORRECTION
        return []

    def _on_load_record(self, demo: Demography) -> list[Effect]:
        if self._phase not in (Phase.INTAKE, Phase.READY):
            self._notice = "Không nạp hồ sơ khi đang chụp / Standby"
            return [Effect.WARN]
        self._demo = demo
        self._search = SearchView()
        self._refresh_phase_after_demo()
        self._notice = f"Đã nạp hồ sơ {demo.patient_id or ''}".strip()
        return [Effect.CLOSE_SEARCH_GRID]

    def _on_search_filter(self, filt: SearchFilterEdit) -> list[Effect]:
        if not self._search.open or self._phase not in (Phase.INTAKE, Phase.READY):
            self._notice = "Lưới tìm chưa mở"
            return [Effect.WARN]
        mode = SearchMode.FILTERED
        if filt.result_count == 0 and filt.patient_id:
            mode = SearchMode.EMPTY_NEW_PATIENT_PROMPT
        elif not any([filt.patient_id, filt.full_name, filt.birth_year, filt.gender]):
            mode = SearchMode.RECENT
        self._search = SearchView(open=True, mode=mode, filter=filt)
        return [Effect.REFRESH_SEARCH_RESULTS]

    def _on_confirm_new_patient(self) -> list[Effect]:
        if not self._search.open or self._phase not in (Phase.INTAKE, Phase.READY):
            self._notice = "Không thể tạo BN mới lúc này"
            return [Effect.WARN]
        pid = (self._search.filter.patient_id or "").strip()
        if not pid:
            self._notice = "Chưa có mã để tạo BN mới"
            return [Effect.WARN]
        # Prefer empty-prompt mode; also allow when shell reported 0 hits
        if (
            self._search.mode != SearchMode.EMPTY_NEW_PATIENT_PROMPT
            and self._search.filter.result_count not in (0, None)
        ):
            self._notice = "Chỉ tạo BN mới khi không có hồ sơ trùng"
            return [Effect.WARN]
        self._demo = Demography(patient_id=pid)
        self._search = SearchView()
        self._refresh_phase_after_demo()
        return [Effect.CLOSE_SEARCH_GRID]

    def _on_close_search(self) -> list[Effect]:
        if not self._search.open:
            return []
        self._search = SearchView()
        return [Effect.CLOSE_SEARCH_GRID]

    def _on_voice(self, text: str) -> list[Effect]:
        raw = (text or "").strip()
        if not raw:
            return []
        lower = raw.lower()

        # Search overlay: only search-filter related intents
        if self._search.open:
            intent = self._match_lexicon(lower)
            if intent == "close_search":
                return self._on_close_search()
            if intent == "confirm_new_patient":
                return self._on_confirm_new_patient()
            # pattern demography into search filter (name / year / gender) — never invent patient_id from loose speech
            filt = self._search.filter
            updated = False
            name = _extract_name(lower)
            if name:
                filt = replace(filt, full_name=name)
                updated = True
            year = _extract_birth_year(lower)
            if year is not None:
                filt = replace(filt, birth_year=str(year))
                updated = True
            gender = _extract_gender(lower)
            if gender:
                filt = replace(filt, gender=gender)
                updated = True
            if updated:
                return self._on_search_filter(filt)
            return []

        if self._phase == Phase.STANDBY:
            intent = self._match_lexicon(lower)
            if intent == "start_session":
                return self._start_session()
            return []

        intent = self._match_lexicon(lower)
        if intent == "start_session" and self._phase == Phase.STANDBY:
            return self._start_session()
        if intent == "end_session" and self._phase != Phase.STANDBY:
            return self._end_session()
        if intent == "begin_capture":
            return self._begin_capture()
        if intent == "capture":
            return self._on_capture_request()
        if intent == "delete_last":
            return self._on_delete_request()
        if intent == "open_search":
            return self._open_search_recent()
        if intent == "unlock_name":
            return self._on_unlock(frozenset({Field.FULL_NAME}))
        if intent == "unlock_birth_year":
            return self._on_unlock(frozenset({Field.BIRTH_YEAR}))
        if intent == "unlock_gender":
            return self._on_unlock(frozenset({Field.GENDER}))
        if intent == "unlock_profile":
            return self._on_unlock(
                frozenset({Field.FULL_NAME, Field.BIRTH_YEAR, Field.GENDER})
            )

        # Intake / Ready / Correction demography patterns — never patient_id
        if self._phase in (Phase.INTAKE, Phase.READY, Phase.CORRECTION):
            return self._voice_demography_patterns(lower)
        return []

    def _match_lexicon(self, lower: str) -> Optional[str]:
        # longest phrase first
        for phrase, intent in sorted(self._lexicon.items(), key=lambda kv: -len(kv[0])):
            if phrase in lower:
                return intent
        return None

    def _voice_demography_patterns(self, lower: str) -> list[Effect]:
        # Explicitly ignore patient id phrasing
        if "mã" in lower and ("bệnh" in lower or "bn" in lower or "phiếu" in lower):
            return []

        editable = self._build_view().affordances.editable
        effects: list[Effect] = []

        name = _extract_name(lower)
        if name and Field.FULL_NAME in editable:
            effects.extend(self._on_ui_field(UiFieldEdit(Field.FULL_NAME, name)))
        year = _extract_birth_year(lower)
        if year is not None and Field.BIRTH_YEAR in editable:
            effects.extend(self._on_ui_field(UiFieldEdit(Field.BIRTH_YEAR, year)))
        gender = _extract_gender(lower)
        if gender and Field.GENDER in editable:
            effects.extend(self._on_ui_field(UiFieldEdit(Field.GENDER, gender)))
        return effects


def _extract_name(lower: str) -> Optional[str]:
    for prefix in ("họ và tên ", "họ tên ", "tên "):
        if prefix in lower:
            return lower.split(prefix, 1)[1].strip().title() or None
    return None


def _extract_birth_year(lower: str) -> Optional[int]:
    import re

    m = re.search(r"năm sinh\s+(\d{4})", lower)
    if m:
        return int(m.group(1))
    # spoken digits not handled in skeleton
    return None


def _extract_gender(lower: str) -> Optional[str]:
    if "giới tính" in lower:
        if "nữ" in lower:
            return "Nữ"
        if "nam" in lower:
            return "Nam"
    return None


def _clean_str(value: object) -> Optional[str]:
    """Coerce field values; never turn Python None into the literal string 'None'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text
