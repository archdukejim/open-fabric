import os

from fabriclib.dns_filter.common.list_zone import list_zone
from fabriclib.dns_filter.common.resolver_paths import resolver_paths
from fabriclib.dns_filter.fetch_catalogue import fetch_catalogue
from fabriclib.dns_filter.update_lists import update_lists
from fabriclib.system.apply_changes import apply_changes


def refresh_lists(v, actor="root", source="cli"):
    """Purpose: the lists job (manual 1.12.2.10, 1.12.2.14): fetch every list and reload the changed ones, refresh
             AdGuard's catalogue, and apply when a list now has a good copy the running configuration does not name
             yet (one just added from the web console, which fabric-agent cannot fetch itself).
    Inputs:  v — rendered vars; actor, source — for the apply's audit line.
    Returns: update_lists' result, plus "catalogue": the number of lists in it (None when it could not be fetched:
             the last copy stays), "applied": None (nothing to add), True or False (the apply's outcome), "output":
             the apply's output when it failed.
    Fails:   OSError from update_lists writing its files; subprocess.TimeoutExpired from apply_changes.
    Feeds:   dns_filter/run_dns_filter_command (`fabricctl dns-filter lists`, the fabric-dns-lists timer and the
             console's Fetch now / a list added, through start_list_fetch)."""
    result = update_lists(v)
    try:
        result["catalogue"] = len(fetch_catalogue(v)["lists"])
    except (OSError, ValueError):
        result["catalogue"] = None
    paths = resolver_paths(v)
    try:
        with open(os.path.join(paths["config"], "named.conf")) as f:
            running = f.read()
    except FileNotFoundError:
        running = ""
    new = [i for i in v.get("dns_filter_lists") or []
           if os.path.exists(os.path.join(paths["lists"], list_zone(i["url"])))
           and f'"{list_zone(i["url"])}"' not in running]
    result["applied"] = None
    if new:
        ok, output = apply_changes(actor, source)
        result["applied"] = ok
        if not ok:
            result["output"] = output[-600:]
    return result
