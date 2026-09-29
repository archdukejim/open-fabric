import os
import subprocess

from fabriclib.common.console import ok
from fabriclib.setup.backup_install import ROOT_DIR


def restore_install(ctx, src):
    """Put a backup_install() copy back under the install root, preserving
    owners and modes, before setup runs (setup then reuses the CA,
    secrets and still-valid certificates)."""
    os.makedirs(ctx.deploy_base, exist_ok=True)
    for entry in os.listdir(src):
        if entry == ROOT_DIR:           # absolute paths (the OpenBao seal key directory)
            subprocess.run(["cp", "-a", os.path.join(src, entry) + "/.", "/"], check=True)
            continue
        subprocess.run(["cp", "-a", os.path.join(src, entry), ctx.deploy_base + os.sep], check=True)
    ok(f"restored config, CA and certificates from {src}")
