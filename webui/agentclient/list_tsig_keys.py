from webui.agentclient.connection import call_agent


def list_tsig_keys():
    """Purpose: The TSIG keys and their update rights (never their secrets).
             Agent route: GET /v1/tsig (dns:read).
    Inputs:  none.
    Returns: list of {"name", "algorithm", "types", "scope", "acls"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/bind9_page (view "tsig").
    """
    return call_agent("GET", "/v1/tsig")
