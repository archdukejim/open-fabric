from webui.agentclient.connection import call_agent


def relaxed_settings():
    """Purpose: the security relaxations turned on for this host, for the overview page (global Rule 10).
             Agent route: GET /v1/relaxed-settings (status:read).
    Inputs:  none.
    Returns: list of {"setting", "effect"}; [] when none is relaxed.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/" (views.overview).
    """
    return call_agent("GET", "/v1/relaxed-settings")
