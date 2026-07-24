from dataclasses import dataclass
from enum import Enum

from pardus_panel.core.command import CommandError, run_command

ALLOWED_ACTIONS = frozenset({"start", "stop", "restart", "enable", "disable"})
UNIT_CHARACTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@_.:-\\"


class ServiceScope(str, Enum):
    SYSTEM = "system"
    USER = "user"


@dataclass(frozen=True, slots=True)
class ServiceEntry:
    scope: ServiceScope
    unit: str
    description: str
    active: str
    sub: str
    enabled: str


def list_services() -> tuple[ServiceEntry, ...]:
    entries: list[ServiceEntry] = []
    first_error: CommandError | None = None
    for scope in ServiceScope:
        try:
            states = {
                unit: (description, active, sub)
                for unit, description, active, sub in _read_states(scope)
            }
            enabled = _read_enabled(scope)
        except CommandError as error:
            first_error = first_error or error
            continue
        for unit in states.keys() | enabled:
            description, active, sub = states.get(unit, ("", "inactive", "dead"))
            entries.append(
                ServiceEntry(
                    scope=scope,
                    unit=unit,
                    description=description,
                    active=active,
                    sub=sub,
                    enabled=enabled.get(unit, "unknown"),
                )
            )
    if not entries and first_error:
        raise first_error
    return tuple(
        sorted(entries, key=lambda item: (item.unit.casefold(), item.scope.value))
    )


def _read_states(scope: ServiceScope) -> tuple[tuple[str, str, str, str], ...]:
    output = run_command(
        scope_command(
            scope,
            "list-units",
            "--type=service",
            "--all",
            "--no-legend",
            "--no-pager",
            "--plain",
        )
    )
    rows = []
    for line in output.splitlines():
        parts = line.strip().removeprefix("● ").lstrip().split(None, 4)
        if len(parts) != 5 or not valid_unit(parts[0]):
            continue
        unit, _load, active, sub, description = parts
        rows.append((unit, description, active, sub))
    return tuple(rows)


def _read_enabled(scope: ServiceScope) -> dict[str, str]:
    output = run_command(
        scope_command(
            scope,
            "list-unit-files",
            "--type=service",
            "--no-legend",
            "--no-pager",
        )
    )
    values = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and valid_unit(parts[0]):
            values[parts[0]] = parts[1]
    return values


def apply_service_action(*, scope: ServiceScope, unit: str, action: str) -> None:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Service action is not allowed")
    if not valid_unit(unit):
        raise ValueError("Service unit is invalid")
    command = scope_command(scope, action, "--", unit)
    if scope is ServiceScope.SYSTEM:
        command = ["/usr/bin/pkexec", "/bin/systemctl", *command[1:]]
    run_command(command, timeout=60.0)


def valid_unit(unit: str) -> bool:
    if unit == ".service" or not unit.endswith(".service") or len(unit) > 256:
        return False
    return all(character in UNIT_CHARACTERS for character in unit)


def scope_command(scope: ServiceScope, *arguments: str) -> list[str]:
    command = ["systemctl"]
    if scope is ServiceScope.USER:
        command.append("--user")
    command.extend(arguments)
    return command
