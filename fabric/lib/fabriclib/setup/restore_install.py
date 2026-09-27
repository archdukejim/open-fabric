import os
import subprocess

from fabriclib.common.console import ok


def restore_install(ctx, src):
    """Put a backup_install() copy back under the install root, preserving
    owners and modes, before setup runs (setup then reuses the CA,
    secrets and still-valid certificates)."""
    os.makedirs(ctx.deploy_base, exist_ok=True)
    for entry in os.listdir(src):
        subprocess.run(["cp", "-a", os.path.join(src, entry), ctx.deploy_base + os.sep], check=True)
    ok(f"restored config, CA and certificates from {src}")
