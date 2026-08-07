"""Maps PatientSessionController Effect values to injectable UI/hardware hooks."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from src.patient_session_controller import Effect, SessionView


class SessionEffectApplier:
    """Thin adapter: domain effects → MainWindow callbacks (no Qt imports)."""

    def __init__(
        self,
        *,
        on_power_on: Callable[[], None],
        on_power_off: Callable[[], None],
        on_capture: Callable[[], None],
        on_delete_last: Callable[[], None],
        on_open_search: Callable[[SessionView], None],
        on_refresh_search: Callable[[SessionView], None],
        on_close_search: Callable[[], None],
        on_persist_clear: Callable[[], None],
        on_warn: Callable[[SessionView], None],
    ) -> None:
        self._hooks: dict[Effect, Callable[[SessionView], None]] = {
            Effect.POWER_DEVICES_ON: lambda _v: on_power_on(),
            Effect.POWER_DEVICES_OFF: lambda _v: on_power_off(),
            Effect.CAPTURE_FRAME: lambda _v: on_capture(),
            Effect.DELETE_LAST: lambda _v: on_delete_last(),
            Effect.OPEN_SEARCH_GRID: on_open_search,
            Effect.REFRESH_SEARCH_RESULTS: on_refresh_search,
            Effect.CLOSE_SEARCH_GRID: lambda _v: on_close_search(),
            Effect.PERSIST_AND_CLEAR: lambda _v: on_persist_clear(),
            Effect.WARN: on_warn,
        }

    def apply(self, effects: Sequence[Effect], view: SessionView) -> None:
        for fx in effects:
            hook = self._hooks.get(fx)
            if hook is not None:
                hook(view)
