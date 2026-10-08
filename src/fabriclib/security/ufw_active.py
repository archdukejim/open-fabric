import os
import subprocess

from fabriclib.common.keep_original import ORIGINALS


def ufw_active(config_dir=None):
    """Purpose: whether the host firewall (ufw) is on: as it was before fabric first turned it on (its record), or now.
    Inputs:  config_dir — the install's config folder: when given and fabric has recorded ufw's state from before
             its own changes (host-originals/ufw.state), that state is the answer, so the consent question does not
             change once fabric has turned ufw on; None, or no record yet: `ufw status` now (setup runs as root).
    Returns: bool; False without ufw.
    Fails:   OSError reading the record.
    Feeds:   consent/plan_firewall (what the question says), setup/configure_firewall (a decline with ufw on)."""
    record = os.path.join(config_dir, ORIGINALS, "ufw.state") if config_dir else ""
    if record and os.path.exists(record):
        return open(record).read().strip() == "active"
    try:
        out = subprocess.run(["ufw", "status"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return False
    return "Status: active" in out
