from webui.agentclient.connection import call_agent


def reverse_zones():
    """Purpose: The reverse (PTR) zones apply generates from the A/AAAA records.
             Agent route: GET /v1/reverse-zones (dns:read).
    Inputs:  none.
    Returns: {"zones": {zone name: records}, "skipped": [addresses left out and why]}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/bind9_page (view "reverse").
    """
    return call_agent("GET", "/v1/reverse-zones")
