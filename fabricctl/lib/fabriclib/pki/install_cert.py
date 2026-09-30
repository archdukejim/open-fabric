import os
import shutil


def install_cert(crt, key, root_ca, dest_dir, uid, gid, names=("fullchain.pem", "privkey.pem", "root_ca.crt")):
    """Copy a minted chain, key and the root CA into dest_dir for one service:
    chain/root 0644, key 0600, all owned by the service's uid/gid."""
    os.makedirs(dest_dir, mode=0o750, exist_ok=True)
    os.chown(dest_dir, uid, gid)
    for src, name, mode in ((crt, names[0], 0o644), (key, names[1], 0o600), (root_ca, names[2], 0o644)):
        if not name:
            continue
        dst = os.path.join(dest_dir, name)
        shutil.copy2(src, dst)
        os.chown(dst, uid, gid)
        os.chmod(dst, mode)
