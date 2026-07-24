from dataclasses import dataclass
from pathlib import Path

import psutil

from pardus_panel.core.command import CommandError, run_command

PROFILES = ("power-saver", "balanced", "performance")
POWER_SUPPLY = Path("/sys/class/power_supply")


@dataclass(frozen=True, slots=True)
class BatterySnapshot:
    status: str
    percent: float | None
    health_percent: float | None
    seconds_left: int | None


@dataclass(frozen=True, slots=True)
class PowerSnapshot:
    battery: BatterySnapshot | None
    profiles: tuple[str, ...]
    active_profile: str | None


def collect_power_info() -> PowerSnapshot:
    profiles, active = _profiles()
    return PowerSnapshot(_battery(), profiles, active)


def _battery() -> BatterySnapshot | None:
    try:
        supplies = sorted(POWER_SUPPLY.iterdir())
    except OSError:
        return None
    for supply in supplies:
        if _read(supply / "type").casefold() != "battery":
            continue
        full = _number(supply, "energy_full", "charge_full")
        design = _number(supply, "energy_full_design", "charge_full_design")
        percent = _number(supply, "capacity")
        if percent is None:
            now = _number(supply, "energy_now", "charge_now")
            percent = now * 100 / full if now is not None and full else None
        health = full * 100 / design if full is not None and design else None
        seconds = None
        try:
            battery = psutil.sensors_battery()
        except (AttributeError, OSError, RuntimeError):
            battery = None
        if battery is not None and battery.secsleft >= 0:
            seconds = int(battery.secsleft)
        return BatterySnapshot(
            _read(supply / "status") or "Unknown",
            _percent(percent),
            _percent(health),
            seconds,
        )
    return None


def _profiles() -> tuple[tuple[str, ...], str | None]:
    try:
        output = run_command(["powerprofilesctl", "list"])
        active = run_command(["powerprofilesctl", "get"]).strip()
    except CommandError:
        return (), None
    profiles = tuple(profile for profile in PROFILES if profile in output)
    return profiles, active if active in profiles else None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _number(supply: Path, *names: str) -> float | None:
    for name in names:
        try:
            return float(_read(supply / name))
        except ValueError:
            continue
    return None


def set_power_profile(profile: str) -> None:
    if profile not in PROFILES:
        raise ValueError(f"Invalid power profile: {profile}")
    run_command(["powerprofilesctl", "set", profile])


def _percent(value: float | None) -> float | None:
    return None if value is None else min(100.0, max(0.0, value))
