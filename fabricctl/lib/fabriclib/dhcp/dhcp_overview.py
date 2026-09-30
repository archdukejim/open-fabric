from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.list_leases import list_leases


def dhcp_overview(v):
    """What the Kea tab shows: whether DHCP is on, its interfaces, subnets
    (pools, router, reservations), the DHCP subzone, and the live leases
    (or why they cannot be read). Read-only."""
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
