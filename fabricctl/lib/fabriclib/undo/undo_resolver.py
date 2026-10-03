import os
import subprocess

from fabriclib.common.restore_original import restore_original
from fabriclib.setup.configure_network import RESOLVED_DROPIN

STUB = "/run/systemd/resolve/stub-resolv.conf"     # Ubuntu's own /etc/resolv.conf link


def undo_resolver(config_dir):
    """Purpose: undo the `resolver` host change (design host-consent.md §4): systemd-resolved's stub listener back
             and /etc/resolv.conf as it was.
    Inputs:  config_dir — the install's config folder (the kept copies: common/keep_original).
    Returns: list of str, what was done (empty when fabric never changed the resolver).
    Fails:   OSError on the files; a failing systemctl is ignored.
    Feeds:   setup/uninstall; undo/undo_group (`fabricctl setup --undo resolver`, once use_host_dns is true: BIND
             no longer needs port 53)."""
    if not os.path.exists(RESOLVED_DROPIN):
        return []
    os.remove(RESOLVED_DROPIN)
    restore_original(RESOLVED_DROPIN, config_dir)          # its record said it was absent: nothing more to do
    done = [f"{RESOLVED_DROPIN} removed (the stub listener is back)"]
    how = restore_original("/etc/resolv.conf", config_dir)
    if how is None:                                       # no copy kept: Ubuntu's default link
        if os.path.lexists("/etc/resolv.conf"):
            os.remove("/etc/resolv.conf")
        os.symlink(STUB, "/etc/resolv.conf")
        how = f"linked to {STUB}"
    done.append(f"/etc/resolv.conf {'put back as it was' if how == 'restored' else how}")
    subprocess.run(["systemctl", "restart", "systemd-resolved"], capture_output=True)
    done.append("systemd-resolved restarted")
    return done
