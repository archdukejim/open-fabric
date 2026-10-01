import fcntl
import os
from contextlib import contextmanager

from fabriclib.common.paths import FEDERATION_LOCK_FILE


@contextmanager
def federation_lock(path=FEDERATION_LOCK_FILE):
    """Purpose: exclusive lock (context manager) around read-modify-write of the invitations (in fabric's
             secrets) and the site registry, shared by `fabricctl federation` and the federation endpoint.
    Inputs:  path — str, the lock file, default FEDERATION_LOCK_FILE (created, and its folder, if missing).
    Returns: a context manager; the body runs while the flock is held.
    Fails:   OSError if the lock file or its folder cannot be created; blocks without timeout while another
             process holds the lock. Exceptions from the body propagate after the lock is released.
    Feeds:   create_invitation, revoke_invitation, accept_join."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
