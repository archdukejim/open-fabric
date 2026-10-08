import os
import subprocess

from fabriclib.common.copy_if_changed import copy_if_changed

TIMERS = ["fabric-certs"]          # fabric's scheduled jobs (the `services` consent group): renewal, 2.1.5.4


def install_timers(paths):
    """Purpose: install fabric's timers and their services, and keep them enabled.
    Inputs:  paths — deploy_paths() (jinja: the templates folder).
    Returns: True if a unit file changed (systemd reloaded here).
    Fails:   OSError copying the files; systemctl failures are not raised (a host without systemd running, such as
             a render test, keeps the files).
    Feeds:   apply_deployment."""
    changed = False
    for name in TIMERS:
        for kind in ("service", "timer"):
            changed |= bool(copy_if_changed(os.path.join(paths["jinja"], "systemd", f"{name}.{kind}"),
                                            f"/etc/systemd/system/{name}.{kind}", 0o644))
    if changed:
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    for name in TIMERS:
        subprocess.run(["systemctl", "enable", "--now", f"{name}.timer"], capture_output=True)
    return changed
