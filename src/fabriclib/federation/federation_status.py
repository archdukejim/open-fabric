from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.list_invitations import list_invitations


def federation_status(v, with_invitations=True):
    """Purpose: what this install is in its fabric: standalone, an upstream with sites, or a site with an
             upstream; its endpoint; the sites that joined it; open invitations.
    Inputs:  v — fabric vars: site_name, domain, org_domain, federation_endpoint, hostname_federation;
             with_invitations — also read the open invitations (needs fabric's secrets), default True.
    Returns: {"site_name", "domain", "org_domain", "role": "standalone" | "upstream" | "site",
             "endpoint": bool, "endpoint_host": hostname_federation or None, "upstream": dict or None,
             "sites": {name: record}, "invitations": list (list_invitations; [] when not read)}.
             An install that joined an upstream is a "site" (it can also have sites of its own later: F4).
    Fails:   yaml.YAMLError/OSError from load_registry; ValidationError from list_invitations (OpenBao
             locked) when with_invitations.
    Feeds:   run_federation_command (status)."""
    reg = load_registry()
    endpoint = bool(v.get("federation_endpoint"))
    role = "site" if reg["upstream"] else ("upstream" if reg["sites"] or endpoint else "standalone")
    return {"site_name": v.get("site_name"), "domain": v.get("domain"),
            "org_domain": v.get("org_domain") or v.get("domain"), "role": role, "endpoint": endpoint,
            "endpoint_host": v.get("hostname_federation") if endpoint else None, "upstream": reg["upstream"],
            "sites": reg["sites"], "invitations": list_invitations(v) if with_invitations else []}
