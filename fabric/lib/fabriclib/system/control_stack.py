import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.system.service_status import service_status

CONTAINERS = {"nginx": "nginx", "bind9": "bind9", "stepca": "step-ca", "ldap": "dirsrv", "postgres": "postgres",
              "keycloak": "keycloak", "webui": "webui"}


def control_stack(verb):
    """`fabricctl start|stop|restart|status`: the whole stack through
    fabric.target (every fabric unit is PartOf it). status returns
    [(unit, state, container health)] — no change is made."""
    if verb in ("start", "stop", "restart"):
        # stop: name the units too — stopping an inactive target would not
        # reach them (PartOf propagates from an active target only).
        units = [u for u, _ in service_status()] if verb == "stop" else []
        res = subprocess.run(["systemctl", verb, "fabric.target", *units], capture_output=True, text=True,
                             timeout=900)
        if res.returncode != 0:
            raise ValidationError(f"systemctl {verb} fabric.target failed: {(res.stderr or res.stdout).strip()}")
        return []
    if verb != "status":
        raise ValidationError(f"unknown action {verb!r}")
    rows = []
    target = subprocess.run(["systemctl", "is-active", "fabric.target"], capture_output=True, text=True).stdout.strip()
    rows.append(("fabric.target", target or "unknown", ""))
    for unit, state in service_status():
        health = ""
        if unit in CONTAINERS:
            health = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", CONTAINERS[unit]],
                                    capture_output=True, text=True).stdout.strip() or "no container"
        rows.append((unit, state, health))
    return rows
