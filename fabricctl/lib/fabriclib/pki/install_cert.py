import os
import shutil


def install_cert(crt, key, root_ca, dest_dir, uid, gid, names=("fullchain.pem", "privkey.pem", "root_ca.crt")):
    """Purpose: Install a minted certificate chain, its key and the root CA into one service's
             certificate directory with the service's owner and safe modes.
    Inputs:  crt, key, root_ca — source paths; dest_dir — target directory (created 0750 if missing,
             chowned uid:gid); uid, gid — the service's user; names — target names for (crt, key, root_ca),
             default ("fullchain.pem", "privkey.pem", "root_ca.crt"); a None or "" name skips that file.
    Returns: None. Chain and root end up 0644, the key 0600, all owned uid:gid.
    Fails:   OSError (FileNotFoundError, PermissionError) from makedirs / copy / chown / chmod.
    Feeds:   setup/mint_service_certs.py (run, _install_dirsrv_tls).
    """
    os.makedirs(dest_dir, mode=0o750, exist_ok=True)
    os.chown(dest_dir, uid, gid)
    for src, name, mode in ((crt, names[0], 0o644), (key, names[1], 0o600), (root_ca, names[2], 0o644)):
        if not name:
            continue
        dst = os.path.join(dest_dir, name)
        shutil.copy2(src, dst)
        os.chown(dst, uid, gid)
        os.chmod(dst, mode)
