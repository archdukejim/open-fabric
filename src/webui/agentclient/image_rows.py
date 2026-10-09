from webui.agentclient.connection import call_agent


def image_rows():
    """Purpose: each installed service's image: running, validated, and whether an update is available (manual 1.14.2),
             for the Overview's Updates section. Agent route: GET /v1/images (status:read).
    Inputs:  none.
    Returns: list of {"service", "var", "running", "applied", "validated", "state"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/" (views.overview).
    """
    return call_agent("GET", "/v1/images")
