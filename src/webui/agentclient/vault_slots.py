from webui.agentclient.connection import call_agent


def vault_slots():
    """Purpose: The vault's unlock methods and this host's name (typed to confirm changes).
             Agent route: GET /v1/vault/slots (vault:status).
    Inputs:  none.
    Returns: {"slots": [slot dicts], "host": str hostname from vars.yaml}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/openbao_page and Handler.vault_post (the host-name confirmation).
    """
    return call_agent("GET", "/v1/vault/slots")
