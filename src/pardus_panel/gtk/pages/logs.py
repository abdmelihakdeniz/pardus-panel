import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.logs.repository import LogEntry, list_entries
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

PRIORITY_NAMES = {
    "0": _("Emergency"),
    "1": _("Alert"),
    "2": _("Critical"),
    "3": _("Error"),
    "4": _("Warning"),
    "5": _("Notice"),
    "6": _("Info"),
    "7": _("Debug"),
}


class LogsPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._scope = LifecycleScope()
        self._builder = Builder("Logs.ui")
        required = self._builder.get_required
        self.root = required("logs_content", Gtk.Box)
        self._search = required("logs_search", Gtk.SearchEntry)
        self._scope_combo = required("logs_scope", Gtk.ComboBoxText)
        self._priority = required("logs_priority", Gtk.ComboBoxText)
        self._refresh_button = required("logs_refresh", Gtk.Button)
        self._view = required("logs_view", Gtk.TreeView)
        self._status = required("logs_status", Gtk.Label)
        self._detail_dialog = required("logs_detail_dialog", Gtk.Dialog)
        self._detail_time = required("logs_detail_time", Gtk.Label)
        self._detail_level = required("logs_detail_level", Gtk.Label)
        self._detail_source = required("logs_detail_source", Gtk.Label)
        self._detail_message = required("logs_detail_message", Gtk.TextView)
        self._store = Gtk.ListStore(str, str, str, str)
        self._view.set_model(self._store)
        self._filters = ("system", "all", "")
        self._scope_combo.set_active_id("system")
        self._priority.set_active_id("all")
        self._connect()
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=self._load_entries,
            on_result=self._render,
            on_error=self._show_error,
        )

    def set_active(self, active: bool) -> None:
        if active and not self._scope.disposed:
            self._status.set_text(_("Loading logs…"))
            self._request_refresh()

    def dispose(self) -> None:
        self._refresh.dispose()
        self._scope.cleanup()

    def _connect(self) -> None:
        for widget, signal in (
            (self._scope_combo, "changed"),
            (self._priority, "changed"),
            (self._search, "activate"),
        ):
            self._scope.connect(widget, signal, self._request_refresh)
        self._scope.connect(
            self._refresh_button,
            "clicked",
            self._request_refresh,
        )
        self._scope.connect(self._view, "row-activated", self._show_detail)

    def _show_detail(
        self,
        _view: Gtk.TreeView,
        path: Gtk.TreePath,
        _column: Gtk.TreeViewColumn,
    ) -> None:
        row = self._store[path]
        self._detail_time.set_text(_("Time: {value}").format(value=row[0]))
        self._detail_level.set_text(_("Level: {value}").format(value=row[1]))
        self._detail_source.set_text(_("Source: {value}").format(value=row[2]))
        self._detail_message.get_buffer().set_text(str(row[3]))
        self._detail_dialog.set_transient_for(self.root.get_toplevel())
        self._detail_dialog.show_all()
        self._detail_dialog.run()
        self._detail_dialog.hide()

    def _request_refresh(self, _widget=None) -> None:
        self._filters = (
            self._scope_combo.get_active_id() or "system",
            self._priority.get_active_id() or "all",
            self._search.get_text(),
        )
        self._refresh.request()

    def _load_entries(self) -> tuple[LogEntry, ...]:
        scope, priority, search = self._filters
        return list_entries(scope=scope, priority=priority, search=search)

    def _render(self, entries: tuple[LogEntry, ...]) -> None:
        self._store.clear()
        for entry in entries:
            time_text = (
                entry.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                if entry.timestamp
                else _("Unknown")
            )
            priority = PRIORITY_NAMES.get(entry.priority, _("Unknown"))
            self._store.append(
                (time_text, priority, entry.source or _("Unknown"), entry.message)
            )
        self._status.set_text(
            _("{count} log entries").format(count=len(entries))
            if entries
            else _("No log entries found")
        )

    def _show_error(self, error: BaseException) -> None:
        self._status.set_text(_("Could not load logs: {error}").format(error=error))
