import json
import os
import subprocess
import time

from fabriclib.common.console import info, ok, warn
from fabriclib.setup.errors import SetupError

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


def run(ctx):
    """Purpose: merge the HARDENED settings into /etc/docker/daemon.json (existing keys kept) and restart Docker
             if anything changed.
    Inputs:  ctx — SetupContext: vars security.docker_daemon_hardening (default True). Reads DAEMON_JSON.
    Returns: None; daemon.json converged and Docker restarted only when it changed. With the setting false it
             only warns — settings written earlier are not removed.
    Fails:   json.JSONDecodeError on an unparseable daemon.json; CalledProcessError from `systemctl restart
             docker`; SetupError when Docker does not answer `docker info` within about 60 s; AttributeError
             if vars `security` is null.
    Feeds:   setup step `docker`, run by run_setup via STEPS.
    Notes:   no-new-privileges, no icc on the default bridge, no userland proxy, live-restore, bounded logs."""
    if not ctx.vars.get("security", {}).get("docker_daemon_hardening", True):
        warn("Docker daemon hardening disabled (security.docker_daemon_hardening: false)")
        return
    current = {}
    if os.path.exists(DAEMON_JSON):
        with open(DAEMON_JSON) as f:
            text = f.read().strip()
        current = json.loads(text) if text else {}
    merged = {**current, **HARDENED, "log-opts": {**current.get("log-opts", {}), **HARDENED["log-opts"]}}
    if merged == current:
        ok("Docker daemon already hardened")
        return
    os.makedirs(os.path.dirname(DAEMON_JSON), exist_ok=True)
    with open(DAEMON_JSON, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    info("restarting Docker to apply daemon settings (live-restore keeps containers running from now on)")
    subprocess.run(["systemctl", "restart", "docker"], check=True)
    for _ in range(12):
        if subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
            ok("Docker daemon hardened: " + ", ".join(k for k in HARDENED if k != "log-driver"))
            return
        time.sleep(5)
    raise SetupError(f"Docker did not come back after applying {DAEMON_JSON}; check `journalctl -u docker`")
