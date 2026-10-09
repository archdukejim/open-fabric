import os

from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user
from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.dns_filter.common.filter_zones import filter_zones
from fabriclib.dns_filter.common.list_zone import list_zone
from fabriclib.dns_filter.common.resolver_paths import resolver_paths
from fabriclib.dns_filter.common.resolver_rndc import resolver_rndc
from fabriclib.dns_filter.update_lists import update_lists

CONFIG = ("named.conf", "fabric.rpz", "owner.rpz", "rndc.key")


def deploy_resolver(v, secrets, links, jinja_env, fetch=True):
    """Purpose: the BIND resolver's deploy step (manual 1.12.2.10): its folders, its configuration and rules zones
             (fabric's zones never filtered, the owner's allows and blocks), its control key; each list with no
             converted copy yet is fetched first, so the configuration only names lists that exist; converted
             lists no longer in the settings are removed; a running resolver reloads what changed.
    Inputs:  v — rendered vars: deploy_base_dir, service_users.resolver, ip_bind9, lan_cidr, fabric_subnet,
             security.firewall_allow, dns_filter_lists, dns_filter_allow, dns_filter_block, dns_filter_upstreams and
             what filter_zones reads; secrets — resolver_rndc_secret; links — dns_links' result (the linked sites'
             zones); jinja_env — fabric's template environment; fetch — False to skip fetching (tests, offline).
    Returns: {"config": bool (a configuration file changed), "reconfigured": bool (the running resolver took it),
             "lists": update_lists' result or None}.
    Fails:   KeyError for a missing secret or var; OSError writing the files; jinja2 errors. A list that cannot be
             fetched is left out (its state says why), never raised.
    Feeds:   deploy/deploy_optional_parts (when install_resolver); tests/resolver/run.py."""
    paths = resolver_paths(v)
    uid, gid = service_user(v, "resolver")
    ensure_dir(paths["root"], 0o750, 0, gid)
    ensure_dir(paths["config"], 0o750, 0, gid)
    ensure_dir(paths["lists"], 0o750, 0, gid)
    ensure_dir(paths["log"], 0o750, uid, gid)
    ensure_dir(paths["cache"], 0o750, uid, gid)
    lists = update_lists(v, only_missing=True, reload=False) if fetch else None
    wanted = [{"zone": list_zone(i["url"]), "name": i.get("name") or i["url"]} for i in v.get("dns_filter_lists") or []]
    present = [i for i in wanted if os.path.exists(os.path.join(paths["lists"], i["zone"]))]
    keep = {i["zone"] for i in wanted} | {"state.json"}
    for f in os.listdir(paths["lists"]):
        if f not in keep:
            os.remove(os.path.join(paths["lists"], f))
    security = v.get("security") or {}
    upstreams = v.get("dns_filter_upstreams") or []
    ctx = {**v, "resolver_rndc_secret": secrets["resolver_rndc_secret"], "zones": filter_zones(v, links),
           "lists": present, "upstream_names": list(dict.fromkeys(u["name"] for u in upstreams)),
           "clients": list(dict.fromkeys([v["lan_cidr"], v["fabric_subnet"],
                                          *(security.get("firewall_allow") or [])]))}
    changed = False
    for name in CONFIG:
        text = jinja_env.get_template(f"resolver/config/{name}.j2").render(**ctx)
        changed |= write_file_if_changed(os.path.join(paths["config"], name), text, 0o640, 0, gid)
    reconfigured = False
    if changed:
        # reload, not reconfig: it rereads the configuration and every zone whose file changed (the rules zones)
        r = resolver_rndc(["reload"], timeout=120)
        reconfigured = bool(r and r.returncode == 0)
    return {"config": changed, "reconfigured": reconfigured, "lists": lists}
