from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AutostartSource(str, Enum):
    USER = "user"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class AutostartEntry:
    path: Path
    source: AutostartSource
    name: str
    command: str
    hidden: bool
