import logging
from collections.abc import Callable
from typing import Any

LOGGER = logging.getLogger(__name__)


class LifecycleScope:
    def __init__(self) -> None:
        self._connections: list[tuple[Any, int]] = []
        self._disposed = False

    @property
    def disposed(self) -> bool:
        return self._disposed

    def connect(
        self,
        owner: Any,
        signal: str,
        callback: Callable[..., object],
        *args: object,
    ) -> None:
        if self._disposed:
            raise RuntimeError("Cannot register signals on a disposed scope")
        handler_id = owner.connect(signal, callback, *args)
        self._connections.append((owner, handler_id))

    def cleanup(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        while self._connections:
            owner, handler_id = self._connections.pop()
            try:
                if owner.handler_is_connected(handler_id):
                    owner.disconnect(handler_id)
            except Exception:
                LOGGER.exception("Could not disconnect signal")
