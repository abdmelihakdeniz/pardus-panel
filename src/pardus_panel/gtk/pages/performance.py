import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.formatting import format_bytes
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.performance.collector import (
    DiskSnapshot,
    PerformanceCollector,
    PerformanceSnapshot,
)
from pardus_panel.gtk.builder import Builder
from pardus_panel.gtk.widgets.live_graph import LiveGraph, MultiSeriesGraph
from pardus_panel.i18n import _

CPU_COLOR = (0.35, 0.58, 0.95)
MEMORY_COLOR = (0.30, 0.72, 0.45)
CORE_COLORS = (
    (0.35, 0.58, 0.95),
    (0.95, 0.45, 0.30),
    (0.30, 0.72, 0.45),
    (0.70, 0.45, 0.90),
    (0.95, 0.70, 0.25),
    (0.25, 0.75, 0.75),
    (0.95, 0.40, 0.65),
    (0.65, 0.75, 0.25),
    (0.55, 0.65, 0.95),
    (0.85, 0.55, 0.30),
    (0.40, 0.85, 0.60),
    (0.85, 0.35, 0.35),
    (0.45, 0.65, 0.85),
    (0.75, 0.50, 0.75),
    (0.55, 0.80, 0.80),
    (0.90, 0.65, 0.75),
)


class PerformancePage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._collector = PerformanceCollector()
        self._scope = LifecycleScope()
        self._timer_id: int | None = None
        self._active = False
        self._builder = Builder("Performance.ui")
        required = self._builder.get_required
        self.root = required("performance_content", Gtk.Box)
        self._cpu_value = required("performance_cpu_value", Gtk.Label)
        self._core_cards = required("performance_core_cards", Gtk.FlowBox)
        self._core_widgets: list[tuple[Gtk.Label, LiveGraph]] = []
        self._memory_value = required("performance_memory_value", Gtk.Label)
        self._memory_detail = required("performance_memory_detail", Gtk.Label)
        self._disk_cards = required("performance_disk_cards", Gtk.FlowBox)
        self._upload = required("performance_upload_value", Gtk.Label)
        self._download = required("performance_download_value", Gtk.Label)
        self._sent_total = required("performance_sent_total", Gtk.Label)
        self._received_total = required("performance_received_total", Gtk.Label)
        self._packets = required("performance_packets", Gtk.Label)
        self._errors = required("performance_errors", Gtk.Label)
        self._drops = required("performance_drops", Gtk.Label)
        self._temperature = required("performance_temperature_value", Gtk.Label)
        self._frequency = required("performance_frequency_value", Gtk.Label)
        self._status = required("performance_status", Gtk.Label)
        self._scroller = required("performance_scroller", Gtk.ScrolledWindow)
        self._sections = (
            (
                required("performance_cpu_nav", Gtk.ToggleButton),
                required("performance_cpu_section", Gtk.Box),
            ),
            (
                required("performance_memory_nav", Gtk.ToggleButton),
                required("performance_memory_section", Gtk.Box),
            ),
            (
                required("performance_disk_nav", Gtk.ToggleButton),
                required("performance_disk_section", Gtk.Box),
            ),
            (
                required("performance_network_nav", Gtk.ToggleButton),
                required("performance_network_section", Gtk.Box),
            ),
        )
        self._syncing_nav = False
        self._build_section_nav()
        self._cpu_graph = LiveGraph(color=CPU_COLOR)
        self._memory_graph = LiveGraph(color=MEMORY_COLOR)
        self._network_graph = MultiSeriesGraph(
            minimum_scale=1024.0,
            colors=(MEMORY_COLOR, CPU_COLOR),
        )
        required("performance_cpu_graph", Gtk.Box).pack_start(
            self._cpu_graph, True, True, 0
        )
        required("performance_memory_graph", Gtk.Box).pack_start(
            self._memory_graph, True, True, 0
        )
        network_graph = required("performance_network_graph", Gtk.Overlay)
        network_graph.add(self._network_graph)
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=self._collector.collect,
            on_result=self._show_snapshot,
            on_error=self._show_error,
        )

    def dispose(self) -> None:
        self.set_active(False)
        self._refresh.dispose()
        self._scope.cleanup()

    def set_active(self, active: bool) -> None:
        if self._scope.disposed or active == self._active:
            return
        self._active = active
        if active:
            self._timer_id = GLib.timeout_add(2_000, self._on_timer)
            self._refresh.request()
        elif self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _on_timer(self) -> bool:
        if not self._active or self._scope.disposed:
            self._timer_id = None
            return GLib.SOURCE_REMOVE
        self._refresh.request()
        return GLib.SOURCE_CONTINUE

    def _build_section_nav(self) -> None:
        for index, (button, _section) in enumerate(self._sections):
            self._scope.connect(button, "clicked", self._on_nav_clicked, index)
        adjustment = self._scroller.get_vadjustment()
        self._scope.connect(adjustment, "value-changed", self._on_scroll_changed)
        self._set_active_section(0)

    def _on_nav_clicked(self, button: Gtk.ToggleButton, index: int) -> None:
        if self._syncing_nav or not button.get_active():
            return
        adjustment = self._scroller.get_vadjustment()
        section_y = self._sections[index][1].get_allocation().y
        maximum = max(
            adjustment.get_lower(),
            adjustment.get_upper() - adjustment.get_page_size(),
        )
        adjustment.set_value(min(float(section_y), maximum))

    def _on_scroll_changed(self, adjustment: Gtk.Adjustment) -> None:
        value = adjustment.get_value()
        maximum = max(
            adjustment.get_lower(),
            adjustment.get_upper() - adjustment.get_page_size(),
        )
        if value >= maximum - 1.0:
            self._set_active_section(len(self._sections) - 1)
            return
        active = 0
        for index, (_button, section) in enumerate(self._sections):
            if section.get_allocation().y <= value + 40:
                active = index
        self._set_active_section(active)

    def _set_active_section(self, active: int) -> None:
        self._syncing_nav = True
        try:
            for index, (button, _section) in enumerate(self._sections):
                button.set_active(index == active)
        finally:
            self._syncing_nav = False

    def _show_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        memory = snapshot.memory
        network = snapshot.network
        self._cpu_value.set_text(f"{snapshot.cpu_total:.1f}%")
        self._memory_value.set_text(f"{memory.percent:.1f}%")
        self._memory_detail.set_text(
            f"{format_bytes(memory.used)} / {format_bytes(memory.total)}"
        )
        self._upload.set_text(_format_rate(network.upload_rate))
        self._download.set_text(_format_rate(network.download_rate))
        self._sent_total.set_text(format_bytes(network.sent_total))
        self._received_total.set_text(format_bytes(network.received_total))
        self._packets.set_text(f"{network.packets_received} / {network.packets_sent}")
        self._errors.set_text(f"{network.errors_in} / {network.errors_out}")
        self._drops.set_text(f"{network.drops_in} / {network.drops_out}")
        self._temperature.set_text(
            f"{snapshot.temperature_celsius:.1f} °C"
            if snapshot.temperature_celsius is not None
            else _("Unavailable")
        )
        self._frequency.set_text(
            f"{snapshot.frequency_mhz:.0f} MHz"
            if snapshot.frequency_mhz is not None
            else _("Unavailable")
        )
        self._status.set_text("")
        self._cpu_graph.append(snapshot.cpu_total)
        self._memory_graph.append(memory.percent)
        self._network_graph.append(
            network.upload_rate or 0.0,
            network.download_rate or 0.0,
        )
        self._replace_cores(snapshot.cpu_cores)
        self._replace_disks(snapshot.disks)

    def _replace_cores(self, values: tuple[float, ...]) -> None:
        if not values:
            if self._core_widgets or not self._core_cards.get_children():
                self._core_widgets = []
                _replace_cards(self._core_cards, [_message_card(_("No CPU core data"))])
            return
        if len(self._core_widgets) != len(values):
            cards = []
            self._core_widgets = []
            for index in range(len(values)):
                card, percent, graph = _core_card(
                    _("Core {number}").format(number=index + 1),
                    CORE_COLORS[index % len(CORE_COLORS)],
                )
                cards.append(card)
                self._core_widgets.append((percent, graph))
            _replace_cards(self._core_cards, cards)
        for (percent, graph), value in zip(self._core_widgets, values):
            percent.set_text(f"{value:.1f}%")
            graph.append(value)

    def _replace_disks(self, disks: tuple[DiskSnapshot, ...]) -> None:
        cards = (
            [
                _usage_card(
                    disk.mountpoint,
                    f"{disk.device}\n"
                    f"{format_bytes(disk.used)} / {format_bytes(disk.total)}",
                    disk.percent,
                )
                for disk in disks
            ]
            if disks
            else [_message_card(_("No physical disks found"))]
        )
        _replace_cards(self._disk_cards, cards)

    def _show_error(self, error: BaseException) -> None:
        self._status.set_text(_("Could not refresh: {error}").format(error=error))


