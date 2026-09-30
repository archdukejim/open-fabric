import os

from fabriclib.common.write_file_if_changed import write_file_if_changed

CONFIG_FILES = ["radiusd.conf", "clients.conf", "fabric-radius.json", "mods/always", "mods/eap", "mods/fabric_policy",
                "sites/fabric", "sites/check-eap-tls"]


def deploy_freeradius(v, secrets, jinja_env):
    """FreeRADIUS's files under <deploy_base>/freeradius: the configuration
    (config/, root:freerad 0640 — clients.conf holds the RADIUS secrets,
    ldap-password the directory account's) and fabric's policy code
    (python/). The certificates (certs/: server.pem, server.key, and ca.pem,
    the fabric CA that client certificates and 389-DS must chain to) come
    from setup's certificate step. Returns True if anything changed."""
    base = os.path.join(v["deploy_base_dir"], "freeradius")
    gid = int(v["service_users"]["freeradius"]["gid"])
    uid = int(v["service_users"]["freeradius"]["uid"])
    for sub, owner in (("config", (0, gid)), ("config/mods", (0, gid)), ("config/sites", (0, gid)),
                       ("python", (0, gid)), ("certs", (uid, gid))):
        path = os.path.join(base, sub)
        os.makedirs(path, mode=0o750, exist_ok=True)
        os.chown(path, *owner)
        os.chmod(path, 0o750)
    ctx = {**v, "radius_secrets": secrets.get("radius_secrets") or {}}
    changed = False
    for name in CONFIG_FILES:
        text = jinja_env.get_template(f"freeradius/config/{name}.j2").render(**ctx)
        changed |= write_file_if_changed(os.path.join(base, "config", name), text, 0o640, 0, gid)
    changed |= write_file_if_changed(os.path.join(base, "config", "ldap-password"),
                                     secrets.get("ldap_radius_password", "") + "\n", 0o640, 0, gid)
    src = os.path.join(jinja_env.loader.searchpath[0], "freeradius", "python")
    for name in sorted(os.listdir(src)):
        if name.endswith(".py"):
            changed |= write_file_if_changed(os.path.join(base, "python", name),
                                             open(os.path.join(src, name)).read(), 0o640, 0, gid)
    return changed
