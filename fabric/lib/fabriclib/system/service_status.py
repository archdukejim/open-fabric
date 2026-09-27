import os
import subprocess

SERVICES = ["nginx", "bind9", "stepca", "ldap", "postgres", "keycloak", "webui", "fabric-agent"]


def service_status():
    """[(service, state)] for every fabric service installed on this host."""
    result = []
    for svc in SERVICES:
        try:
            res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            state = res.stdout.strip() or "unknown"
        except subprocess.TimeoutExpired:
            state = "timeout"
        if state != "inactive" or os.path.exists(f"/etc/systemd/system/{svc}.service"):
            result.append((svc, state))
    return result
