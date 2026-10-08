from webui.agentclient.connection import call_agent


def federation_overview():
    """Purpose: The federation: sites, this DC's replication and conflicts, limits, the address plan.
             Agent route: GET /v1/federation (federation:read).
    Inputs:  none.
    Returns: dict from fabriclib.federation.federation_overview.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page (/federation).
    """
    return call_agent("GET", "/v1/federation")
