import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.services.repository import (
    ServiceEntry,
    ServiceScope,
    apply_service_action,
    list_services,
)
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

SCOPE, UNIT, DESCRIPTION, ACTIVE, SUB, ENABLED, ENTRY = range(7)
SERVICE_STATE_LABELS = {
    "active": _("Active"),
    "reloading": _("Reloading"),
    "inactive": _("Inactive"),
    "failed": _("Failed"),
    "activating": _("Activating"),
    "deactivating": _("Deactivating"),
    "maintenance": _("Maintenance"),
    "refreshing": _("Refreshing"),
    "running": _("Running"),
    "exited": _("Exited"),
    "dead": _("Dead"),
    "condition": _("Waiting for condition"),
    "start-pre": _("Preparing to start"),
    "start": _("Starting"),
    "start-post": _("Finishing startup"),
    "reload": _("Reloading"),
    "reload-signal": _("Reloading"),
    "reload-notify": _("Reloading"),
    "auto-restart": _("Restarting automatically"),
    "stop": _("Stopping"),
    "stop-watchdog": _("Stopping"),
    "stop-sigterm": _("Stopping"),
    "stop-sigkill": _("Stopping"),
    "stop-post": _("Finishing shutdown"),
    "final-watchdog": _("Finishing shutdown"),
    "final-sigterm": _("Finishing shutdown"),
    "final-sigkill": _("Finishing shutdown"),
    "cleaning": _("Cleaning"),
    "enabled": _("Enabled"),
    "enabled-runtime": _("Enabled for this session"),
    "linked": _("Linked"),
    "linked-runtime": _("Linked for this session"),
    "alias": _("Alias"),
    "masked": _("Masked"),
    "masked-runtime": _("Masked for this session"),
    "static": _("Static"),
    "indirect": _("Indirect"),
    "disabled": _("Disabled"),
    "generated": _("Generated"),
    "transient": _("Transient"),
    "bad": _("Invalid"),
}
SERVICE_ACTION_LABELS = {
    "start": _("Start"),
    "stop": _("Stop"),
    "restart": _("Restart"),
    "enable": _("Enable"),
    "disable": _("Disable"),
}


class ServicesPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._jobs = jobs
        self._scope = LifecycleScope()
        self._builder = Builder("Services.ui")
        required = self._builder.get_required
        self.root = required("services_content", Gtk.Box)
        self._search = required("services_search", Gtk.SearchEntry)
        self._view = required("services_view", Gtk.TreeView)
        self._status = required("services_status", Gtk.Label)
        self._buttons = {
            action: required(f"services_{action}", Gtk.Button)
            for action in ("start", "stop", "restart", "enable", "disable")
        }
        self._refresh_button = required("services_refresh", Gtk.Button)
        self._store = Gtk.ListStore(str, str, str, str, str, str, object)
        self._view.set_model(self._store)
        self._columns = {
            DESCRIPTION: required("services_description_column", Gtk.TreeViewColumn),
            SUB: required("services_detail_column", Gtk.TreeViewColumn),
        }
        self._message_dialog = required("services_message_dialog", Gtk.Dialog)
        self._message_icon = required("services_message_icon", Gtk.Image)
        self._message_title = required("services_message_title", Gtk.Label)
        self._message_detail = required("services_message_detail", Gtk.Label)
        self._entries: tuple[ServiceEntry, ...] = ()
        self._busy = False
        self._connect()
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=list_services,
            on_result=self._receive,
            on_error=self._show_load_error,
        )

    def set_active(self, active: bool) -> None:
        if active and not self._scope.disposed:
            self._status.set_text(_("Loading services…"))
            self._refresh.request()

    def dispose(self) -> None:
        self._refresh.dispose()
        self._scope.cleanup()

    def _connect(self) -> None:
        self._scope.connect(self._search, "changed", lambda _entry: self._render())
        self._scope.connect(
            self._refresh_button,
            "clicked",
            lambda _button: self._refresh.request(),
        )
        selection = self._view.get_selection()
        self._scope.connect(
            selection, "changed", lambda _selection: self._update_buttons()
        )
        for action, button in self._buttons.items():
            self._scope.connect(
                button,
                "clicked",
                lambda _button, value=action: self._apply(value),
            )
        self._scope.connect(self.root, "size-allocate", self._on_size_allocate)

    def _on_size_allocate(self, _root: Gtk.Box, allocation) -> None:
        wide = allocation.width >= 600
        self._columns[DESCRIPTION].set_visible(wide)
        self._columns[SUB].set_visible(wide)

    def _receive(self, entries: tuple[ServiceEntry, ...]) -> None:
        self._entries = entries
        self._render()

    def _render(self) -> None:
        needle = self._search.get_text().casefold().strip()
        shown = [
            entry
            for entry in self._entries
            if not needle or needle in f"{entry.unit} {entry.description}".casefold()
        ]
        self._store.clear()
        for entry in shown:
            self._store.append(
                (
                    _("System") if entry.scope is ServiceScope.SYSTEM else _("User"),
                    entry.unit,
                    entry.description,
                    SERVICE_STATE_LABELS.get(entry.active, _("Unknown")),
                    SERVICE_STATE_LABELS.get(entry.sub, _("Unknown")),
                    SERVICE_STATE_LABELS.get(entry.enabled, _("Unknown")),
                    entry,
                )
            )
        self._status.set_text(
            _("{count} services").format(count=len(shown))
            if shown
            else _("No services found")
        )
        self._update_buttons()

    def _selected(self) -> ServiceEntry | None:
        model, iterator = self._view.get_selection().get_selected()
        if iterator is None:
            return None
        return model[iterator][ENTRY]

    def _update_buttons(self) -> None:
        sensitive = self._selected() is not None and not self._busy
        for button in self._buttons.values():
            button.set_sensitive(sensitive)

    def _apply(self, action: str) -> None:
        entry = self._selected()
        if entry is None or self._busy:
            return
        self._busy = True
        self._update_buttons()
        self._jobs.submit(
            lambda: apply_service_action(
                scope=entry.scope,
                unit=entry.unit,
                action=action,
            ),
            on_success=lambda _value: self._operation_done(action, entry.unit),
            on_error=lambda error: self._operation_failed(action, entry.unit, error),
        )

    def _operation_done(self, action: str, unit: str) -> None:
        self._busy = False
        if self._scope.disposed:
            return
        message = _("{action} completed for {unit}.").format(
            action=SERVICE_ACTION_LABELS[action],
            unit=unit,
        )
        self._status.set_text(message)
        self._status.set_tooltip_text(message)
        self._update_buttons()
        self._refresh.request()
        self._show_message(
            Gtk.MessageType.INFO,
            _("{action} completed").format(action=SERVICE_ACTION_LABELS[action]),
            message,
        )

    def _operation_failed(self, action: str, unit: str, error: BaseException) -> None:
        self._busy = False
        if self._scope.disposed:
            return
        message = _("{action} failed for {unit}.").format(
            action=SERVICE_ACTION_LABELS[action],
            unit=unit,
        )
        self._status.set_text(message)
        self._status.set_tooltip_text(str(error))
        self._update_buttons()
        self._show_message(
            Gtk.MessageType.ERROR,
            _("{action} failed").format(action=SERVICE_ACTION_LABELS[action]),
            _(
                "The operation could not be completed for {unit}.\n\nReason: {error}"
            ).format(unit=unit, error=error),
        )

    def _show_load_error(self, error: BaseException) -> None:
        message = _("Could not load services")
        self._status.set_text(message)
        self._status.set_tooltip_text(str(error))
        self._show_message(
            Gtk.MessageType.ERROR,
            message,
            _("The service list could not be loaded.\n\nReason: {error}").format(
                error=error
            ),
        )

    def _show_message(
        self, message_type: Gtk.MessageType, title: str, detail: str
    ) -> None:
        self._message_dialog.set_transient_for(self.root.get_toplevel())
        self._message_icon.set_from_icon_name(
            (
                "dialog-error-symbolic"
                if message_type == Gtk.MessageType.ERROR
                else "dialog-information-symbolic"
            ),
            Gtk.IconSize.DIALOG,
        )
        self._message_title.set_text(title)
        self._message_detail.set_text(detail)
        self._message_dialog.show_all()
        self._message_dialog.run()
        self._message_dialog.hide()
