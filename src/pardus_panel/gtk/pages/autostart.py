import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator
from pardus_panel.features.autostart.entities import AutostartEntry, AutostartSource
from pardus_panel.features.autostart.repository import AutostartRepository
from pardus_panel.gtk.builder import Builder
from pardus_panel.i18n import _


class AutostartPage:
    def __init__(self, *, jobs: AsyncJobRunner) -> None:
        self._jobs = jobs
        self._repository = AutostartRepository()
        self._scope = LifecycleScope()
        self._builder = Builder("Autostart.ui")
        required = self._builder.get_required
        self.root = required("autostart_content", Gtk.Box)
        self._view = required("autostart_view", Gtk.ListBox)
        self._add_button = required("autostart_add_button", Gtk.Button)
        self._status = required("autostart_status", Gtk.Label)
        self._add_dialog = required("autostart_add_dialog", Gtk.Dialog)
        self._name_entry = required("autostart_name_entry", Gtk.Entry)
        self._command_entry = required("autostart_command_entry", Gtk.Entry)
        self._scope.connect(
            self._add_button, "clicked", lambda _button: self._show_add_dialog()
        )
        self._refresh = RefreshCoordinator(
            jobs=jobs,
            work=self._repository.list_entries,
            on_result=self._render,
            on_error=self._show_error,
        )

    def set_active(self, active: bool) -> None:
        if self._scope.disposed:
            return
        if active:
            self._refresh.request()

    def dispose(self) -> None:
        self._refresh.dispose()
        self._scope.cleanup()

    def _render(self, entries: tuple[AutostartEntry, ...]) -> None:
        for row in self._view.get_children():
            row.destroy()
        for entry in entries:
            self._view.add(self._make_row(entry))
        self._view.show_all()
        self._status.set_text(_("{count} entries").format(count=len(entries)))

    def _make_row(self, entry: AutostartEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(selectable=False, activatable=False)
        content = Gtk.Box(spacing=12, margin=10)

        toggle = Gtk.Switch(active=not entry.hidden, valign=Gtk.Align.CENTER)
        toggle.get_accessible().set_name(_("Enable {name}").format(name=entry.name))
        toggle.connect(
            "state-set",
            lambda _switch, enabled: self._set_enabled(entry, enabled),
        )
        content.pack_start(toggle, False, False, 0)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label=entry.name, xalign=0, ellipsize=3)
        name.get_style_context().add_class("system-info-value")
        command = Gtk.Label(label=entry.command, xalign=0, ellipsize=3)
        command.get_style_context().add_class("dim-label")
        details.pack_start(name, False, False, 0)
        details.pack_start(command, False, False, 0)
        content.pack_start(details, True, True, 0)

        source = Gtk.Label(
            label=_("User") if entry.source is AutostartSource.USER else _("System")
        )
        source.get_style_context().add_class("dim-label")
        content.pack_start(source, False, False, 0)

        delete = Gtk.Button.new_from_icon_name(
            "user-trash-symbolic", Gtk.IconSize.BUTTON
        )
        delete.set_tooltip_text(_("Delete startup application"))
        delete.set_valign(Gtk.Align.CENTER)
        delete.set_sensitive(entry.source is AutostartSource.USER)
        delete.connect("clicked", lambda _button: self._delete(entry))
        content.pack_start(delete, False, False, 0)

        row.add(content)
        return row

    def _set_enabled(self, entry: AutostartEntry, enabled: bool) -> bool:
        self._jobs.submit(
            lambda: self._repository.set_enabled(entry, enabled=enabled),
            on_success=lambda _value: self._refresh.request(),
            on_error=self._show_error,
        )
        return False

    def _delete(self, entry: AutostartEntry) -> None:
        self._jobs.submit(
            lambda: self._repository.delete(entry),
            on_success=lambda _value: self._refresh.request(),
            on_error=self._show_error,
        )

    def _show_add_dialog(self) -> None:
        self._name_entry.set_text("")
        self._command_entry.set_text("")
        self._add_dialog.set_transient_for(self.root.get_toplevel())
        self._add_dialog.show_all()
        response = self._add_dialog.run()
        name = self._name_entry.get_text()
        command = self._command_entry.get_text()
        self._add_dialog.hide()
        if response != Gtk.ResponseType.OK:
            return
        self._jobs.submit(
            lambda: self._repository.create(name=name, command=command),
            on_success=lambda _value: self._refresh.request(),
            on_error=self._show_error,
        )

    def _show_error(self, error: BaseException) -> None:
        if not self._scope.disposed:
            self._status.set_text(
                _("Autostart action failed: {error}").format(error=error)
            )
