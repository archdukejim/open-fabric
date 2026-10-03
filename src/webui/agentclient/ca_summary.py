from webui.agentclient.connection import call_agent


def ca_summary():
    """Purpose: The CA certificates, where devices fetch them, and the signing limits, for the Step-CA page.
             Agent route: GET /v1/pki/ca (pki:read).
    Inputs:  none.
    Returns: dict from fabriclib.pki.ca_summary: {"domain", "certs_url", "max_days", "root": {...},
             "intermediate": {...}}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/stepca_page (catches AgentError/ValidationError and shows no CA).
    """
    return call_agent("GET", "/v1/pki/ca")
