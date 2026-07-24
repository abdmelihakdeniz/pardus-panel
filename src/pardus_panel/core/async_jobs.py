from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


class AsyncJobRunner:
    def __init__(self, *, dispatch: Callable[..., object]) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="pardus-panel",
        )
        self._dispatch = dispatch

    def submit(
        self,
        work: Callable[[], Any],
        *,
        on_success: Callable[[Any], object],
        on_error: Callable[[BaseException], object],
    ) -> None:
        future = self._executor.submit(work)
        future.add_done_callback(
            lambda completed: self._deliver(completed, on_success, on_error)
        )

    def shutdown(self) -> None:
        self._executor.shutdown(cancel_futures=True)

    def _deliver(
        self,
        future: Future[Any],
        on_success: Callable[[Any], object],
        on_error: Callable[[BaseException], object],
    ) -> None:
        try:
            value = future.result()
        except Exception as exc:
            self._dispatch(on_error, exc)
        else:
            self._dispatch(on_success, value)
