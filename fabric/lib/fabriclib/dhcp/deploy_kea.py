import os

from fabriclib.dhcp.ensure_ddns_zone import ensure_ddns_zone


def _write(path, text, mode, uid=0, gid=0):
    if os.path.exists(path) and open(path).read() == text:
        return False
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(path + ".tmp", uid, gid)
    os.replace(path + ".tmp", path)
    return True


def deploy_kea(v, secrets, jinja_env, bind_uid, bind_gid):
    """Kea's files under <deploy_base>/kea: kea-dhcp4.conf and
    kea-dhcp-ddns.conf (root:kea 0640 — the DDNS one holds the TSIG
    secret), the lease folder and the control-socket folder; and the DHCP
    subzone's file, created once. `v` must hold the normalised `dhcp`.
    Returns True if Kea's configuration changed."""
    base = os.path.join(v["deploy_base_dir"], "kea")
    kgid = int(v["service_users"]["kea"]["gid"])
    for sub, mode, owner in (("config", 0o750, (0, kgid)), ("leases", 0o750, (0, 0)), ("run", 0o750, (0, 0))):
        path = os.path.join(base, sub)
        os.makedirs(path, mode=mode, exist_ok=True)
        os.chown(path, *owner)
        os.chmod(path, mode)
    ctx = {**v, "kea_ddns_secret": secrets.get("kea_ddns_secret", "")}
    changed = False
    for name in ("kea-dhcp4.conf", "kea-dhcp-ddns.conf"):
        text = jinja_env.get_template(f"kea/{name}.j2").render(**ctx)
        changed |= _write(os.path.join(base, "config", name), text, 0o640, 0, kgid)
    if (v.get("dhcp") or {}).get("ddns", True):
        ensure_ddns_zone(v, bind_uid, bind_gid)
    return changed
