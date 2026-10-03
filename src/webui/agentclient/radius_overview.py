from webui.agentclient.connection import call_agent


def radius_overview():
    """Purpose: What the FreeRADIUS page shows: on/off, clients, password groups, recent decisions.
             Agent route: GET /v1/radius (radius:read).
    Inputs:  none.
    Returns: {"enabled", "server_name", "host_ip", "clients", "people", "log", "log_error"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/freeradius" and Handler.radius_post (host_ip).
    """
    return call_agent("GET", "/v1/radius")
