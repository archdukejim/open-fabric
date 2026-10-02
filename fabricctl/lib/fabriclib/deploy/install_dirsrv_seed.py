import os

from fabriclib.common.copy_tree_with_perms import copy_tree_with_perms
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_dirsrv_seed(paths, final_vars):
    """Purpose: 389-DS's data folder and its seed files (applied by dirsrv.sh seed when they change).
    Inputs:  paths — deploy_paths() (base, render); final_vars — rendered settings (install_ldap,
             service_users.ldap).
    Returns: True if a seed file changed; False when they did not or LDAP is off.
    Fails:   OSError from creating folders or copying.
    Feeds:   apply_deployment.
    Notes:   group-readable by the container user only: 20-accounts.ldif holds role-account passwords."""
    if not final_vars.get("install_ldap"):
        return False
    uid, gid = service_user(final_vars, "ldap")
    ensure_dir(os.path.join(paths["base"], "dirsrv/data"), 0o750, uid, gid)
    return copy_tree_with_perms(os.path.join(paths["render"], "dirsrv/seed"), os.path.join(paths["base"], "dirsrv/seed"),
                                0, gid, 0o640, 0o750)
