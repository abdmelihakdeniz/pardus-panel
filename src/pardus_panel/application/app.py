from importlib import resources

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from pardus_panel.core.async_jobs import AsyncJobRunner
from pardus_panel.core.paths import read_text_resource
from pardus_panel.gtk.builder import Builder
from pardus_panel.gtk.pages.autostart import AutostartPage
from pardus_panel.gtk.pages.logs import LogsPage
from pardus_panel.gtk.pages.performance import PerformancePage
from pardus_panel.gtk.pages.power import PowerPage
from pardus_panel.gtk.pages.processes import ProcessPage
from pardus_panel.gtk.pages.services import ServicesPage
from pardus_panel.gtk.pages.system_info import SystemInfoPage

APPLICATION_ID = "tr.org.pardus.panel"
APPLICATION_ICON_NAME = "tr.org.pardus.panel"
APPLICATION_ICON_DIR = resources.files("pardus_panel").joinpath("data", "icons")
APPLICATION_ICON_FILE = APPLICATION_ICON_DIR.joinpath(f"{APPLICATION_ICON_NAME}.svg")
PAGES = (
    ("process", ProcessPage),
    ("performance", PerformancePage),
    ("autostart", AutostartPage),
    ("services", ServicesPage),
    ("logs", LogsPage),
    ("power", PowerPage),
    ("system-info", SystemInfoPage),
)
CSS_FILES = ("base.css", "navigation.css", "performance.css", "tables.css")


class PardusPanelApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._window: Gtk.ApplicationWindow | None = None
        self._icon: GdkPixbuf.Pixbuf | None = None
        self._jobs = AsyncJobRunner(dispatch=GLib.idle_add)
        self._pages_by_name = {}

    def do_activate(self) -> None:
        if self._window is None:
            Gtk.IconTheme.get_default().append_search_path(str(APPLICATION_ICON_DIR))
            self._icon = GdkPixbuf.Pixbuf.new_from_file(str(APPLICATION_ICON_FILE))
            Gtk.Window.set_default_icon(self._icon)
            self._load_styles()
            builder = Builder("MainWindow.ui")
            window = builder.get_required("main_window", Gtk.ApplicationWindow)
            window.set_application(self)
            window.set_icon(self._icon)
            self._window = window
            self._install_pages(builder)
            self._window.show_all()
        self._window.present()

    @staticmethod
    def _load_styles() -> None:
        screen = Gdk.Screen.get_default()
        if screen is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(
            "\n".join(read_text_resource("css", name) for name in CSS_FILES).encode()
        )
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_shutdown(self) -> None:
        for page in self._pages_by_name.values():
            page.dispose()
        self._jobs.shutdown()
        Gtk.Application.do_shutdown(self)

    def _install_pages(self, builder: Builder) -> None:
        stack = builder.get_required("content_stack", Gtk.Stack)
        sidebar = builder.get_required("sidebar_list", Gtk.ListBox)
        for name, page_type in PAGES:
            page = page_type(jobs=self._jobs)
            stack.add_named(page.root, name)
            self._pages_by_name[name] = page
        sidebar.connect("row-selected", self._on_page_selected, stack)
        initial = sidebar.get_row_at_index(0)
        if initial is not None:
            sidebar.select_row(initial)

    def _on_page_selected(
        self,
        _sidebar: Gtk.ListBox,
        row: Gtk.ListBoxRow | None,
        stack: Gtk.Stack,
    ) -> None:
        if row is None:
            return
        name = row.get_name()
        stack.set_visible_child_name(name)
        for page_name, page in self._pages_by_name.items():
            page.set_active(page_name == name)
