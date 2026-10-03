import os
import shutil

STAGE_DIR = "/var/tmp/fabric-reinstall-src"


def stage_source(ctx):
    """Purpose: the fabric tree setup should run from after an uninstall: a git checkout survives the
             uninstall and is used as-is; the installed copy (<deploy_base>/fabric) is deleted by it, so it is
             first copied to /var/tmp.
    Inputs:  ctx — SetupContext: source_dir (the tree this code runs from), target_dir.
    Returns: ctx.source_dir when it is outside the install; otherwise STAGE_DIR/fabric (folder 0700, re-created),
             a copy without config/, archive/ (they hold secrets and are kept by the backup) and __pycache__.
    Fails:   OSError/shutil.Error while copying.
    Feeds:   cli main (`reinstall`: its lib/fabriclib/cli.py runs setup)."""
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
