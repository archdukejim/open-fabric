from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def zone_detail(key):
    """Purpose: One zone's records and BIND sync status, for the forward-zone view.
             Agent route: GET /v1/zones/<key> (dns:read).
    Inputs:  key — str zone key from list_zones (quoted into the path).
    Returns: {"key", "name", "records": [record dicts with display values and PTR info], "status": str}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown zone key.
    Feeds:   webui/routes/bind9_page.
    """
    return call_agent("GET", f"/v1/zones/{quote_segment(key)}")
