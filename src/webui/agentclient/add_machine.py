from webui.agentclient.connection import call_agent


def add_machine(name):
    """Purpose: Pre-create a machine in this site with a one-time join password.
             Agent route: POST /v1/machines (machines:admin).
    Inputs:  name — the machine's host name.
    Returns: str, the one-time join password (shown once, stored nowhere).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
             ValidationError for a bad or taken name.
    Feeds:   src/webui/routes/directory_post (machines/_new -> views.machine_result).
    """
    return call_agent("POST", "/v1/machines", {"name": name})["password"]
