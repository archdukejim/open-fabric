from webui.agentclient.connection import call_agent


def domain_overview():
    """Purpose: The domain, its controller, the password policy and this site's machines.
             Agent route: GET /v1/domain (domain:read).
    Inputs:  none.
    Returns: dict from fabriclib.samba.domain_overview: status, policy, site, machines (or None), machines_error.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/directory_page (views "domain", "machines").
    """
    return call_agent("GET", "/v1/domain")
