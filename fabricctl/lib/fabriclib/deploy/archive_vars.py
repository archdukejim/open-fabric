import os
import shutil
from datetime import datetime

from fabriclib.common.ensure_dir import ensure_dir


def archive_vars(target):
    """Purpose: keep the deployed vars.yaml before it is replaced.
    Inputs:  target — <deploy base>/fabric.
    Returns: the archived copy's path (<target>/archive/<stamp>-vars.yaml), or None on a first deploy.
    Fails:   OSError from creating the archive folder or copying.
    Feeds:   apply_deployment."""
    deployed = os.path.join(target, "config", "vars.yaml")
    if not os.path.exists(deployed):
        return None
    archive = os.path.join(target, "archive")
    ensure_dir(archive)
    dst = os.path.join(archive, f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-vars.yaml")
    shutil.copy(deployed, dst)
    return dst
