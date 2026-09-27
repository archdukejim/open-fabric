import os
import subprocess
import time

from fabriclib.common.console import info, ok
from fabriclib.common.wait_healthy import wait_healthy
from fabriclib.setup.errors import SetupError

# (systemd unit, container, enabled-if flag); order = start order
ORDER = [("bind9", "bind9", None), ("stepca", "step-ca", None), ("ldap", "dirsrv", "install_ldap"),
         ("postgres", "postgres", "install_keycloak"), ("keycloak", "keycloak", "install_keycloak"),
         ("nginx", "nginx", None)]


def _start(unit, container, restart):
    active = subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0
    if active and not restart:
        return "running"
    subprocess.run(["systemctl", "enable", unit], check=True, capture_output=True)
    subprocess.run(["systemctl", "restart" if active else "start", unit], check=True)
    healthy, why = wait_healthy(container, timeout=900)
    if not healthy:
        logs = subprocess.run(["docker", "logs", "--tail", "40", container], capture_output=True, text=True)
        raise SetupError(f"{container} did not become healthy ({why}):\n{logs.stdout}{logs.stderr}")
    return "restarted" if active else "started"


def run(ctx):
    """Start the stack in dependency order (local image layers build on first
    start), seed 389-DS, configure Keycloak, then fabric-agent and the web UI."""
    v, lib = ctx.vars, os.path.join(ctx.target_dir, "lib")
    for unit, container, flag in ORDER:
        if flag and not v.get(flag, flag == "install_ldap"):
            continue
        info(f"{unit}…")
        ok(f"{unit}: {_start(unit, container, unit in ctx.restart_services)}")

    if v.get("install_ldap", True):
        res = subprocess.run(["bash", os.path.join(lib, "dirsrv.sh"), "seed"], capture_output=True, text=True)
        if res.returncode != 0:
            raise SetupError(f"389-DS seeding failed:\n{res.stdout}{res.stderr}")
        ok("389-DS seeded (" + (res.stdout.strip().splitlines() or ["?"])[-1] + ")")

    if v.get("install_keycloak"):
        for attempt in range(6):
            res = subprocess.run(["python3", os.path.join(lib, "keycloak_bootstrap.py"),
                                  "--vars", ctx.vars_file, "--secrets", ctx.secrets_file],
                                 capture_output=True, text=True)
            if res.returncode == 0:
                break
            time.sleep(15)
        else:
            raise SetupError(f"Keycloak configuration failed:\n{res.stdout}{res.stderr}")
        ok("Keycloak configured (realm, LDAP federation" + (", web UI client, TOTP)" if v.get("install_webui") else ")"))

    if v.get("install_webui"):
        subprocess.run(["systemctl", "enable", "--now", "fabric-agent"], check=True, capture_output=True)
        if "fabric-agent" in ctx.restart_services:
            subprocess.run(["systemctl", "restart", "fabric-agent"], check=True)
        ok(f"fabric-agent: {'restarted' if 'fabric-agent' in ctx.restart_services else 'running'}")
        ok(f"webui: {_start('webui', 'webui', 'webui' in ctx.restart_services)}")
