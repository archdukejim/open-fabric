import subprocess

from fabriclib.common.console import info, ok
from fabriclib.common.wait_healthy import wait_healthy
from fabriclib.setup.errors import SetupError


def run(ctx):
    """Start the two services certificate minting depends on: BIND9 (step-ca
    resolves names through it) and Step-CA; then check every zone file."""
    info("starting bind9 and step-ca (images build on first start)")
    subprocess.run(["systemctl", "enable", "--now", "bind9", "stepca"], check=True)
    for container in ("bind9", "step-ca"):
        healthy, why = wait_healthy(container, timeout=600)
        if not healthy:
            logs = subprocess.run(["docker", "logs", "--tail", "40", container], capture_output=True, text=True)
            raise SetupError(f"{container} did not become healthy ({why}):\n{logs.stdout}{logs.stderr}")
        ok(f"{container} healthy")

    domain = ctx.vars["domain"]
    uid = ctx.uid("bind")[0]
    for key in (ctx.vars.get("dns") or {}):
        zone = domain if key == "dynamic_zone_var" else key
        res = subprocess.run(["docker", "exec", "-u", str(uid), "bind9", "named-checkzone", zone,
                              f"/var/lib/bind/db.{zone}"], capture_output=True, text=True)
        if res.returncode != 0:
            raise SetupError(f"zone {zone} does not load:\n{res.stdout}{res.stderr}")
        ok(f"zone {zone} valid")
