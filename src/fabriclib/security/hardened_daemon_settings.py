import json
import os

DAEMON_JSON = "/etc/docker/daemon.json"

# Every container: no privilege escalation via setuid/file caps. The default
# bridge gets no inter-container traffic (fabric uses its own fabric_net).
# No userland proxy (kernel NAT only), containers survive daemon restarts,
# bounded logs so a chatty container cannot fill the SD card.
HARDENED = {
    "no-new-privileges": True,
    "icc": False,
    "userland-proxy": False,
    "live-restore": True,
    "log-driver": "json-file",
    "log-opts": {"max-size": "10m", "max-file": "3"},
}


def hardened_daemon_settings(path=DAEMON_JSON):
    """Purpose: Docker's daemon settings now and with fabric's hardening merged in (existing keys kept).
    Inputs:  path — daemon.json (default /etc/docker/daemon.json; absent counts as {}).
    Returns: (current dict, merged dict); equal when nothing would change.
    Fails:   json.JSONDecodeError on an unparseable file; OSError reading it.
    Feeds:   setup/harden_docker (writes merged), consent/plan_runtime (asks first)."""
    current = {}
    if os.path.exists(path):
        with open(path) as f:
            text = f.read().strip()
        current = json.loads(text) if text else {}
    merged = {**current, **HARDENED, "log-opts": {**current.get("log-opts", {}), **HARDENED["log-opts"]}}
    return current, merged
