from webui.agentclient.connection import call_agent


def list_zones():
    """Purpose: The DNS zones for the BIND page's zone list.
             Agent route: GET /v1/zones (dns:read).
    Inputs:  none.
    Returns: [{"key": str, "name": str, "records": int, "reverse": bool}] (fabriclib.dns.list_zones).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/bind9_page.
    """
    return call_agent("GET", "/v1/zones")
