import os

from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.samba.write_bind_dlz import write_bind_dlz


def deploy_samba(v, secrets, jinja_env):
    """Purpose: write the domain controller's files under <deploy_base>/samba during apply (manual 2.11.2): the
             Administrator's password for provisioning and the code that converges the domain inside the DC.
    Inputs:  v — the rendered vars: deploy_base_dir, host_ip, ad_domain. secrets — fabric's secrets
             (ad_admin_password).
             jinja_env — Jinja environment whose first search path holds samba/converge/*.py (an install) or sits
             beside src/containers/samba (a checkout).
    Returns: {"converge": True if the converge code changed, "restart": True if the DC's resolv.conf changed}.
             (The password file is read only when the domain is provisioned: a change to it changes nothing in a
             running domain.) BIND's DLZ files are written when missing, so BIND
             can start; turning DLZ on (and restarting BIND) happens after the domain is converged.
    Fails:   KeyError without ad_admin_password; OSError from creating, owning or writing.
    Feeds:   deploy/deploy_optional_parts (apply); tests/samba.
    Notes:   every folder is root-only (the DC runs as root in its container): data/ (the domain's database and
             SYSVOL; its etc/ and bind-dns/ are mounted into BIND), secrets/, tls/ (filled by setup's certificate
             step), converge/ (read-only in the container); bind/ is BIND's (write_bind_dlz); resolv.conf (the DC's
             resolver, mounted read-only)."""
    base = os.path.join(v["deploy_base_dir"], "samba")
    for sub in ("data", "secrets", "tls", "converge"):
        ensure_dir(os.path.join(base, sub), 0o700, 0, 0)
    # BIND mounts these two (its DLZ): made once if missing, never reset — provisioning gives them BIND's group
    for sub in ("etc", "bind-dns"):
        os.makedirs(os.path.join(base, "data", sub), mode=0o755, exist_ok=True)
    # BIND includes these when it starts: they must exist; turning DLZ on is for after the domain is converged
    if not os.path.exists(os.path.join(base, "bind", "dlz.conf")):
        write_bind_dlz(v)
    write_file_if_changed(os.path.join(base, "secrets", "admin_password"), secrets["ad_admin_password"] + "\n", 0o600)
    # the DC's own resolver: the host's address (BIND, or the DNS filter in front of it), which knows the AD zone —
    # in the host network it would otherwise use the host's resolver, which may not (use_host_dns), and then cannot
    # find its own KDC or send its signed updates
    restart = write_file_if_changed(os.path.join(base, "resolv.conf"),
                                    f"nameserver {v['host_ip']}\nsearch {v['ad_domain']}\n", 0o644)
    src = os.path.join(jinja_env.loader.searchpath[0], "samba", "converge")
    if not os.path.isdir(src):              # a checkout: the converge code lives in src/containers/ (manual 1.3.2)
        src = os.path.join(os.path.dirname(jinja_env.loader.searchpath[0]), "src", "containers", "samba")
    converge = False
    for name in sorted(os.listdir(src)):
        if name.endswith(".py"):
            converge |= write_file_if_changed(os.path.join(base, "converge", name),
                                              open(os.path.join(src, name)).read(), 0o600)
    return {"converge": converge, "restart": restart}
