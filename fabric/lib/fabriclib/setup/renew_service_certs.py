import subprocess

from fabriclib.common.console import ok
from fabriclib.setup import mint_service_certs


def renew_service_certs(ctx, force=False):
    """Day-2 certificate renewal on a running install: issue the service
    certificates that need it (all of them with force) and restart only the
    services whose certificates changed."""
    ctx.load_state()
    ctx.force_certs = force
    mint_service_certs.run(ctx)
    for unit in sorted(ctx.restart_services):
        if subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0:
            subprocess.run(["systemctl", "restart", unit], check=True)
            ok(f"{unit}: restarted")
