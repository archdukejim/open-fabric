import subprocess

from fabriclib.common.console import ok
from fabriclib.setup import mint_service_certs


def renew_service_certs(ctx, force=False):
    """Purpose: day-2 certificate renewal on a running install (`fabricctl certs [--force]`): issue the service
             certificates that need it and restart only the services whose certificates changed.
    Inputs:  ctx — SetupContext (state is reloaded from vars.yaml); force — bool, re-issue all (default False).
    Returns: None. Changed services that are active are restarted; inactive ones are left for their next start.
    Fails:   as mint_service_certs.run (SetupError, ValidationError, CalledProcessError); CalledProcessError
             from `systemctl restart`.
    Feeds:   cli main (`certs`)."""
    ctx.load_state()
    ctx.force_certs = force
    mint_service_certs.run(ctx)
    for unit in sorted(ctx.restart_services):
        if subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0:
            subprocess.run(["systemctl", "restart", unit], check=True)
            ok(f"{unit}: restarted")
