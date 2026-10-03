import os
import shutil

ORIGINALS = "host-originals"     # under the install's config folder: <config>/host-originals/<path on the host>


def keep_original(path, config_dir, marker=None):
    """Purpose: keep a copy of a host file as it was before fabric first changes it, so `fabricctl setup --undo` and
             uninstall can put it back (manual 2.7.1.5).
    Inputs:  path — the host file about to change (absolute); config_dir — the install's config folder (None: keep
             nothing, e.g. tests on a scratch tree); marker — text that marks the file as fabric's own (its first
             line): a file holding it is not an original (an install set up before originals were kept).
    Returns: True when a record was made now: a copy, a ".link" file with a symlink's target, or an ".absent" file
             when the path did not exist; False when a record exists already (only the first is kept), config_dir
             is None or the file is fabric's own.
    Fails:   OSError reading the file or writing the record.
    Feeds:   setup/harden_docker, setup/configure_firewall (ufw's state), setup/configure_network,
             ntp/deploy_chrony; undone by common/restore_original."""
    if not config_dir:
        return False
    store = os.path.join(config_dir, ORIGINALS, path.lstrip("/"))
    if any(os.path.lexists(store + s) for s in ("", ".link", ".absent")):
        return False
    if marker and os.path.isfile(path) and not os.path.islink(path):
        with open(path, errors="replace") as f:
            if marker in f.read():
                return False
    os.makedirs(os.path.dirname(store), mode=0o700, exist_ok=True)
    if os.path.islink(path):
        with open(store + ".link", "w") as f:
            f.write(os.readlink(path))
    elif os.path.exists(path):
        shutil.copy2(path, store)
    else:
        open(store + ".absent", "w").close()
    return True
