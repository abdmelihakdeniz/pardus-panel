import tempfile
import unittest
from pathlib import Path

from pardus_panel.features.autostart.entities import (
    AutostartEntry,
    AutostartSource,
)
from pardus_panel.features.autostart.parser import (
    DesktopEntryError,
    parse_desktop_entry,
    serialize_desktop_entry,
)
from pardus_panel.features.autostart.repository import AutostartRepository


def desktop_entry(name="Demo", command="/bin/true"):
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={command}\n"
    )


class AutostartTests(unittest.TestCase):
    def test_desktop_entry_round_trip(self):
        path = Path("/etc/xdg/autostart/demo.desktop")
        entry = parse_desktop_entry(
            desktop_entry() + "Hidden=1\nNoDisplay=false\nX-Test=value\n",
            path=path,
            source=AutostartSource.SYSTEM,
        )

        self.assertTrue(entry.hidden)
        self.assertFalse(entry.no_display)
        self.assertEqual(entry.extra_fields, (("X-Test", "value"),))

        parsed_again = parse_desktop_entry(
            serialize_desktop_entry(entry),
            path=path,
            source=AutostartSource.SYSTEM,
        )
        self.assertEqual(parsed_again, entry)

    def test_desktop_entry_rejects_invalid_content(self):
        cases = (
            "\0",
            "[Other]\nName=Demo\nExec=/bin/true\n",
            "[Desktop Entry]\nType=Link\nName=Demo\nExec=/bin/true\n",
            "[Desktop Entry]\nExec=/bin/true\n",
            desktop_entry() + "Hidden=maybe\n",
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaises(DesktopEntryError):
                    parse_desktop_entry(
                        content,
                        path=Path("demo.desktop"),
                        source=AutostartSource.USER,
                    )

    def test_serializer_drops_unsafe_extra_fields(self):
        entry = AutostartEntry(
            basename="demo.desktop",
            path=Path("demo.desktop"),
            source=AutostartSource.USER,
            name="Demo",
            command="/bin/true",
            hidden=False,
            no_display=False,
            extra_fields=(
                ("X-Good", "yes"),
                ("Bad\nKey", "ignored"),
                ("Name", "override"),
            ),
        )

        content = serialize_desktop_entry(entry)
        self.assertIn("X-Good=yes\n", content)
        self.assertNotIn("Bad\nKey", content)
        self.assertEqual(content.count("Name="), 1)

    def test_repository_masks_system_entries_and_manages_user_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = AutostartRepository()
            repository.config_home = root / "user"
            repository.config_dirs = (root / "system",)

            system_dir = repository.config_dirs[0] / "autostart"
            system_dir.mkdir(parents=True)
            system_path = system_dir / "demo.desktop"
            system_path.write_text(desktop_entry(), encoding="utf-8")

            repository.user_dir.mkdir(parents=True)
            user_mask = repository.user_dir / system_path.name
            user_mask.write_text("broken", encoding="utf-8")
            self.assertEqual(repository.list_entries(), ())

            user_mask.unlink()
            system_entry = repository.list_entries()[0]
            self.assertIs(system_entry.source, AutostartSource.SYSTEM)

            first = repository.create(name="My App", command="/bin/true")
            second = repository.create(name="My App", command="/bin/false")
            self.assertEqual(first.basename, "my-app.desktop")
            self.assertEqual(second.basename, "my-app-2.desktop")

            disabled = repository.set_enabled(system_entry, enabled=False)
            self.assertTrue(disabled.hidden)
            self.assertIs(disabled.source, AutostartSource.USER)
            self.assertTrue(disabled.path.exists())

            with self.assertRaises(PermissionError):
                repository.delete(system_entry)
            repository.delete(first)
            self.assertFalse(first.path.exists())


if __name__ == "__main__":
    unittest.main()
