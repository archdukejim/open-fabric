import os
import subprocess

from fabriclib.common.keep_original import ORIGINALS
from fabriclib.security.ufw_rule import RECORDS, ufw_rule

UNIT = "/etc/systemd/system/fabric-firewall.service"


def undo_firewall(config_dir):
    """Purpose: undo the `firewall` host change (manual 2.7.1.5): the ufw rules fabric added, its
             DOCKER-USER rules and their boot unit; ufw switched off again if it was off before fabric.
    Inputs:  config_dir — the install's config folder: the records of what fabric opened (security/ufw_rule RECORDS)
             and whether ufw was on before (<config>/host-originals/ufw.state).
    Returns: list of str, what was done and what was left (ufw's default policy is left as it is).
    Fails:   OSError removing the unit or the records; command failures (ufw, systemctl, iptables) are ignored:
             a rule may be gone already.
    Feeds:   undo/undo_group (`fabricctl setup --undo firewall`), setup/uninstall."""
    done = []
    for kind, name in RECORDS.items():
        record = os.path.join(config_dir, name)
        if not os.path.exists(record):
            continue
        for x in open(record).read().split():
            subprocess.run(["ufw", "delete", "allow", *ufw_rule(kind, x)], capture_output=True)
            done.append(f"ufw: fabric's {kind} rule for {x} removed")
        os.remove(record)
    if os.path.exists(UNIT):
        subprocess.run(["systemctl", "disable", "--now", "fabric-firewall"], capture_output=True)
        os.remove(UNIT)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        done.append("fabric-firewall.service removed")
    if subprocess.run(["iptables", "-n", "-L", "DOCKER-USER"], capture_output=True).returncode == 0:
        subprocess.run(["iptables", "-F", "DOCKER-USER"], capture_output=True)
        subprocess.run(["iptables", "-A", "DOCKER-USER", "-j", "RETURN"], capture_output=True)
        done.append("DOCKER-USER: fabric's rules removed (published ports follow Docker's defaults again)")
    state = os.path.join(config_dir, ORIGINALS, "ufw.state")
    before = open(state).read().strip() if os.path.exists(state) else ""
    if before == "inactive":
        subprocess.run(["ufw", "--force", "disable"], capture_output=True)
        done.append("ufw switched off (it was off before fabric)")
    else:
        done.append("ufw stays on with its default policy" + (" (it was on before fabric)" if before else
                                                                "; `sudo ufw disable` if you no longer want it"))
    if before:
        os.remove(state)
    return done
