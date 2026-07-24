from enum import Enum

import psutil


class TerminationStatus(str, Enum):
    TERMINATED = "terminated"
    KILLED = "killed"
    GONE = "gone"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    REUSED = "reused"


def terminate_process(
    *,
    pid: int,
    create_time: float,
    timeout: float = 2.0,
) -> TerminationStatus:
    if pid <= 0:
        raise ValueError("PID must be positive")
    try:
        process = psutil.Process(pid)
        if abs(float(process.create_time()) - create_time) > 1e-6:
            return TerminationStatus.REUSED
        process.terminate()
        process.wait(timeout=timeout)
        return TerminationStatus.TERMINATED
    except psutil.NoSuchProcess:
        return TerminationStatus.GONE
    except psutil.AccessDenied:
        return TerminationStatus.DENIED
    except psutil.TimeoutExpired:
        pass

    try:
        process.kill()
        process.wait(timeout=timeout)
        return TerminationStatus.KILLED
    except psutil.NoSuchProcess:
        return TerminationStatus.GONE
    except psutil.AccessDenied:
        return TerminationStatus.DENIED
    except psutil.TimeoutExpired:
        return TerminationStatus.TIMED_OUT