def _usage_card(
    name: str,
    detail: str,
    percent: float,
) -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.get_style_context().add_class("performance-resource-card")

    header = Gtk.Box(spacing=8)
    name_label = Gtk.Label(label=name, xalign=0)
    name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    name_label.get_style_context().add_class("performance-resource-name")
    percent_label = Gtk.Label(label=f"{percent:.1f}%")
    percent_label.get_style_context().add_class("performance-resource-percent")
    header.pack_start(name_label, True, True, 0)
    header.pack_end(percent_label, False, False, 0)

    detail_label = Gtk.Label(label=detail, xalign=0)
    detail_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    detail_label.get_style_context().add_class("muted-label")
    progress = Gtk.ProgressBar()
    progress.set_fraction(min(100.0, max(0.0, percent)) / 100.0)

    card.pack_start(header, False, False, 0)
    card.pack_start(detail_label, False, False, 0)
    card.pack_start(progress, False, False, 0)
    return card


def _core_card(
    name: str,
    color: tuple[float, float, float],
) -> tuple[Gtk.Box, Gtk.Label, LiveGraph]:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.get_style_context().add_class("performance-resource-card")

    header = Gtk.Box(spacing=8)
    name_label = Gtk.Label(label=name, xalign=0)
    name_label.get_style_context().add_class("performance-resource-name")
    percent = Gtk.Label(label="—")
    percent.get_style_context().add_class("performance-resource-percent")
    header.pack_start(name_label, True, True, 0)
    header.pack_end(percent, False, False, 0)

    graph = LiveGraph(color=color)
    graph.get_style_context().add_class("performance-core-graph")
    card.pack_start(header, False, False, 0)
    card.pack_start(graph, True, True, 0)
    return card, percent, graph


def _message_card(message: str) -> Gtk.Box:
    card = Gtk.Box()
    card.get_style_context().add_class("performance-resource-card")
    card.pack_start(Gtk.Label(label=message, xalign=0), True, True, 0)
    return card


def _replace_cards(flowbox: Gtk.FlowBox, cards: list[Gtk.Box]) -> None:
    for child in flowbox.get_children():
        flowbox.remove(child)
    for card in cards:
        flowbox.add(card)
    flowbox.show_all()


def _format_rate(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return _("Calculating…")
    return f"{format_bytes(value)}/s"
