import os
import subprocess
from collections.abc import Sequence


class CommandError(RuntimeError):
    pass


def run_command(arguments: Sequence[str], *, timeout: float = 8.0) -> str:
    if (
        isinstance(arguments, (str, bytes))
        or not arguments
        or not arguments[0]
        or any(
            not isinstance(value, str) or "\x00" in value
            for value in arguments
        )
    ):
        raise ValueError("Command arguments are invalid")
    environment = {**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    try:
        result = subprocess.run(
            list(arguments),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as error:
        raise CommandError(f"{arguments[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise CommandError(f"{arguments[0]} timed out") from error
    except OSError as error:
        raise CommandError(f"{arguments[0]} could not be executed: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or (
            f"{arguments[0]} exited with status {result.returncode}"
        )
        raise CommandError(message)
    return result.stdout
