import os

from fabriclib.common.errors import ValidationError
from fabriclib.setup.uninstall import DIRS


def check_export_dir(ctx, path):
    """Purpose: decide whether an uninstall may export fabric's data to a folder: absolute, not something the
             uninstall deletes, new or empty.
    Inputs:  ctx — SetupContext with state loaded (DIRS under deploy_base, vars.openbao_key_dir); path — folder.
    Returns: the resolved real path (str).
    Fails:   ValidationError: not absolute; equal to, inside or a parent of a fabric folder, the key folder,
             /run, /usr/lib/fabricctl, /proc, /sys or /dev; "/"; exists and is not an empty folder.
    Feeds:   run_uninstall_command (checked before anything is touched, and again before export_install)."""
    if not path or not os.path.isabs(path):
        raise ValidationError("export folder: give an absolute path, e.g. /home/you/fabric-export")
    real = os.path.realpath(path)
    v = ctx.vars
    doomed = [ctx.path(d) for d in DIRS] + [v.get("openbao_key_dir") or "/etc/fabric/openbao", "/run",
                                           "/usr/lib/fabricctl", "/proc", "/sys", "/dev"]
    for d in doomed:
        d = os.path.realpath(d)
        if real == d or real.startswith(d + os.sep) or d.startswith(real + os.sep):
            raise ValidationError(f"export folder {real}: it would be deleted by the uninstall ({d})")
    if real == "/":
        raise ValidationError("export folder: not /")
    if os.path.exists(real) and (not os.path.isdir(real) or os.listdir(real)):
        raise ValidationError(f"export folder {real}: must be new or empty")
    return real
