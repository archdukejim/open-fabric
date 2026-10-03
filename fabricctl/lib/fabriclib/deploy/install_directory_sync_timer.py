import os
import subprocess

from fabriclib.common.copy_if_changed import copy_if_changed

SERVICE = "/etc/systemd/system/fabric-directory-sync.service"
TIMER = "/etc/systemd/system/fabric-directory-sync.timer"


def install_directory_sync_timer(paths, final_vars, manage_units=True):
    """Purpose: the timer that gives people created in Keycloak's own console their POSIX identity within 5 minutes
             (design domain-join.md step 1); removed when LDAP is off.
    Inputs:  paths — deploy_paths() (render, jinja); final_vars — rendered settings (install_ldap); manage_units —
             systemctl calls (False in tests).
    Returns: True if a unit file changed or was removed (systemd must reload).
    Fails:   OSError copying or removing; a failing systemctl is ignored (the next apply retries).
    Feeds:   deploy/apply_deployment."""
    if not final_vars.get("install_ldap", True):
        removed = False
        for unit in (TIMER, SERVICE):
            if os.path.exists(unit):
                if manage_units:
                    subprocess.run(["systemctl", "disable", "--now", os.path.basename(unit)], capture_output=True)
                os.remove(unit)
                removed = True
        return removed
    changed = copy_if_changed(os.path.join(paths["render"], "systemd", "fabric-directory-sync.service"), SERVICE, 0o644)
    changed |= copy_if_changed(os.path.join(paths["jinja"], "systemd", "fabric-directory-sync.timer"), TIMER, 0o644)
    if manage_units:
        if changed:
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=30)
        subprocess.run(["systemctl", "enable", "--now", "fabric-directory-sync.timer"], capture_output=True, timeout=30)
    return changed
