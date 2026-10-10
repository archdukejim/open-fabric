import copy

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.common.filter_target import filter_target


def remove_filter_list(actor, url, source="cli", group=""):
    """Purpose: take a block list out of the DNS filter, everyone's or a client group's (manual 1.12.2.14, 1.12.2.15):
             saved in vars.yaml; the next apply drops its zone, and its converted copy when nothing uses it
             (deploy_resolver).
    Inputs:  actor — who asks (audit); url — the list's url, as listed; source — "cli" or "web"; group — "" for
             everyone, else a group's name.
    Returns: {"name", "url", "group"} of the list removed.
    Fails:   ValidationError for an unknown group or when it has no list with that url; OSError or yaml errors from
             the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/lists/delete)."""
    url = str(url or "").strip()
    with vars_lock():
        data = copy.deepcopy(load_vars())
        target, keys, label = filter_target(data, group)
        lists = list(target.get(keys["lists"]) or [])
        gone = next((i for i in lists if isinstance(i, dict) and i.get("url") == url), None)
        if gone is None:
            raise ValidationError(f"{label} has no list with the url {url}")
        target[keys["lists"]] = [i for i in lists if i is not gone]
        save_vars(data)
    write_audit(actor, "DNS_FILTER_LIST_REMOVE", f"{gone.get('name')} {url} ({label})", source)
    return {"name": gone.get("name") or url, "url": url, "group": "" if label == "everyone" else label[6:]}
