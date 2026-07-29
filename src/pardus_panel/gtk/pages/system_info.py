from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, Pango

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.formatting import format_bytes
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.system_info.collector import SystemInfo, collect_system_info
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

VENDOR_ICON_DIR = Path("/usr/share/icons/vendor/scalable/emblems")
BOOT_MODE_LABELS = {"uefi": _("UEFI"), "legacy": _("Legacy")}
SYSTEM_INFO_FIELDS = (
    ("hostname", _("Hostname")),
    ("os", _("Operating system")),
    ("kernel", _("Kernel")),
    ("desktop", _("Desktop and session")),
    ("cpu", _("Processor")),
    ("gpu", _("Graphics")),
    ("memory", _("Memory")),
    ("disk", _("System disk")),
    ("ip", _("Internal IP addresses")),
)


class SystemInfoPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        builder = Builder("SystemInfo.ui")
        required = builder.get_required
        self.root = required("system_info_content", Gtk.Box)
        self._header_icon = required("system_info_icon", Gtk.Image)
        hostname_list = required("system_info_hostname_list", Gtk.ListBox)
        detail_list = required("system_info_list", Gtk.ListBox)
        self._values = {}
        for index, (name, title) in enumerate(SYSTEM_INFO_FIELDS):
            row, value = _info_row(title)
            (hostname_list if index == 0 else detail_list).add(row)
            self._values[name] = value
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=collect_system_info,
            on_result=self._render,
            on_error=self._show_error,
        )
        self._status = required("system_info_status", Gtk.Label)

    def set_active(self, active: bool) -> None:
        if active:
            self._status.set_text(_("Loading system information…"))
            self._refresh.request()

    def dispose(self) -> None:
        self._refresh.dispose()

    def _render(self, info: SystemInfo) -> None:
        values = {
            "hostname": info.hostname,
            "os": f"{info.os_name} ({BOOT_MODE_LABELS[info.boot_mode]})",
            "kernel": info.kernel,
            "desktop": info.desktop_session or _("Unavailable"),
            "cpu": info.cpu or _("Unknown"),
            "gpu": info.gpu or _("Unavailable"),
            "memory": format_bytes(info.memory_bytes),
            "disk": format_bytes(info.disk_bytes),
            "ip": info.internal_ips or _("Unavailable"),
        }
        for name, value in values.items():
            self._values[name].set_text(value)
        self._set_header_icon(info.distro_id)
        self._status.set_text("")

    def _set_header_icon(self, distro_id: str) -> None:
        if distro_id == "pardus":
            path = VENDOR_ICON_DIR / "emblem-vendor-symbolic.svg"
            if path.is_file():
                icon = Gio.FileIcon.new(Gio.File.new_for_path(str(path)))
                self._header_icon.set_from_gicon(icon, Gtk.IconSize.DIALOG)
                self._header_icon.set_pixel_size(48)

    def _show_error(self, error: BaseException) -> None:
        self._status.set_text(
            _("Could not load system information: {error}").format(error=error)
        )


def _info_row(title: str) -> tuple[Gtk.ListBoxRow, Gtk.Label]:
    row = Gtk.ListBoxRow(selectable=False, activatable=False)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    content.get_style_context().add_class("system-info-row")
    title_label = Gtk.Label(label=title, xalign=0)
    title_label.get_style_context().add_class("dim-label")
    value = Gtk.Label(xalign=0, selectable=True)
    value.set_ellipsize(Pango.EllipsizeMode.END)
    value.get_style_context().add_class("system-info-value")
    content.pack_start(title_label, False, False, 0)
    content.pack_start(value, False, False, 0)
    row.add(content)
    return row, value
