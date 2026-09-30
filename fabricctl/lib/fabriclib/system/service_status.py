import os
import subprocess

SERVICES = ["nginx", "bind9", "stepca", "ldap", "postgres", "keycloak", "openbao", "kea", "freeradius",
            "fluentbit", "fabric-web", "fabric-agent"]
# systemd unit -> its container (units without one run on the host)
CONTAINERS = {"nginx": "nginx", "bind9": "bind9", "stepca": "step-ca", "ldap": "dirsrv", "postgres": "postgres",
              "keycloak": "keycloak", "openbao": "openbao", "kea": "kea-dhcp4", "freeradius": "freeradius",
              "fluentbit": "fluentbit", "fabric-web": "fabric-web"}


def _health(container):
    try:
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
                             capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        return "timeout"
    return res.stdout.strip() or "no container"


def service_status():
    """[(service, systemd state, container health)] for every fabric service
    installed on this host; health is '' for host services."""
    result = []
    for svc in SERVICES:
        try:
            res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            state = res.stdout.strip() or "unknown"
        except subprocess.TimeoutExpired:
            state = "timeout"
        if state != "inactive" or os.path.exists(f"/etc/systemd/system/{svc}.service"):
            result.append((svc, state, _health(CONTAINERS[svc]) if svc in CONTAINERS else ""))
    return result
