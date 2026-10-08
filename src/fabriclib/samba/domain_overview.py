from fabriclib.common.errors import ValidationError
from fabriclib.directory.list_machines import list_machines
from fabriclib.samba.domain_status import domain_status


def domain_overview(v):
    """Purpose: what the Directory tab's domain section shows (manual 1.6.5.21 S7.4): the domain and its DC, the
             password policy as set, and this site's machines.
    Inputs:  v — fabric vars (ad_domain, ad_realm, ad_netbios, hostname_dc, ad_password_policy, site_name).
    Returns: {"status": domain_status(v), "policy": the settings' ad_password_policy, "site", "machines": list or
             None, "machines_error": "" or why they could not be read}.
    Fails:   never for a DC that does not answer (status says so; machines_error carries the reason).
    Feeds:   agent route GET /v1/domain (domain:read)."""
    out = {"status": domain_status(v), "policy": v.get("ad_password_policy") or {}, "site": v.get("site_name", ""),
           "machines": None, "machines_error": ""}
    try:
        out["machines"] = list_machines(v)
    except ValidationError as e:
        out["machines_error"] = str(e)
    return out
