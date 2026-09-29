import time

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request


def wait_active(v, timeout=120, uninitialised_ok=False):
    """Wait until OpenBao is the active node (sys/health 200). Right after a
    start it may be unsealed while Raft still elects it leader; requests
    then fail ("local node not active"). With `uninitialised_ok`, a server
    that has not been initialised yet (501) also counts as ready."""
    deadline = time.time() + timeout
    while True:
        try:
            status = bao_request(v, "GET", "sys/health")[0]
        except ValidationError:
            status = None
        if status == 200 or (uninitialised_ok and status == 501):
            return status
        if time.time() > deadline:
            raise ValidationError(f"OpenBao did not become active within {timeout} s (sys/health {status})")
        time.sleep(2)
