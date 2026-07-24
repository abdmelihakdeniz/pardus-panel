import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from pardus_panel.features.logs.repository import list_entries, parse_record
from pardus_panel.features.services.repository import (
    ServiceScope,
    apply_service_action,
    list_services,
    valid_unit,
)


class SystemFeatureTests(unittest.TestCase):
    def test_log_records_are_normalized(self):
        entry = parse_record(
            json.dumps(
                {
                    "__REALTIME_TIMESTAMP": "1000000",
                    "PRIORITY": 6,
                    "_SYSTEMD_UNIT": "demo.service",
                    "MESSAGE": [72, 105, 0, 999],
                }
            )
        )

        self.assertEqual(entry.timestamp, datetime.fromtimestamp(1, tz=timezone.utc))
        self.assertEqual(entry.priority, "6")
        self.assertEqual(entry.source, "demo.service")
        self.assertEqual(entry.message, "Hi�")
        self.assertIsNone(parse_record("not json"))

    @patch("pardus_panel.features.logs.repository.run_command")
    def test_log_listing_builds_a_bounded_filtered_query(self, run):
        run.return_value = "\n".join(
            (
                json.dumps({"SYSLOG_IDENTIFIER": "first", "MESSAGE": "ignored"}),
                json.dumps({"SYSLOG_IDENTIFIER": "second", "MESSAGE": "Needle"}),
            )
        )

        entries = list_entries(
            scope="user",
            priority="err",
            limit=5000,
            search="needle",
        )

        self.assertEqual([entry.source for entry in entries], ["second"])
        command = run.call_args.args[0]
        self.assertIn("--user", command)
        self.assertIn("--lines=1000", command)
        self.assertEqual(command[-2:], ["--priority", "err"])

    def test_service_units_are_validated(self):
        self.assertTrue(valid_unit("demo@user.service"))
        for unit in ("", ".service", "demo.timer", "bad unit.service", "x" * 257):
            with self.subTest(unit=unit):
                self.assertFalse(valid_unit(unit))

    @patch("pardus_panel.features.services.repository.run_command")
    def test_service_actions_use_the_expected_privilege(self, run):
        apply_service_action(
            scope=ServiceScope.SYSTEM,
            unit="demo.service",
            action="restart",
        )
        run.assert_called_once_with(
            [
                "/usr/bin/pkexec",
                "/bin/systemctl",
                "restart",
                "--",
                "demo.service",
            ],
            timeout=60.0,
        )

        with self.assertRaises(ValueError):
            apply_service_action(
                scope=ServiceScope.SYSTEM,
                unit="demo.service",
                action="remove",
            )

    @patch("pardus_panel.features.services.repository.run_command")
    def test_service_states_are_combined_and_sorted(self, run):
        def output(command):
            is_user = "--user" in command
            if "list-units" in command:
                return (
                    ""
                    if is_user
                    else "demo.service loaded active running Demo service\n"
                )
            return (
                "demo.service disabled\n"
                if is_user
                else "demo.service enabled\norphan.service static\n"
            )

        run.side_effect = output
        entries = list_services()

        self.assertEqual(
            [
                (entry.unit, entry.scope, entry.active, entry.enabled)
                for entry in entries
            ],
            [
                ("demo.service", ServiceScope.SYSTEM, "active", "enabled"),
                ("demo.service", ServiceScope.USER, "inactive", "disabled"),
                ("orphan.service", ServiceScope.SYSTEM, "inactive", "static"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
