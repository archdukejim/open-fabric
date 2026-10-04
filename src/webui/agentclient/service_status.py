from webui.agentclient.connection import call_agent


def service_status():
    """Purpose: The state of every fabric service, for the overview page.
             Agent route: GET /v1/services (status:read).
    Inputs:  none.
    Returns: list of tuples (service, systemd state, container health — "" for host services); the agent's
             JSON lists are turned back into tuples.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/" (views.overview).
    """
    return [tuple(x) for x in call_agent("GET", "/v1/services")]
