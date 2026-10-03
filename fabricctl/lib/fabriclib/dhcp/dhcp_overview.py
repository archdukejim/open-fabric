from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.list_leases import list_leases


def dhcp_overview(v):
    """Purpose: What the Kea tab and `fabricctl dhcp` show: whether DHCP is on, its interfaces, subnets (pools, router,
             reservations), lease time, the DHCP subzone and the live leases. Read-only.
    Inputs:  v — the vars dict (install_kea, dhcp, domain). Asks Kea's control socket when DHCP is on.
    Returns: {"enabled", "interfaces", "subnets" (with id, name, vlan, notes, options as stored), "lease_time",
             "ddns_zone" ("" when DDNS is off), "options" (the admin's, every subnet), "overrides" (names of the
             options fabric sets itself that the admin replaced: domain-name-servers, ntp-servers, domain-name,
             domain-search, routers — shown so a replaced default is never a surprise), "option_defs",
             "client_classes", "leases" (see list_leases), "leases_error" (why leases could not be read, else "")}.
    Fails:   never for Kea problems — a ValidationError from list_leases goes into leases_error; other errors propagate.
    Feeds:   agent route GET /v1/dhcp (fabric-agent, fabricctl/lib/agent/, called by the web UI); run_dhcp_command
             (status, leases).
    """
    d = v.get("dhcp") or {}
    out = {"enabled": bool(v.get("install_kea")), "interfaces": d.get("interfaces") or [],
           "subnets": d.get("subnets") or [], "lease_time": d.get("lease_time", 86400),
           "ddns_zone": f"{d.get('ddns_subdomain', 'dhcp')}.{v.get('domain', '')}" if d.get("ddns", True) else "",
           "options": d.get("options") or [], "option_defs": d.get("option_defs") or [],
           "client_classes": d.get("client_classes") or [], "leases": [], "leases_error": ""}
    own = {"domain-name-servers", "ntp-servers", "domain-name", "domain-search", "routers"}
    out["overrides"] = sorted({o.get("name") for o in out["options"] if o.get("name") in own}
                              | {f"routers ({s.get('name', s.get('subnet'))})" for s in out["subnets"]
                                 if any(o.get("name") == "routers" for o in s.get("options") or [])})
    if out["enabled"]:
        try:
            out["leases"] = list_leases(v)
        except ValidationError as exc:
            out["leases_error"] = str(exc)
    return out
