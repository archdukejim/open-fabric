from webui.agentclient.connection import call_agent


def vault_rotate(actor):
    """Purpose: Make a new vault key and give it to every unlock method whose device is present.
             Agent route: POST /v1/vault/rotate (vault:unlock), timeout 900 s.
    Inputs:  actor — str user name.
    Returns: {"key_id": str, "kept": [slot ids], "dropped": [slot ids removed because their device was absent]}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/vault_post (rotate).
    """
    return call_agent("POST", "/v1/vault/rotate", {"actor": actor}, timeout=900)
