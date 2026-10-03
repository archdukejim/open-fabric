import fcntl
import os
from contextlib import contextmanager

from fabriclib.common.paths import VARS_LOCK_FILE


@contextmanager
def vars_lock(path=VARS_LOCK_FILE):
    """Purpose: exclusive lock (context manager) around read-modify-write of vars.yaml, shared by the CLI,
             fabric-agent and the web UI.
    Inputs:  path — str, the lock file, default VARS_LOCK_FILE (created, and its folder, if missing).
    Returns: a context manager; the body runs while the flock is held.
    Fails:   OSError if the lock file or its folder cannot be created; blocks without timeout while another
             process holds the lock. Exceptions from the body propagate after the lock is released.
    Feeds:   dns/* edits, dhcp/add_reservation, dhcp/remove_reservation, radius/* edits, system/apply_changes."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
