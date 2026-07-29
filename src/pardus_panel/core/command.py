import os
import signal
import subprocess
import threading
from collections.abc import Sequence

_RUNNING_COMMANDS: set[subprocess.Popen[str]] = set()
_RUNNING_COMMANDS_LOCK = threading.Lock()


class CommandError(RuntimeError):
    pass


def run_command(arguments: Sequence[str], *, timeout: float = 8.0) -> str:
    if (
        isinstance(arguments, (str, bytes))
        or not arguments
        or not arguments[0]
        or any(not isinstance(value, str) or "\x00" in value for value in arguments)
    ):
        raise ValueError("Command arguments are invalid")
    environment = os.environ | {"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    try:
        process = subprocess.Popen(
            list(arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env=environment,
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise CommandError(f"{arguments[0]} is not installed") from error
    except OSError as error:
        raise CommandError(f"{arguments[0]} could not be executed: {error}") from error
    with _RUNNING_COMMANDS_LOCK:
        _RUNNING_COMMANDS.add(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _kill(process)
        process.communicate()
        raise CommandError(f"{arguments[0]} timed out") from error
    finally:
        with _RUNNING_COMMANDS_LOCK:
            _RUNNING_COMMANDS.discard(process)
    if process.returncode != 0:
        message = stderr.strip() or (
            f"{arguments[0]} exited with status {process.returncode}"
        )
        raise CommandError(message)
    return stdout


def cancel_running_commands() -> None:
    with _RUNNING_COMMANDS_LOCK:
        processes = tuple(_RUNNING_COMMANDS)
    for process in processes:
        _kill(process)


def _kill(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
