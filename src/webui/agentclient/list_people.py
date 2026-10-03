from webui.agentclient.connection import call_agent


def list_people():
    """Purpose: People and their groups (read-only; managed in Keycloak).
             Agent route: GET /v1/people (people:read).
    Inputs:  none.
    Returns: dict from fabriclib.ldap.list_people, e.g. {"users": [...], "groups": [...], "keycloak_url": str}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/dirsrv_page (view "people").
    """
    return call_agent("GET", "/v1/people")
