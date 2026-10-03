from webui.agentclient.connection import call_agent


def list_issued():
    """Purpose: Certificates issued by hand, for the Step-CA 'issued' view.
             Agent route: GET /v1/pki/issued (pki:read).
    Inputs:  none.
    Returns: list of {"when", "actor", "kind", "subject", "sans", "not_after", "status"}, newest first.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/stepca_page (view "issued").
    """
    return call_agent("GET", "/v1/pki/issued")
