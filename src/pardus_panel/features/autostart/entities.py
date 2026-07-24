from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AutostartSource(str, Enum):
    USER = "user"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class AutostartEntry:
    basename: str
    path: Path
    source: AutostartSource
    name: str
    command: str
    hidden: bool
    no_display: bool
    extra_fields: tuple[tuple[str, str], ...] = ()
