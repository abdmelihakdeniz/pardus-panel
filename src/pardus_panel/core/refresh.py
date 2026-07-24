from collections.abc import Callable
from typing import Any

from pardus_panel.core.async_jobs import AsyncJobRunner


class RefreshCoordinator:
    def __init__(
        self,
        *,
        jobs: AsyncJobRunner,
        work: Callable[[], Any],
        on_result: Callable[[Any], object],
        on_error: Callable[[BaseException], object],
    ) -> None:
        self._jobs = jobs
        self._work = work
        self._on_result = on_result
        self._on_error = on_error
        self._running = False
        self._pending = False
        self._disposed = False

    def request(self) -> None:
        if self._disposed:
            return
        if self._running:
            self._pending = True
            return
        self._start()

    def dispose(self) -> None:
        self._disposed = True

    def _start(self) -> None:
        self._running = True
        self._jobs.submit(
            self._work,
            on_success=lambda value: self._finish(self._on_result, value),
            on_error=lambda error: self._finish(self._on_error, error),
        )

    def _finish(self, callback: Callable[[Any], object], value: Any) -> None:
        if self._disposed:
            return
        pending = self._pending
        self._pending = False
        self._running = False
        callback(value)
        if pending and not self._running:
            self._start()
