from webui import agentclient as actions
from webui import views


def bind9_page(h, ctx, query, status=200):
    """Purpose: Render the BIND9 tab: forward zone records, generated reverse zones, the names DHCP registered
             (read-only, from Kea's leases: manual 1.10.3.6) or TSIG keys.
    Inputs:  h — the request handler (send); ctx — page context; query — dict: view ('reverse', 'dhcp' or 'tsig',
             anything else is forward), zone (a zone key; default the first forward zone), msg, err; status — int,
             default 200.
    Returns: the BIND9 page with the given status.
    Fails:   agent errors propagate to handle_request (400, redirect to /login, 403, 503) (e.g. an unknown zone key →
             400).
    Feeds:   get_page (/bind9) and tsig_post (re-shows the TSIG section with 400 on a validation error).
    """
    section = query.get("view") if query.get("view") in ("reverse", "dhcp", "tsig") else "forward"
    zones = actions.list_zones()
    forward = [z for z in zones if not z.get("reverse")]
    key = query.get("zone") or (forward[0]["key"] if forward else "")
    return h.send(status, views.bind9(
        ctx, section, zones, zone=actions.zone_detail(key) if section == "forward" and key else None,
        types=actions.RECORD_TYPES, msg=query.get("msg", ""), err=query.get("err", ""),
        tsig_keys=actions.list_tsig_keys() if section == "tsig" else None,
        reverse=actions.reverse_zones() if section == "reverse" else None,
        dhcp=actions.dhcp_overview() if section == "dhcp" else None))
