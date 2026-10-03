import os

from fabriclib.common.copy_tree_with_perms import copy_tree_with_perms
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_stepca_templates(paths, final_vars):
    """Purpose: Step-CA's data folder and its certificate templates (leaf, sub-CA).
    Inputs:  paths — deploy_paths() (base, render); final_vars — rendered settings (service_users.step).
    Returns: True if a template changed (Step-CA must restart).
    Fails:   OSError from creating folders or copying.
    Feeds:   apply_deployment."""
    uid, gid = service_user(final_vars, "step")
    ensure_dir(os.path.join(paths["base"], "stepca/data"), 0o750, uid, gid)
    if not os.path.exists(os.path.join(paths["render"], "stepca/templates/certs")):
        return False
    return copy_tree_with_perms(os.path.join(paths["render"], "stepca/templates"),
                                os.path.join(paths["base"], "stepca/data/templates"), uid, gid, 0o640, 0o750)
