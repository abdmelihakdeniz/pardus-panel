import time
from dataclasses import dataclass

import psutil


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    total: int
    used: int
    percent: float


@dataclass(frozen=True, slots=True)
class DiskSnapshot:
    device: str
    mountpoint: str
    total: int
    used: int
    percent: float


@dataclass(frozen=True, slots=True)
class NetworkSnapshot:
    sent_total: int
    received_total: int
    upload_rate: float | None
    download_rate: float | None
    packets_sent: int
    packets_received: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    cpu_total: float
    cpu_cores: tuple[float, ...]
    memory: MemorySnapshot
    disks: tuple[DiskSnapshot, ...]
    network: NetworkSnapshot
    temperature_celsius: float | None
    frequency_mhz: float | None


class PerformanceCollector:
    def __init__(self) -> None:
        self._network_sample: tuple[float, int, int] | None = None

    def collect(self) -> PerformanceSnapshot:
        timestamp = time.monotonic()
        core_values = tuple(
            self._clamp_percent(value)
            for value in psutil.cpu_percent(interval=0.1, percpu=True)
        )
        cpu_total = (
            sum(core_values) / len(core_values)
            if core_values
            else self._clamp_percent(psutil.cpu_percent(interval=None))
        )

        memory_raw = psutil.virtual_memory()
        memory = MemorySnapshot(
            total=max(0, int(memory_raw.total)),
            used=max(0, int(memory_raw.used)),
            percent=self._clamp_percent(memory_raw.percent),
        )

        network_raw = psutil.net_io_counters()
        sent = int(network_raw.bytes_sent)
        received = int(network_raw.bytes_recv)
        upload, download = self._network_rates(timestamp, sent, received)
        network = NetworkSnapshot(
            sent_total=max(0, sent),
            received_total=max(0, received),
            upload_rate=upload,
            download_rate=download,
            packets_sent=max(0, int(network_raw.packets_sent)),
            packets_received=max(0, int(network_raw.packets_recv)),
            errors_in=max(0, int(network_raw.errin)),
            errors_out=max(0, int(network_raw.errout)),
            drops_in=max(0, int(network_raw.dropin)),
            drops_out=max(0, int(network_raw.dropout)),
        )

        return PerformanceSnapshot(
            cpu_total=self._clamp_percent(cpu_total),
            cpu_cores=core_values,
            memory=memory,
            disks=self._collect_disks(),
            network=network,
            temperature_celsius=self._collect_temperature(),
            frequency_mhz=self._collect_frequency(),
        )

    def _collect_disks(self) -> tuple[DiskSnapshot, ...]:
        disks: list[DiskSnapshot] = []
        try:
            partitions = psutil.disk_partitions(all=False)
        except OSError:
            return ()
        for part in partitions:
            if not part.fstype or not part.device.startswith("/dev/"):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            disks.append(
                DiskSnapshot(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    total=max(0, int(usage.total)),
                    used=max(0, int(usage.used)),
                    percent=self._clamp_percent(usage.percent),
                )
            )
        return tuple(disks)

    def _collect_temperature(self) -> float | None:
        try:
            groups = psutil.sensors_temperatures()
        except (AttributeError, OSError, RuntimeError):
            return None
        for entries in groups.values():
            for entry in entries:
                current = getattr(entry, "current", None)
                try:
                    current = float(current)
                except (TypeError, ValueError):
                    continue
                if -50.0 <= current <= 200.0:
                    return current
        return None

    def _collect_frequency(self) -> float | None:
        try:
            frequency = psutil.cpu_freq()
        except (AttributeError, OSError, RuntimeError):
            return None
        if frequency is None or frequency.current <= 0:
            return None
        return float(frequency.current)

    def _network_rates(
        self,
        timestamp: float,
        sent: int,
        received: int,
    ) -> tuple[float | None, float | None]:
        previous = self._network_sample
        self._network_sample = timestamp, sent, received
        if previous is None:
            return None, None
        previous_time, previous_sent, previous_received = previous
        elapsed = timestamp - previous_time
        sent_delta = sent - previous_sent
        received_delta = received - previous_received
        if elapsed <= 1e-9 or sent_delta < 0 or received_delta < 0:
            return None, None
        return sent_delta / elapsed, received_delta / elapsed

    @staticmethod
    def _clamp_percent(value: float) -> float:
        return min(100.0, max(0.0, float(value)))
