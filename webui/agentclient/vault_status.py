from webui.agentclient.connection import call_agent


def vault_status():
    """Purpose: OpenBao at a glance for the OpenBao page; never secrets.
             Agent route: GET /v1/vault (vault:status).
    Inputs:  none.
    Returns: dict from fabriclib.vault.vault_status: {"url", "reachable", "initialized", "sealed", "key", "mounts",
             "auth", ...}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/openbao_page.
    """
    return call_agent("GET", "/v1/vault")
