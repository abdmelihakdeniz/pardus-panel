import platform
from dataclasses import dataclass

import distro
import psutil

from pardus_panel.core.command import CommandError, run_command


@dataclass(frozen=True, slots=True)
class SystemInfo:
    distro_id: str
    os_name: str
    hostname: str
    kernel: str
    cpu: str
    memory_bytes: int
    disk_bytes: int
    gpu: str | None


def collect_system_info() -> SystemInfo:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return SystemInfo(
        distro_id=distro.id(),
        os_name=distro.name(pretty=True) or platform.system(),
        hostname=platform.node(),
        kernel=platform.release(),
        cpu=platform.processor() or _cpu_model() or "",
        memory_bytes=max(0, int(memory.total)),
        disk_bytes=max(0, int(disk.total)),
        gpu=_gpu(),
    )


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
