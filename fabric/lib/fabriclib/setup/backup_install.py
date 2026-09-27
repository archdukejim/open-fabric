import os
import subprocess
import time

from fabriclib.common.console import ok

KEEP = ["fabric/config", "stepca/data", "nginx/certs", "bind9/ssl", "keycloak/certs", "postgres/certs",
        "dirsrv/data/tls"]


def backup_install(ctx):
    """Copy what a reinstall must keep — config + secrets, the whole Step-CA
    (keys, database) and every issued certificate/key — to a root-only
    directory, preserving owners and modes (cp -a). Returns its path."""
    dest = f"/root/fabric-reinstall-{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(dest, mode=0o700)
    for rel in KEEP:
        src = ctx.path(*rel.split("/"))
        if os.path.isdir(src):
            parent = os.path.join(dest, os.path.dirname(rel))
            os.makedirs(parent, exist_ok=True)
            subprocess.run(["cp", "-a", src, parent], check=True)
    ok(f"backup: {dest}")
    return dest
