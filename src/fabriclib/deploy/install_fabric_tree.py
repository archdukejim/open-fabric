import os
import shutil

from fabriclib.common.copy_tree_with_perms import copy_tree_with_perms
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user

BASE_DIRS = ("fabric/config/certs", "nginx/www/certs", "nginx/www/shared", "nginx/www/landing", "nginx/www/manual/docs")
WEB_FOLDERS = ("certs", "shared", "landing", "manual")


def install_fabric_tree(paths, final_vars):
    """Purpose: install fabric itself and what nginx serves: the fabric tree (from a checkout), the secrets file,
             the rendered vars.yaml and link-vars.yaml, the web pages and the manual's docs.
    Inputs:  paths — deploy_paths() (fabric_dir, repo_dir, base, target, secrets, render); final_vars — rendered
             settings (service_users.nginx).
    Returns: None.
    Fails:   OSError from copying or setting owners.
    Feeds:   apply_deployment.
    Notes:   the fabric tree is copied only when this code does not run from the installed tree already. Docs come
             from a checkout (<repo>/docs) or the installed tree (<fabric>/docs), and are kept in the installed tree
             so setup and reinstall run from /opt/fabric still have them."""
    base, target, out = paths["base"], paths["target"], paths["render"]
    for d in BASE_DIRS:
        ensure_dir(os.path.join(base, d), 0o755)
    nginx_uid, nginx_gid = service_user(final_vars, "nginx")
    os.chown(os.path.join(base, "nginx/www"), nginx_uid, nginx_gid)

    if os.path.realpath(paths["fabric_dir"]) != os.path.realpath(target):
        copy_tree_with_perms(paths["fabric_dir"], target, 0, 0, 0o640, 0o750)
    sec_dst = os.path.join(target, "config/fabric-secrets.yml")
    if os.path.exists(paths["secrets"]) and os.path.realpath(paths["secrets"]) != os.path.realpath(sec_dst):
        shutil.copy2(paths["secrets"], sec_dst)
        os.chmod(sec_dst, 0o600)
    shutil.copy2(os.path.join(out, "vars.yaml"), os.path.join(target, "config/vars.yaml"))
    if os.path.exists(os.path.join(out, "link-vars.yaml")):
        shutil.copy2(os.path.join(out, "link-vars.yaml"), os.path.join(target, "config/link-vars.yaml"))
        os.chmod(os.path.join(target, "config/link-vars.yaml"), 0o644)

    for folder in WEB_FOLDERS:
        src = os.path.join(out, f"nginx/www/{folder}")
        if os.path.exists(src):
            copy_tree_with_perms(src, os.path.join(base, f"nginx/www/{folder}"), nginx_uid, nginx_gid, 0o644, 0o755)
    docs = next((d for d in (os.path.join(paths["repo_dir"], "docs"), os.path.join(paths["fabric_dir"], "docs"))
                 if os.path.isdir(d)), None)
    if docs:
        if os.path.realpath(docs) != os.path.realpath(os.path.join(target, "docs")):
            copy_tree_with_perms(docs, os.path.join(target, "docs"), 0, 0, 0o644, 0o755)
        copy_tree_with_perms(docs, os.path.join(base, "nginx/www/manual/docs"), nginx_uid, nginx_gid, 0o644, 0o755)
