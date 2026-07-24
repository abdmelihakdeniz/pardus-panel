import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pardus_panel.core.command import run_command

SCOPES = frozenset({"system", "user"})
PRIORITIES = frozenset(
    {"all", "emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"}
)


@dataclass(frozen=True, slots=True)
class LogEntry:
    timestamp: datetime | None
    priority: str
    source: str
    message: str


def list_entries(
    *,
    scope: str = "system",
    priority: str = "all",
    limit: int = 300,
    search: str = "",
) -> tuple[LogEntry, ...]:
    if scope not in SCOPES:
        raise ValueError("Log scope is invalid")
    if priority not in PRIORITIES:
        raise ValueError("Log priority is invalid")
    limit = min(1000, max(1, int(limit)))
    command = ["journalctl"]
    if scope == "user":
        command.append("--user")
    command.extend(
        (
            "--output=json",
            "--output-fields=__REALTIME_TIMESTAMP,PRIORITY,SYSLOG_IDENTIFIER,"
            "_SYSTEMD_UNIT,_COMM,MESSAGE",
            "--no-pager",
            "--reverse",
            f"--lines={limit}",
        )
    )
    if priority != "all":
        command.extend(("--priority", priority))
    output = run_command(command)
    needle = search.casefold().strip()
    entries = []
    for line in output.splitlines():
        entry = parse_record(line)
        if entry is None:
            continue
        if not needle or needle in f"{entry.source} {entry.message}".casefold():
            entries.append(entry)
    return tuple(entries)


def parse_record(line: str) -> LogEntry | None:
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(record, dict):
        return None
    message = record.get("MESSAGE", "")
    if isinstance(message, list):
        message = bytes(
            value
            for value in message
            if isinstance(value, int) and 0 <= value <= 255
        )
        message = message.decode("utf-8", errors="replace")
    elif not isinstance(message, str):
        message = str(message) if message is not None else ""
    source = str(
        record.get("SYSLOG_IDENTIFIER")
        or record.get("_SYSTEMD_UNIT")
        or record.get("_COMM")
        or ""
    )
    return LogEntry(
        timestamp=_timestamp(record.get("__REALTIME_TIMESTAMP")),
        priority=str(record.get("PRIORITY", "")),
        source=source,
        message=message.replace("\x00", "�"),
    )


def _timestamp(value: object) -> datetime | None:
    try:
        microseconds = int(str(value))
        return datetime.fromtimestamp(microseconds / 1_000_000, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None
