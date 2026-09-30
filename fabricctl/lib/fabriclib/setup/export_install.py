import os
import subprocess
import time

from fabriclib.common.console import info, ok
from fabriclib.secrets.export_secrets import export_secrets
from fabriclib.secrets.secrets_in_openbao import secrets_in_openbao
from fabriclib.setup.uninstall import DIRS

ROOT_DIR = "@root"          # absolute paths outside the install root (the vault key folder, external data)

README = """fabric export — {host}, {when}

Everything fabric had on this host, copied with owners and modes kept
(cp -a) while the stack was stopped, so databases are consistent:

  fabric/            config, vars.yaml, audit log; fabric-secrets.yml = fabric's
                     own secrets exported from OpenBao (PLAINTEXT)
  stepca/            the CA: root + intermediate keys, database
  openbao/           OpenBao's data (your apps/ secrets, encrypted)
  @root/…            OpenBao's vault key and unlock methods — with openbao/ this
                     OPENS THE VAULT
  dirsrv/            389 Directory Server: users, groups, devices, device roles
  keycloak/, postgres/  Keycloak and its database (TOTP enrolments, sessions)
  bind9/, nginx/, webui/  zones, TSIG material, certificates

Whoever has this folder has your CA and your vault. Keep it root-only and
offline; delete it when you no longer need it.
"""


def _copy(src, dest_parent):
    os.makedirs(dest_parent, exist_ok=True)
    subprocess.run(["cp", "-a", src, dest_parent], check=True)


def export_install(ctx, dest):
    """Export all of fabric's data before an uninstall, to `dest` (checked
    by check_export_dir): fabric's secrets out of OpenBao while it runs,
    then the stack is stopped and every fabric folder, the vault key folder
    and any data folder outside the install root are copied cold. `dest`
    is root 0700. Returns it."""
    os.makedirs(dest, mode=0o700, exist_ok=True)
    os.chown(dest, 0, 0)
    os.chmod(dest, 0o700)
    v = ctx.vars
    secrets = os.path.join(dest, "fabric", "config", "fabric-secrets.yml")
    if secrets_in_openbao(ctx.secrets_file):
        os.makedirs(os.path.dirname(secrets), mode=0o700, exist_ok=True)
        export_secrets(ctx.secrets_file, secrets)
    info("stopping fabric for a consistent copy")
    subprocess.run(["systemctl", "stop", "fabric.target", "fabric-agent"], capture_output=True)
    for name in DIRS:
        if os.path.isdir(ctx.path(name)):
            _copy(ctx.path(name), dest)
    outside = [v.get("openbao_key_dir")] + [v.get(k) for k in ("keycloak_data_dir", "postgres_data_dir")]
    for path in outside:
        if path and os.path.isdir(path) and not path.startswith(ctx.deploy_base + os.sep):
            _copy(path, os.path.join(dest, ROOT_DIR, os.path.dirname(path).lstrip("/")))
    with open(os.path.join(dest, "README.txt"), "w") as f:
        f.write(README.format(host=v.get("hostname") or "?", when=time.strftime("%Y-%m-%d %H:%M")))
    size = subprocess.run(["du", "-sh", dest], capture_output=True, text=True).stdout.split("\t")[0]
    ok(f"exported to {dest} ({size}, root only)")
    return dest
