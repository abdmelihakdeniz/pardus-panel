import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from pardus_panel.features.autostart.entities import AutostartEntry, AutostartSource
from pardus_panel.features.autostart.parser import (
    DesktopEntryError,
    parse_desktop_entry,
    serialize_desktop_entry,
)


class AutostartRepository:
    def __init__(self) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", ""))
        self.config_home = (
            config_home if config_home.is_absolute() else Path.home() / ".config"
        )
        raw_dirs = os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg"
        self.config_dirs = tuple(
            path
            for value in raw_dirs.split(":")
            if value and (path := Path(value)).is_absolute()
        )

    @property
    def user_dir(self) -> Path:
        return self.config_home / "autostart"

    def list_entries(self) -> tuple[AutostartEntry, ...]:
        found: list[AutostartEntry] = []
        seen: set[str] = set()
        locations = ((self.user_dir, AutostartSource.USER),) + tuple(
            (directory / "autostart", AutostartSource.SYSTEM)
            for directory in self.config_dirs
        )
        for directory, source in locations:
            try:
                paths = sorted(directory.glob("*.desktop"))
            except OSError:
                continue
            for path in paths:
                if path.name in seen:
                    continue
                # A broken user file must still mask the system entry.
                seen.add(path.name)
                try:
                    text = path.read_text(encoding="utf-8")
                    found.append(parse_desktop_entry(text, path=path, source=source))
                except (OSError, UnicodeError, DesktopEntryError):
                    continue
        return tuple(
            sorted(found, key=lambda entry: (entry.name.casefold(), entry.basename))
        )

    def create(self, *, name: str, command: str) -> AutostartEntry:
        user_dir = self._prepare_user_dir()
        base = self._slug(name)
        path = user_dir / f"{base}.desktop"
        suffix = 2
        while path.exists():
            path = user_dir / f"{base}-{suffix}.desktop"
            suffix += 1
        entry = AutostartEntry(
            basename=path.name,
            path=path,
            source=AutostartSource.USER,
            name=name,
            command=command,
            hidden=False,
            no_display=False,
        )
        self._write(entry)
        return entry

    def set_enabled(self, entry: AutostartEntry, *, enabled: bool) -> AutostartEntry:
        user_dir = self._prepare_user_dir()
        path = (
            entry.path
            if entry.source is AutostartSource.USER
            else user_dir / entry.basename
        )
        changed = replace(
            entry,
            path=path,
            source=AutostartSource.USER,
            hidden=not enabled,
        )
        self._write(changed)
        return changed

    def delete(self, entry: AutostartEntry) -> None:
        if entry.source is not AutostartSource.USER:
            raise PermissionError("System autostart entry cannot be deleted")
        path = entry.path.resolve()
        if path.parent != self.user_dir.resolve():
            raise PermissionError("Entry is outside user autostart directory")
        path.unlink(missing_ok=True)

    def _write(self, entry: AutostartEntry) -> None:
        user_dir = self._prepare_user_dir()
        target = entry.path.resolve()
        if target.parent != user_dir.resolve():
            raise PermissionError("Write is outside user autostart directory")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pardus-", dir=user_dir)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(serialize_desktop_entry(entry))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _prepare_user_dir(self) -> Path:
        self.user_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self.user_dir

    @staticmethod
    def _slug(name: str) -> str:
        clean = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        return clean[:64] or "autostart-entry"
