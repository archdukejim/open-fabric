import copy

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.check_filter_settings import check_filter_settings
from fabriclib.dns_filter.common.filter_target import filter_target
from fabriclib.dns_filter.common.list_zone import list_zone


def add_filter_list(actor, name, url, source="cli", group=""):
    """Purpose: add a block list to the DNS filter, for everyone or one client group (manual 1.12.2.14, 1.12.2.15):
             saved in vars.yaml, checked like the settings (an http(s) url, not twice; a group's not one already on
             everyone). Applied by the next apply; fetched by the lists job (start_list_fetch).
    Inputs:  actor — who asks (audit); name — the list's name (from the catalogue or typed; the url when empty); url —
             str; source — "cli" or "web"; group — "" for everyone, else a group's name.
    Returns: {"name", "url", "zone", "group"}.
    Fails:   ValidationError from check_filter_settings (not http(s), already there), for an unknown group or a name
             over 200 characters; nothing is saved then. OSError or yaml errors from the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/lists)."""
    url, name = str(url or "").strip(), str(name or "").strip()
    if len(name) > 200:
        raise ValidationError("a list's name is at most 200 characters")
    with vars_lock():
        data = copy.deepcopy(load_vars())
        target, keys, label = filter_target(data, group)
        target[keys["lists"]] = [*(target.get(keys["lists"]) or []), {"name": name or url, "url": url}]
        check_filter_settings(data)
        save_vars(data)
    write_audit(actor, "DNS_FILTER_LIST_ADD", f"{name or url} {url} ({label})", source)
    return {"name": name or url, "url": url, "zone": list_zone(url), "group": "" if label == "everyone" else label[6:]}
