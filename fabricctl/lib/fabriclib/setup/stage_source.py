import os
import shutil

STAGE_DIR = "/var/tmp/fabric-reinstall-src"


def stage_source(ctx):
    """Return the fabric/ tree setup should run from after an uninstall.

    A git checkout survives uninstall and is used as-is. The installed copy
    (<deploy_base>/fabric, docs included) is deleted by uninstall, so it is
    first copied to /var/tmp."""
    src = os.path.realpath(ctx.source_dir)
    if not src.startswith(os.path.realpath(ctx.target_dir) + os.sep) and src != os.path.realpath(ctx.target_dir):
        return ctx.source_dir
    shutil.rmtree(STAGE_DIR, ignore_errors=True)
    os.makedirs(STAGE_DIR, mode=0o700)
    staged = os.path.join(STAGE_DIR, "fabric")
    # Only the code: config/ and archive/ hold secrets and are kept by the backup.
    shutil.copytree(src, staged, symlinks=True,
                    ignore=lambda d, names: [n for n in names if d == src and n in ("config", "archive")]
                    + [n for n in names if n == "__pycache__"])
    return staged
