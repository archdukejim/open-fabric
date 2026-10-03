from webui.agentclient.connection import call_agent


def radius_guides():
    """Purpose: The FreeRADIUS setup guides and Windows scripts, filled in for this host (public data only).
             Agent route: GET /v1/radius/guides (radius:read).
    Inputs:  none.
    Returns: dict from fabriclib.radius.radius_guides: {"host_ip", "server_name", "people", "windows": {"tls"|"ttls":
             {"filename", "script"}}, ...}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/get_page for "/freeradius" (views "switches" and "windows").
    """
    return call_agent("GET", "/v1/radius/guides")
