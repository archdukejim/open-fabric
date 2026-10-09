from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def remove_filter_list(actor, url, source="cli"):
    """Purpose: take a block list out of the DNS filter (manual 1.12.2.14): saved in vars.yaml; the next apply drops
             its zone and its converted copy (deploy_resolver).
    Inputs:  actor — who asks (audit); url — the list's url, as listed; source — "cli" or "web".
    Returns: {"name", "url"} of the list removed.
    Fails:   ValidationError when no list has that url; OSError or yaml errors from the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/lists/delete)."""
    url = str(url or "").strip()
    with vars_lock():
        data = load_vars()
        lists = list(data.get("dns_filter_lists") or [])
        gone = next((i for i in lists if i.get("url") == url), None)
        if gone is None:
            raise ValidationError(f"no list has the url {url}")
        data["dns_filter_lists"] = [i for i in lists if i is not gone]
        save_vars(data)
    write_audit(actor, "DNS_FILTER_LIST_REMOVE", f"{gone.get('name')} {url}", source)
    return {"name": gone.get("name") or url, "url": url}
