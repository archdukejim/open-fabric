from webui.agentclient.connection import call_agent


def cert_warnings():
    """Purpose: what is wrong or coming with fabric's certificates, for the overview page (manual 2.1.5.4, 2.1.5.5).
             Agent route: GET /v1/cert-warnings (status:read).
    Inputs:  none.
    Returns: list of {"level": "fail" | "warn", "what"}; [] when all is well.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/" (views.overview).
    """
    return call_agent("GET", "/v1/cert-warnings")
