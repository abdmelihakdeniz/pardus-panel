import ipaddress
import os
import platform
import socket
from dataclasses import dataclass
from pathlib import Path

import psutil

from pardus_panel.core.command import CommandError, run_command

EFI_PATH = Path("/sys/firmware/efi")


@dataclass(frozen=True, slots=True)
class SystemInfo:
    distro_id: str
    os_name: str
    boot_mode: str
    hostname: str
    desktop_session: str | None
    internal_ips: str | None
    kernel: str
    cpu: str
    memory_bytes: int
    disk_bytes: int
    gpu: str | None


def collect_system_info() -> SystemInfo:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    release = platform.freedesktop_os_release()
    return SystemInfo(
        distro_id=release.get("ID", ""),
        os_name=release.get("PRETTY_NAME") or platform.system(),
        boot_mode=_boot_mode(),
        hostname=platform.node(),
        desktop_session=_desktop_session(),
        internal_ips=_internal_ips(),
        kernel=platform.release(),
        cpu=platform.processor() or _cpu_model() or "",
        memory_bytes=max(0, int(memory.total)),
        disk_bytes=max(0, int(disk.total)),
        gpu=_gpu(),
    )


def _boot_mode() -> str:
    return "uefi" if EFI_PATH.is_dir() else "legacy"


def _desktop_session() -> str | None:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").strip().replace(":", " / ")
    session = os.environ.get("XDG_SESSION_TYPE", "").strip().title()
    return " · ".join(filter(None, (desktop, session))) or None


def _internal_ips() -> str | None:
    addresses = set()
    try:
        interfaces = psutil.net_if_addrs().values()
    except OSError:
        return None
    for entries in interfaces:
        for address in entries:
            if address.family != socket.AF_INET:
                continue
            try:
                value = ipaddress.ip_address(address.address)
            except ValueError:
                continue
            if value.is_private and not value.is_loopback and not value.is_link_local:
                addresses.add(str(value))
    return ", ".join(sorted(addresses)) or None


def _cpu_model() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as source:
            for line in source:
                if line.casefold().startswith("model name"):
                    return line.partition(":")[2].strip() or None
    except OSError:
        return None
    return None


def _gpu() -> str | None:
    try:
        output = run_command(["lspci"])
    except CommandError:
        return None
    for line in output.splitlines():
        lowered = line.casefold()
        if any(
            marker in lowered
            for marker in ("vga compatible", "3d controller", "display controller")
        ):
            return line.partition(": ")[2] or line
    return None
