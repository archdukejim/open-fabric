import fcntl
import os
from contextlib import contextmanager

from fabriclib.common.paths import VARS_LOCK_FILE


@contextmanager
def vars_lock(path=VARS_LOCK_FILE):
    """Exclusive lock for read-modify-write of vars.yaml (CLI, fabricd, web UI)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
