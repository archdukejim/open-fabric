import os
import subprocess
import time

from fabriclib.common.console import info, ok
from fabriclib.setup.errors import SetupError
from fabriclib.setup.start_unit import start_unit

# (systemd unit, container, enabled-if flag); order = start order
ORDER = [("bind9", "bind9", None), ("stepca", "step-ca", None), ("ldap", "dirsrv", "install_ldap"),
         ("postgres", "postgres", "install_keycloak"), ("keycloak", "keycloak", "install_keycloak"),
         ("nginx", "nginx", None)]


def run(ctx):
    """Start the stack in dependency order (local image layers build on first
    start), seed 389-DS, configure Keycloak, then fabric-agent and the web UI."""
    v, lib = ctx.vars, os.path.join(ctx.target_dir, "lib")
    # fabric.target groups every unit: systemctl start|stop|restart fabric.target
    subprocess.run(["systemctl", "enable", "fabric.target"], check=True, capture_output=True)
    for unit, container, flag in ORDER:
        if flag and not v.get(flag, flag == "install_ldap"):
            continue
        info(f"{unit}…")
        ok(f"{unit}: {start_unit(unit, container, unit in ctx.restart_services)}")

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
        ok(f"webui: {start_unit('webui', 'webui', 'webui' in ctx.restart_services)}")

    # Everything is up: activate the target now (it is enabled for boot), so
    # `fabricctl stop|restart` / `systemctl ... fabric.target` reach every unit.
    subprocess.run(["systemctl", "start", "fabric.target"], check=True, capture_output=True)
    ok("fabric.target active (systemctl status fabric.target)")
