import configparser
from pathlib import Path

from pardus_panel.features.autostart.entities import AutostartEntry, AutostartSource

SECTION = "Desktop Entry"
KNOWN_FIELDS = {"Type", "Name", "Exec", "Hidden", "NoDisplay"}


class DesktopEntryError(ValueError):
    pass


def parse_desktop_entry(
    text: str,
    *,
    path: Path,
    source: AutostartSource,
) -> AutostartEntry:
    if "\x00" in text:
        raise DesktopEntryError("Null byte is not allowed")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read_string(text)
    except configparser.Error as error:
        raise DesktopEntryError("Invalid desktop entry") from error
    if not parser.has_section(SECTION):
        raise DesktopEntryError("Desktop Entry section is missing")
    values = parser[SECTION]
    if values.get("Type", "Application") != "Application":
        raise DesktopEntryError("Only Application type is supported")
    name = _required(values.get("Name"), "Name")
    command = _required(values.get("Exec"), "Exec")
    hidden = _boolean(values.get("Hidden"))
    no_display = _boolean(values.get("NoDisplay"))
    extras = tuple(
        (key, value) for key, value in values.items() if key not in KNOWN_FIELDS
    )
    return AutostartEntry(
        basename=path.name,
        path=path,
        source=source,
        name=name,
        command=command,
        hidden=hidden,
        no_display=no_display,
        extra_fields=extras,
    )


def serialize_desktop_entry(entry: AutostartEntry) -> str:
    name = _required(entry.name, "Name")
    command = _required(entry.command, "Exec")
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={command}",
        f"Hidden={'true' if entry.hidden else 'false'}",
        f"NoDisplay={'true' if entry.no_display else 'false'}",
    ]
    for key, value in entry.extra_fields:
        if key not in KNOWN_FIELDS and _safe_field(key) and _safe_field(value):
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _required(value: str | None, field: str) -> str:
    clean = (value or "").strip()
    if not clean or not _safe_field(clean):
        raise DesktopEntryError(f"{field} is invalid")
    return clean


def _safe_field(value: str) -> bool:
    return "\x00" not in value and "\n" not in value and "\r" not in value


def _boolean(value: str | None) -> bool:
    if value is None:
        return False
    lowered = value.strip().casefold()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    raise DesktopEntryError("Invalid boolean value")
