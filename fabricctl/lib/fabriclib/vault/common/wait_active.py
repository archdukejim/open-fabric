import time

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request


def wait_active(v, timeout=120, uninitialised_ok=False):
    """Purpose: wait until OpenBao is the active node (sys/health 200), polling every 2 seconds.
    Inputs:  v — vars for bao_request; timeout — seconds (120);
             uninitialised_ok — also accept 501 (a server not initialised yet counts as ready).
    Returns: the sys/health status that ended the wait: 200, or 501 with uninitialised_ok.
    Fails:   ValidationError "did not become active within <timeout> s" with the last status (None: unreachable).
    Feeds:   init_openbao, run_vault_command.restart_openbao, setup/setup_openbao.
    Notes:   right after a start OpenBao may be unsealed while Raft still elects it leader; requests then fail
             ("local node not active"), so unsealed is not enough.
    """
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
