import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.system.service_status import service_status


def control_stack(verb):
    """Purpose: `fabricctl start|stop|restart|status`: the whole stack through fabric.target (every fabric
             unit is PartOf it).
    Inputs:  verb — "start", "stop", "restart" or "status".
    Returns: [] for start/stop/restart once systemctl succeeded; for status [(unit, state, container health)]:
             fabric.target first, then service_status() — no change is made.
    Fails:   ValidationError when systemctl fails or the verb is unknown; subprocess.TimeoutExpired after 900 s.
    Feeds:   cli main (prints the rows).
    Notes:   stop names every installed unit too: stopping an inactive target would not reach them. chrony (the
             host's time, manual 1.13.1) is shown by status but never stopped."""
    if verb in ("start", "stop", "restart"):
        # stop: name the units too — stopping an inactive target would not
        # reach them (PartOf propagates from an active target only).
        # chrony is listed for status but is the host's clock, not part of the stack: it keeps running
        units = [u for u, _, _ in service_status() if u != "chrony"] if verb == "stop" else []
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
    return rows + service_status()
