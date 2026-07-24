from dataclasses import dataclass

import psutil

FIELDS = (
    "pid",
    "create_time",
    "name",
    "username",
    "cpu_percent",
    "memory_info",
    "status",
)


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    pid: int
    create_time: float
    name: str
    username: str | None
    cpu_percent: float
    memory_bytes: int
    status: str | None


def list_processes() -> tuple[ProcessSnapshot, ...]:
    rows: list[ProcessSnapshot] = []
    cpu_count = psutil.cpu_count() or 1
    for process in psutil.process_iter(attrs=FIELDS, ad_value=None):
        try:
            info = process.info
            pid = int(info["pid"])
            create_time = float(info["create_time"])
            memory_info = info.get("memory_info")
            memory_bytes = int(memory_info.rss) if memory_info is not None else 0
            rows.append(
                ProcessSnapshot(
                    pid=pid,
                    create_time=create_time,
                    name=str(info.get("name") or f"PID {pid}"),
                    username=info.get("username"),
                    cpu_percent=min(
                        100.0,
                        max(
                            0.0,
                            float(info.get("cpu_percent") or 0.0) / cpu_count,
                        ),
                    ),
                    memory_bytes=max(0, memory_bytes),
                    status=info.get("status"),
                )
            )
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            continue
    return tuple(rows)
