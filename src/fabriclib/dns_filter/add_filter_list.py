from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.check_filter_settings import check_filter_settings
from fabriclib.dns_filter.common.list_zone import list_zone


def add_filter_list(actor, name, url, source="cli"):
    """Purpose: add a block list to the DNS filter (manual 1.12.2.14): saved in vars.yaml, checked like the settings
             (an http(s) url, not twice). Applied by the next apply; fetched by the lists job (start_list_fetch).
    Inputs:  actor — who asks (audit); name — the list's name (from the catalogue or typed; the url when empty); url —
             str; source — "cli" or "web".
    Returns: {"name", "url", "zone"}.
    Fails:   ValidationError from check_filter_settings (not http(s), already there) or for a name over 200 characters;
             OSError or yaml errors from the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/lists)."""
    url, name = str(url or "").strip(), str(name or "").strip()
    if len(name) > 200:
        raise ValidationError("a list's name is at most 200 characters")
    with vars_lock():
        data = load_vars()
        lists = list(data.get("dns_filter_lists") or [])
        lists.append({"name": name or url, "url": url})
        check_filter_settings({**data, "dns_filter_lists": lists})
        data["dns_filter_lists"] = lists
        save_vars(data)
    write_audit(actor, "DNS_FILTER_LIST_ADD", f"{name or url} {url}", source)
    return {"name": name or url, "url": url, "zone": list_zone(url)}
