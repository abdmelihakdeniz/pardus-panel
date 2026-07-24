import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.power.collector import (
    PowerSnapshot,
    collect_power_info,
    set_power_profile,
)
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

BATTERY_STATUS_LABELS = {
    "Charging": _("Charging"),
    "Discharging": _("Discharging"),
    "Not charging": _("Not charging"),
    "Full": _("Full"),
    "Unknown": _("Unknown"),
}
PROFILE_LABELS = {
    "power-saver": _("Power saver"),
    "balanced": _("Balanced"),
    "performance": _("Performance"),
}


class PowerPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._jobs = jobs
        self._scope = LifecycleScope()
        self._builder = Builder("Power.ui")
        required = self._builder.get_required
        self.root = required("power_content", Gtk.Box)
        self._battery = required("power_battery", Gtk.Label)
        self._health = required("power_health", Gtk.Label)
        self._time = required("power_time", Gtk.Label)
        self._profile = required("power_profile", Gtk.ComboBoxText)
        self._profile_unavailable = required("power_profile_unavailable", Gtk.Label)
        self._status = required("power_status", Gtk.Label)
        self._updating_profile = False
        self._profile.set_sensitive(False)
        self._scope.connect(self._profile, "changed", self._profile_changed)
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=collect_power_info,
            on_result=self._render,
            on_error=self._show_error,
        )

    def set_active(self, active: bool) -> None:
        if active and not self._scope.disposed:
            self._status.set_text(_("Loading power information…"))
            self._refresh.request()

    def dispose(self) -> None:
        self._refresh.dispose()
        self._scope.cleanup()

    def _render(self, snapshot: PowerSnapshot) -> None:
        battery = snapshot.battery
        if battery is None:
            self._battery.set_text(_("No battery detected"))
            self._health.set_text(_("Unavailable"))
            self._status.set_text(_("Unavailable"))
            self._time.set_text(_("Unavailable"))
        else:
            percent = (
                f"{battery.percent:.0f}%"
                if battery.percent is not None
                else _("Unknown")
            )
            status = BATTERY_STATUS_LABELS.get(battery.status, _("Unknown"))
            self._battery.set_text(percent)
            self._health.set_text(
                f"{battery.health_percent:.0f}%"
                if battery.health_percent is not None
                else _("Unknown")
            )
            self._status.set_text(status)
            self._time.set_text(_duration(battery.seconds_left))
        self._updating_profile = True
        self._profile.remove_all()
        for profile in snapshot.profiles:
            self._profile.append(profile, PROFILE_LABELS.get(profile, _("Unknown")))
        self._profile.set_active_id(snapshot.active_profile)
        self._profile.set_sensitive(bool(snapshot.profiles))
        self._profile.set_visible(bool(snapshot.profiles))
        self._profile_unavailable.set_visible(not snapshot.profiles)
        self._updating_profile = False

    def _profile_changed(self, _combo: Gtk.ComboBoxText) -> None:
        profile = self._profile.get_active_id()
        if self._updating_profile or not profile:
            return
        self._profile.set_sensitive(False)
        self._jobs.submit(
            lambda: set_power_profile(profile),
            on_success=lambda _value: self._refresh.request(),
            on_error=self._profile_failed,
        )

    def _profile_failed(self, error: BaseException) -> None:
        if self._scope.disposed:
            return
        self._profile.set_sensitive(True)
        self._show_error(error)

    def _show_error(self, error: BaseException) -> None:
        self._status.set_text(
            _("Could not load power information: {error}").format(error=error)
        )


def _duration(seconds: int | None) -> str:
    if seconds is None:
        return _("Unknown")
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return _("{hours} h {minutes} min").format(hours=hours, minutes=minutes)
