from webui.agentclient.connection import call_agent


def device_overview():
    """Purpose: Devices, roles and the RBAC vocabulary from one directory read.
             Agent route: GET /v1/devices (devices:read).
    Inputs:  none.
    Returns: {"devices": [...], "roles": [...], "types": [...], "permissions": {...}}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/dirsrv_page and Handler.stepca_page (device picker; errors ignored there).
    """
    return call_agent("GET", "/v1/devices")
