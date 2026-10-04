import os
import subprocess

from fabriclib.common.restore_original import restore_original

FILES = ("/etc/chrony/chrony.conf", "/etc/default/chrony", "/etc/systemd/system/chrony-wait.service.d/fabric.conf")


def undo_time(config_dir, manage_units=True):
    """Purpose: undo the `time` host change (manual 2.7.1.5): chrony's files as they were before fabric
             first wrote them, chrony restarted.
    Inputs:  config_dir — the install's config folder (the kept copies: common/keep_original); manage_units —
             systemctl calls (False in tests).
    Returns: list of str, what was done and what could not be (no copy kept: an install set up before copies were
             kept keeps fabric's file, said so).
    Fails:   OSError writing a file; a failing systemctl is ignored (chrony may be gone).
    Feeds:   undo/undo_group (`fabricctl setup --undo time`), setup/uninstall."""
    done, changed = [], False
    for path in FILES:
        how = restore_original(path, config_dir)
        if how:
            changed = True
            done.append(f"{path}: {'put back as it was' if how == 'restored' else 'removed (fabric added it)'}")
        elif path.endswith("fabric.conf") and os.path.exists(path):
            os.remove(path)
            changed = True
            done.append(f"{path} removed")
        elif os.path.exists(path):
            done.append(f"{path}: kept as fabric wrote it (no copy of the earlier file was kept); edit it if needed")
    if changed and manage_units:
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "restart", "chrony"], capture_output=True)
        done.append("chrony restarted")
    return done
