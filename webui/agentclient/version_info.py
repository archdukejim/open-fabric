from webui.agentclient.connection import call_agent


def version_info():
    """Purpose: The fabric version and build shown in every page's header.
             Agent route: GET /v1/version (permission: session).
    Inputs:  none.
    Returns: {"version": str, "build": str} (fabriclib.system.version_info).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/session/page_context (every page).
    """
    return call_agent("GET", "/v1/version")
