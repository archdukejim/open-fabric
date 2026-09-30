from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.list_leases import list_leases


def dhcp_overview(v):
    """Purpose: What the Kea tab and `fabricctl dhcp` show: whether DHCP is on, its interfaces, subnets (pools, router,
             reservations), lease time, the DHCP subzone and the live leases. Read-only.
    Inputs:  v — the vars dict (install_kea, dhcp, domain). Asks Kea's control socket when DHCP is on.
    Returns: {"enabled", "interfaces", "subnets", "lease_time", "ddns_zone" ("" when DDNS is off), "leases" (see
             list_leases), "leases_error" (why leases could not be read, else "")}.
    Fails:   never for Kea problems — a ValidationError from list_leases goes into leases_error; other errors propagate.
    Feeds:   agent route GET /v1/dhcp (fabricctl/lib/agent/server.py, called by webui/server.py); run_dhcp_command
             (status, leases).
    """
    d = v.get("dhcp") or {}
    out = {"enabled": bool(v.get("install_kea")), "interfaces": d.get("interfaces") or [],
           "subnets": d.get("subnets") or [], "lease_time": d.get("lease_time", 86400),
           "ddns_zone": f"{d.get('ddns_subdomain', 'dhcp')}.{v.get('domain', '')}" if d.get("ddns", True) else "",
           "leases": [], "leases_error": ""}
    if out["enabled"]:
        try:
            out["leases"] = list_leases(v)
        except ValidationError as exc:
            out["leases_error"] = str(exc)
    return out
