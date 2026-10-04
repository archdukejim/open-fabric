import os

from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.write_file_if_changed import write_file_if_changed


def deploy_samba(v, secrets, jinja_env):
    """Purpose: write the domain controller's files under <deploy_base>/samba during apply (manual 2.11.2): the
             Administrator's password for provisioning and the code that converges the domain inside the DC.
    Inputs:  v — the rendered vars: deploy_base_dir. secrets — fabric's secrets (ad_admin_password).
             jinja_env — Jinja environment whose first search path holds samba/converge/*.py (an install) or sits
             beside src/containers/samba (a checkout).
    Returns: True if the converge code changed. (The password file is read only when the domain is provisioned:
             a change to it changes nothing in a running domain.)
    Fails:   KeyError without ad_admin_password; OSError from creating, owning or writing.
    Feeds:   deploy/deploy_optional_parts (apply); tests/samba.
    Notes:   every folder is root-only (the DC runs as root in its container): data/ (the domain's database and
             SYSVOL), secrets/, tls/ (filled by setup's certificate step), converge/ (read-only in the container)."""
    base = os.path.join(v["deploy_base_dir"], "samba")
    for sub in ("data", "secrets", "tls", "converge"):
        ensure_dir(os.path.join(base, sub), 0o700, 0, 0)
    write_file_if_changed(os.path.join(base, "secrets", "admin_password"), secrets["ad_admin_password"] + "\n", 0o600)
    src = os.path.join(jinja_env.loader.searchpath[0], "samba", "converge")
    if not os.path.isdir(src):              # a checkout: the converge code lives in src/containers/ (manual 1.3.2)
        src = os.path.join(os.path.dirname(jinja_env.loader.searchpath[0]), "src", "containers", "samba")
    converge = False
    for name in sorted(os.listdir(src)):
        if name.endswith(".py"):
            converge |= write_file_if_changed(os.path.join(base, "converge", name),
                                              open(os.path.join(src, name)).read(), 0o600)
    return converge
