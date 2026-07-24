import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.formatting import format_bytes
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.processes.repository import ProcessSnapshot, list_processes
from pardus_panel.features.processes.termination import (
    TerminationStatus,
    terminate_process,
)
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _

(
    PID,
    NAME,
    USER,
    MEMORY_TEXT,
    CPU_TEXT,
    MEMORY_RAW,
    CPU_RAW,
    CREATE_TIME,
    STATUS,
) = range(9)
PROCESS_STATUS_LABELS = {
    "running": _("Running"),
    "sleeping": _("Sleeping"),
    "disk-sleep": _("Disk sleep"),
    "stopped": _("Stopped"),
    "tracing-stop": _("Tracing stop"),
    "zombie": _("Zombie"),
    "dead": _("Dead"),
    "wake-kill": _("Wake kill"),
    "waking": _("Waking"),
    "parked": _("Parked"),
    "idle": _("Idle"),
    "locked": _("Locked"),
    "waiting": _("Waiting"),
}


class ProcessPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._jobs = jobs
        self._scope = LifecycleScope()
        self._builder = Builder("Process.ui")
        required = self._builder.get_required
        self.root = required("process_content", Gtk.Box)
        self._title = required("process_title", Gtk.Label)
        self._search = required("process_search_entry", Gtk.SearchEntry)
        self._refresh_button = required("process_refresh_button", Gtk.Button)
        self._kill_button = required("process_kill_button", Gtk.Button)
        self._status = required("process_status", Gtk.Label)
        self._view = required("process_view", Gtk.TreeView)
        self._store = Gtk.ListStore(int, str, str, str, str, float, float, float, str)
        self._view.set_model(self._store)
        self._store.set_sort_column_id(MEMORY_RAW, Gtk.SortType.DESCENDING)
        self._columns = {
            USER: required("process_user_column", Gtk.TreeViewColumn),
            STATUS: required("process_status_column", Gtk.TreeViewColumn),
        }
        self._termination_dialog = required("process_termination_dialog", Gtk.Dialog)
        self._termination_title = required("process_termination_title", Gtk.Label)
        self._termination_detail = required("process_termination_detail", Gtk.Label)
        self._processes: tuple[ProcessSnapshot, ...] = ()
        self._timer_id: int | None = None
        self._active = False
        self._terminating = False
        self._connect_signals()
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=list_processes,
            on_result=self._receive_processes,
            on_error=self._show_error,
        )

    def set_active(self, active: bool) -> None:
        if self._scope.disposed or active == self._active:
            return
        self._active = active
        if active:
            self._timer_id = GLib.timeout_add(5_000, self._on_timer)
            self._refresh.request()
        elif self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def dispose(self) -> None:
        self.set_active(False)
        self._refresh.dispose()
        self._scope.cleanup()

    def _connect_signals(self) -> None:
        self._scope.connect(self._search, "changed", self._on_search_changed)
        self._scope.connect(
            self._refresh_button,
            "clicked",
            lambda _button: self._refresh.request(),
        )
        self._scope.connect(
            self._kill_button,
            "clicked",
            lambda _button: self._confirm_termination(),
        )
        selection = self._view.get_selection()
        self._scope.connect(selection, "changed", self._on_selection_changed)
        self._scope.connect(self._view, "key-press-event", self._on_key_press)
        self._scope.connect(self.root, "size-allocate", self._on_size_allocate)

    def _on_size_allocate(self, _root: Gtk.Box, allocation: Gdk.Rectangle) -> None:
        wide = allocation.width >= 600
        self._title.set_visible(wide)
        self._columns[USER].set_visible(wide)
        self._columns[STATUS].set_visible(wide)

    def _on_timer(self) -> bool:
        if not self._active or self._scope.disposed:
            self._timer_id = None
            return GLib.SOURCE_REMOVE
        self._refresh.request()
        return GLib.SOURCE_CONTINUE

    def _receive_processes(self, processes: tuple[ProcessSnapshot, ...]) -> None:
        self._processes = processes
        self._render()

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self._render()

    def _render(self) -> None:
        selected = self._selected_identity()
        needle = self._search.get_text().strip().casefold()
        shown = [
            process
            for process in self._processes
            if not needle
            or needle
            in f"{process.pid} {process.name} {process.username or ''}".casefold()
        ]
        self._store.clear()
        for process in shown:
            self._store.append(
                (
                    process.pid,
                    process.name,
                    process.username or _("Unknown"),
                    format_bytes(process.memory_bytes),
                    f"{process.cpu_percent:.1f}%",
                    float(process.memory_bytes),
                    process.cpu_percent,
                    process.create_time,
                    PROCESS_STATUS_LABELS.get(process.status or "", _("Unknown")),
                )
            )
        if selected is not None:
            for model_row in self._store:
                if (model_row[PID], model_row[CREATE_TIME]) == selected:
                    self._view.get_selection().select_path(model_row.path)
                    break
        self._status.set_text(_("{count} processes").format(count=len(shown)))
        self._on_selection_changed(self._view.get_selection())

    def _selected_identity(self) -> tuple[int, float] | None:
        model, iterator = self._view.get_selection().get_selected()
        if iterator is None:
            return None
        return int(model[iterator][PID]), float(model[iterator][CREATE_TIME])

    def _selected_name(self) -> str:
        model, iterator = self._view.get_selection().get_selected()
        return str(model[iterator][NAME]) if iterator is not None else ""

    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        _model, iterator = selection.get_selected()
        self._kill_button.set_sensitive(iterator is not None and not self._terminating)

    def _on_key_press(self, _view: Gtk.TreeView, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Delete and self._selected_identity() is not None:
            self._confirm_termination()
            return True
        return False

    def _confirm_termination(self) -> None:
        identity = self._selected_identity()
        if identity is None:
            return
        pid, create_time = identity
        self._termination_dialog.set_transient_for(self.root.get_toplevel())
        self._termination_title.set_text(
            _("End {name}?").format(name=self._selected_name())
        )
        self._termination_detail.set_text(
            _("PID {pid} will be asked to stop.").format(pid=pid)
        )
        self._termination_dialog.show_all()
        response = self._termination_dialog.run()
        self._termination_dialog.hide()
        if response == Gtk.ResponseType.OK:
            self._terminating = True
            self._on_selection_changed(self._view.get_selection())
            self._jobs.submit(
                lambda: terminate_process(pid=pid, create_time=create_time),
                on_success=self._termination_done,
                on_error=self._termination_failed,
            )

    def _termination_done(self, status: TerminationStatus) -> None:
        self._terminating = False
        if self._scope.disposed:
            return
        messages = {
            TerminationStatus.TERMINATED: _("Process ended"),
            TerminationStatus.KILLED: _("Process killed after timeout"),
            TerminationStatus.GONE: _("Process already gone"),
            TerminationStatus.DENIED: _("Permission denied"),
            TerminationStatus.TIMED_OUT: _("Process did not stop"),
            TerminationStatus.REUSED: _("PID now belongs to another process"),
        }
        self._view.get_selection().unselect_all()
        self._status.set_text(messages[status])
        self._refresh.request()

    def _termination_failed(self, error: BaseException) -> None:
        self._terminating = False
        if self._scope.disposed:
            return
        self._on_selection_changed(self._view.get_selection())
        self._status.set_text(_("Could not end process: {error}").format(error=error))

    def _show_error(self, error: BaseException) -> None:
        self._status.set_text(
            _("Could not load processes: {error}").format(error=error)
        )
