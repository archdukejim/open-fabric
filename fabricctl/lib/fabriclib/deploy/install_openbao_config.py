import os

from fabriclib.common.copy_tree_with_perms import copy_tree_with_perms
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_openbao_config(paths, final_vars):
    """Purpose: OpenBao's folders (config read-only in the container, Raft data, audit log, TLS) and its config.
    Inputs:  paths — deploy_paths() (base, render); final_vars — rendered settings (service_users.openbao).
    Returns: True if the config changed (OpenBao must restart).
    Fails:   OSError from creating folders or copying.
    Feeds:   apply_deployment."""
    uid, gid = service_user(final_vars, "openbao")
    for d in ("config", "data", "logs", "certs"):
        ensure_dir(os.path.join(paths["base"], "openbao", d), 0o750, uid, gid)
    return copy_tree_with_perms(os.path.join(paths["render"], "openbao/config"),
                                os.path.join(paths["base"], "openbao/config"), uid, gid, 0o640, 0o750)
