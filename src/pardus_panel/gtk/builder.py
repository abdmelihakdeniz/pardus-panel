import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from pardus_panel.core.paths import read_text_resource
from pardus_panel.i18n import DOMAIN


class Builder(Gtk.Builder):
    def __init__(self, source: str) -> None:
        super().__init__()
        self._source = source
        self.set_translation_domain(DOMAIN)
        try:
            self.add_from_string(read_text_resource("ui", source))
        except GLib.Error as exc:
            raise RuntimeError(f"Invalid Builder resource {source}: {exc}") from exc
        for widget in self.get_objects():
            if isinstance(widget, Gtk.Button) and not widget.get_label():
                accessible_name = widget.get_tooltip_text()
                if accessible_name:
                    widget.get_accessible().set_name(accessible_name)

    def get_required(self, name: str, expected_type: type):
        widget = self.get_object(name)
        if not isinstance(widget, expected_type):
            raise RuntimeError(
                f"{self._source} must define {name} as {expected_type.__name__}"
            )
        return widget
