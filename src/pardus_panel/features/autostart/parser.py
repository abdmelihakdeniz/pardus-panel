import configparser
import locale
from pathlib import Path

from pardus_panel.features.autostart.entities import AutostartEntry, AutostartSource

SECTION = "Desktop Entry"


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
    name = _required(_localized(values, "Name"), "Name")
    command = _required(values.get("Exec"), "Exec")
    hidden = _boolean(values.get("Hidden"))
    return AutostartEntry(
        path=path,
        source=source,
        name=name,
        command=command,
        hidden=hidden,
    )


def serialize_desktop_entry(entry: AutostartEntry) -> str:
    name = _escape(_validated(entry.name, "Name"))
    command = _escape(_validated(entry.command, "Exec"))
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={command}",
        f"Hidden={'true' if entry.hidden else 'false'}",
    ]
    return "\n".join(lines) + "\n"


def _required(value: str | None, field: str) -> str:
    clean = (value or "").strip()
    if not clean:
        raise DesktopEntryError(f"{field} is invalid")
    return _validated(_unescape(clean), field)


def _validated(value: str, field: str) -> str:
    if not value.strip() or "\x00" in value:
        raise DesktopEntryError(f"{field} is invalid")
    return value


def _localized(values: configparser.SectionProxy, field: str) -> str | None:
    current = locale.setlocale(locale.LC_MESSAGES)
    base, _, modifier = current.partition("@")
    base = base.partition(".")[0]
    language, separator, country = base.partition("_")
    candidates = []
    if language not in {"C", "POSIX"}:
        if separator and modifier:
            candidates.append(f"{language}_{country}@{modifier}")
        if separator:
            candidates.append(f"{language}_{country}")
        if modifier:
            candidates.append(f"{language}@{modifier}")
        candidates.append(language)
    return next(
        (
            values[key]
            for candidate in candidates
            if (key := f"{field}[{candidate}]") in values
        ),
        values.get(field),
    )


def _unescape(value: str) -> str:
    escapes = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    result = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            result.append(character)
            index += 1
            continue
        index += 1
        if index == len(value) or value[index] not in escapes:
            raise DesktopEntryError("Invalid escape sequence")
        result.append(escapes[value[index]])
        index += 1
    return "".join(result)


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )


def set_hidden(text: str, *, hidden: bool) -> str:
    lines = text.splitlines(keepends=True)
    section_start = next(
        (index for index, line in enumerate(lines) if line.strip() == f"[{SECTION}]"),
        None,
    )
    if section_start is None:
        raise DesktopEntryError("Desktop Entry section is missing")
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(lines))
            if lines[index].lstrip().startswith("[")
        ),
        len(lines),
    )
    replacement = f"Hidden={'true' if hidden else 'false'}"
    found = False
    for index in range(section_start + 1, section_end):
        if lines[index].partition("=")[0].strip() == "Hidden":
            ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
            lines[index] = replacement + ending
            found = True
    if not found:
        ending = "\r\n" if "\r\n" in text else "\n"
        if not lines[section_end - 1].endswith(("\n", "\r")):
            lines[section_end - 1] += ending
        lines.insert(section_end, replacement + ending)
    return "".join(lines)


def _boolean(value: str | None) -> bool:
    if value is None:
        return False
    lowered = value.strip().casefold()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    raise DesktopEntryError("Invalid boolean value")
