from collections.abc import Callable
from typing import Any

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.refresh import RefreshCoordinator


class PeriodicRefreshCoordinator(RefreshCoordinator):
    def __init__(
        self,
        *,
        interval_ms: int,
        jobs: AsyncJobRunner,
        work: Callable[[], Any],
        on_result: Callable[[Any], object],
        on_error: Callable[[BaseException], object],
    ) -> None:
        super().__init__(
            jobs=jobs,
            work=work,
            on_result=on_result,
            on_error=on_error,
        )
        self._interval_ms = interval_ms
        self._timer_id: int | None = None
        self._active = False

    def set_active(self, active: bool) -> None:
        if self.disposed or active == self._active:
            return
        self._active = active
        if active:
            self._timer_id = GLib.timeout_add(self._interval_ms, self._on_timer)
            self.request()
        elif self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def dispose(self) -> None:
        self.set_active(False)
        super().dispose()

    def _on_timer(self) -> bool:
        if not self._active:
            self._timer_id = None
            return GLib.SOURCE_REMOVE
        self.request()
        return GLib.SOURCE_CONTINUE
