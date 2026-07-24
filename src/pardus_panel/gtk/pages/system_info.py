from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.formatting import format_bytes
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.system_info.collector import SystemInfo, collect_system_info
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

VENDOR_ICON_DIR = Path("/usr/share/icons/vendor/scalable/emblems")


class SystemInfoPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._builder = Builder("SystemInfo.ui")
        required = self._builder.get_required
        self.root = required("system_info_content", Gtk.Box)
        self._header_icon = required("system_info_icon", Gtk.Image)
        self._values = {
            name: required(f"system_info_{name}", Gtk.Label)
            for name in (
                "os",
                "hostname",
                "kernel",
                "cpu",
                "memory",
                "disk",
                "gpu",
            )
        }
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
            "os": info.os_name,
            "hostname": info.hostname,
            "kernel": info.kernel,
            "cpu": info.cpu or _("Unknown"),
            "memory": format_bytes(info.memory_bytes),
            "disk": format_bytes(info.disk_bytes),
            "gpu": info.gpu or _("Unavailable"),
        }
        for name, value in values.items():
            self._values[name].set_text(str(value))
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
