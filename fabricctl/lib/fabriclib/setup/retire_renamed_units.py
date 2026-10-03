import os
import subprocess

# old systemd unit -> its old container (renamed since: webui -> fabric-web)
RENAMED = {"webui": "webui"}


def retire_renamed_units():
    """Purpose: upgrade step: stop, disable and remove units and containers that were renamed (webui is now
             fabric-web), so the old one never runs next to the new one or holds its socket.
    Inputs:  none (RENAMED; /etc/systemd/system/<unit>.service).
    Returns: list of unit names retired ([] when none was installed). Idempotent.
    Fails:   OSError removing the unit file; systemctl/docker failures are ignored.
    Feeds:   start_services.run (logs each)."""
    retired = []
    for unit, container in RENAMED.items():
        path = f"/etc/systemd/system/{unit}.service"
        if not os.path.exists(path):
            continue
        subprocess.run(["systemctl", "disable", "--now", unit], capture_output=True)
        os.remove(path)
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        retired.append(unit)
    if retired:
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    return retired
