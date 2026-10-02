import os
import subprocess

from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.ntp.chrony_settings import chrony_settings

WAIT_DROPIN = """# fabric (design ntp.md): fabric's services start after time-sync.target; never wait for it forever
# (an offline install must start)
[Service]
TimeoutStartSec=90
"""


def deploy_chrony(v, registry_path, jinja_env, root="/", manage_units=True):
    """Purpose: the host's time service (design ntp.md): chrony configured by fabric, keeping this host's clock
             and serving the network.
    Inputs:  v — vars (chrony_settings; ntp_set_clock); registry_path — config/federation.yaml (the
             upstream site's address); jinja_env — loads chrony/chrony.conf.j2; root — "/" (tests: a scratch
             tree); manage_units — systemctl calls (False in tests).
    Returns: True if chrony's configuration changed (chrony restarted when manage_units).
    Fails:   ValidationError from normalize_ntp (through chrony_settings); OSError writing; CalledProcessError from systemctl.
    Feeds:   deploy/deploy_optional_parts (every apply: the upstream site or the subnets may have changed).
    Notes:   /etc/default/chrony: -s sets the clock at start from the drift file's time when there is no RTC (a
             Pi), so it never starts in the past; -x (ntp_set_clock false) never touches the clock. systemd-timesyncd
             is stopped and disabled (chrony replaces it). chrony-wait gets a 90 s limit: services ordered after
             time-sync.target start then even offline."""
    def at(p):
        return os.path.join(root, p.lstrip("/"))

    conf = jinja_env.get_template("chrony/chrony.conf.j2").render(**chrony_settings(v, registry_path))
    opts = "-F 1 " + ("-s" if v.get("ntp_set_clock", True) else "-x")
    default = ("# fabric (design ntp.md): -s sets the clock from the drift file's time at start (no RTC); "
               "-x never sets it\n" f'DAEMON_OPTS="{opts}"\n')
    for d in ("/etc/chrony", "/etc/default", "/etc/systemd/system/chrony-wait.service.d"):
        os.makedirs(at(d), exist_ok=True)
    changed = write_file_if_changed(at("/etc/chrony/chrony.conf"), conf, 0o644)
    changed |= write_file_if_changed(at("/etc/default/chrony"), default, 0o644)
    dropin = write_file_if_changed(at("/etc/systemd/system/chrony-wait.service.d/fabric.conf"), WAIT_DROPIN, 0o644)
    if not manage_units:
        return changed
    if dropin:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "disable", "--now", "systemd-timesyncd"], capture_output=True)
    subprocess.run(["systemctl", "enable", "chrony"], check=True, capture_output=True)
    subprocess.run(["systemctl", "enable", "chrony-wait"], capture_output=True)   # absent on some releases
    subprocess.run(["systemctl", "restart" if changed else "start", "chrony"], check=True)
    return changed
