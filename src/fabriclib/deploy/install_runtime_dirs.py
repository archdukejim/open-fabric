import os
import shutil

from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_runtime_dirs(paths, final_vars, tsig_keys):
    """Purpose: the data folders services write (owned by them) and each TSIG key's RFC2136 client settings.
    Inputs:  paths — deploy_paths() (base, render); final_vars — rendered settings (install_keycloak,
             postgres_data_dir, keycloak_data_dir, service_users); tsig_keys — normalized keys (name, out).
    Returns: None. bind9 data/log/cache; Postgres and Keycloak data with
             Keycloak; <out or base/<key>/rfc2136.ini> 0600 root for each key (certbot-style DNS-01 clients).
    Fails:   OSError from creating folders or copying.
    Feeds:   apply_deployment."""
    base = paths["base"]
    for rel, user, wanted in (("bind9/data", "bind", True), ("bind9/log", "bind", True), ("bind9/cache", "bind", True)):
        if wanted:
            ensure_dir(os.path.join(base, rel), 0o750, *service_user(final_vars, user))
    if final_vars.get("install_keycloak"):
        ensure_dir(final_vars.get("postgres_data_dir", os.path.join(base, "postgres/data")), 0o750,
                   *service_user(final_vars, "postgres"))
        ensure_dir(final_vars.get("keycloak_data_dir", os.path.join(base, "keycloak/data")), 0o750,
                   *service_user(final_vars, "keycloak"))
    for key in tsig_keys:
        src = os.path.join(paths["render"], "rfc2136", key["name"], "rfc2136.ini")
        dst = key.get("out") or os.path.join(base, key["name"], "rfc2136.ini")
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), mode=0o700, exist_ok=True)
            shutil.copy2(src, dst)
            os.chown(dst, 0, 0)
            os.chmod(dst, 0o600)
