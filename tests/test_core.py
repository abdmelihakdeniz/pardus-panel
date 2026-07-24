import sys
import unittest
from unittest.mock import Mock, call

from pardus_panel.core.command import CommandError, run_command
from pardus_panel.core.formatting import format_bytes
from pardus_panel.core.lifecycle import LifecycleScope
from pardus_panel.core.refresh import RefreshCoordinator


class FakeJobs:
    def __init__(self):
        self.submissions = []

    def submit(self, work, *, on_success, on_error):
        self.submissions.append((work, on_success, on_error))


class CoreTests(unittest.TestCase):
    def test_lifecycle_disconnects_signals_in_reverse_order(self):
        owner = Mock()
        owner.connect.side_effect = (1, 2)
        owner.handler_is_connected.return_value = True
        scope = LifecycleScope()

        scope.connect(owner, "first", lambda: None)
        scope.connect(owner, "second", lambda: None)
        scope.cleanup()
        scope.cleanup()

        self.assertEqual(owner.disconnect.call_args_list, [call(2), call(1)])
        self.assertTrue(scope.disposed)
        with self.assertRaises(RuntimeError):
            scope.connect(owner, "late", lambda: None)

    def test_format_bytes(self):
        cases = (
            (-1, "0 B"),
            (0, "0 B"),
            (1023, "1023 B"),
            (1024, "1.0 KiB"),
            (1536, "1.5 KiB"),
            (1024**2, "1.0 MiB"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(format_bytes(value), expected)

    def test_run_command(self):
        output = run_command([sys.executable, "-c", "print('ok')"])
        self.assertEqual(output, "ok\n")

        with self.assertRaisesRegex(CommandError, "failed"):
            run_command(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stderr.write('failed'); sys.exit(2)",
                ]
            )

    def test_run_command_rejects_invalid_arguments(self):
        for arguments in ("echo", b"echo", [], [""], ["echo", "bad\0value"]):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    run_command(arguments)

    def test_refresh_requests_are_coalesced(self):
        jobs = FakeJobs()
        results = []
        errors = []
        refresh = RefreshCoordinator(
            jobs=jobs,
            work=lambda: "work",
            on_result=results.append,
            on_error=errors.append,
        )

        refresh.request()
        refresh.request()
        self.assertEqual(len(jobs.submissions), 1)

        jobs.submissions[0][1]("first")
        self.assertEqual(results, ["first"])
        self.assertEqual(len(jobs.submissions), 2)

        error = RuntimeError("failed")
        jobs.submissions[1][2](error)
        self.assertEqual(errors, [error])


if __name__ == "__main__":
    unittest.main()
