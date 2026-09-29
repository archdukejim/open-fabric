import os

from fabriclib.common.errors import ValidationError
from fabriclib.setup.uninstall import DIRS


def check_export_dir(ctx, path):
    """Where an uninstall may export fabric's data: an absolute path that
    the uninstall will not delete (not under a fabric directory, the vault
    key folder or /run) and that is new or empty. Returns the resolved path."""
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
