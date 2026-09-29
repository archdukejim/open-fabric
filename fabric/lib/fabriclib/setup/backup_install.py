import os
import subprocess
import time

from fabriclib.common.console import ok
from fabriclib.secrets.export_secrets import export_secrets
from fabriclib.secrets.secrets_in_openbao import secrets_in_openbao

KEEP = ["fabric/config", "stepca/data", "nginx/certs", "bind9/ssl", "keycloak/certs", "postgres/certs",
        "dirsrv/data/tls", "openbao/data", "openbao/certs"]
ROOT_DIR = "@root"          # absolute paths outside the install root (the OpenBao seal key)


def backup_install(ctx):
    """Copy what a reinstall must keep — config + secrets, the whole Step-CA
    (keys, database) and every issued certificate/key — to a root-only
    directory, preserving owners and modes (cp -a). OpenBao's data and its
    seal key (outside the install root, kept under @root/) go together: one
    is useless without the other. Returns its path."""
    dest = f"/root/fabric-reinstall-{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(dest, mode=0o700)
    for rel in KEEP:
        src = ctx.path(*rel.split("/"))
        if os.path.isdir(src):
            parent = os.path.join(dest, os.path.dirname(rel))
            os.makedirs(parent, exist_ok=True)
            subprocess.run(["cp", "-a", src, parent], check=True)
    if secrets_in_openbao(ctx.secrets_file):
        # The reinstall starts before OpenBao runs; setup reads this copy,
        # and its vault step re-imports it into OpenBao and shreds it.
        export_secrets(ctx.secrets_file, os.path.join(dest, "fabric", "config", "fabric-secrets.yml"))
    key_dir = ctx.load_state().vars.get("openbao_key_dir")
    if key_dir and os.path.isdir(key_dir):
        parent = os.path.join(dest, ROOT_DIR, os.path.dirname(key_dir).lstrip("/"))
        os.makedirs(parent, exist_ok=True)
        subprocess.run(["cp", "-a", key_dir, parent], check=True)
    ok(f"backup: {dest}")
    return dest
