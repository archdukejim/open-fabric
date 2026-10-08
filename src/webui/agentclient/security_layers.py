from webui.agentclient.connection import call_agent


def security_layers():
    """Purpose: the sign-in layers for the Security page (manual 2.3.6.2.6.4). Agent route: GET /v1/security
             (security:raise).
    Inputs:  none.
    Returns: list of {"layer", "what", "value", "effective", "choices", "lowered"} (fabriclib signin_rows).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/security".
    """
    return call_agent("GET", "/v1/security")
