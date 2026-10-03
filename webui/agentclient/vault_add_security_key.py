from webui.agentclient.connection import call_agent


def vault_add_security_key(actor, module, token, pin, key_id, label):
    """Purpose: Add a PKCS#11 security key (e.g. a YubiKey) as an unlock method.
             Agent route: POST /v1/vault/slots/add-security-key (vault:unlock), timeout 120 s.
    Inputs:  actor — str user name; module — PKCS#11 module path; token — token serial; pin — the token PIN;
             key_id — an existing key id on the token, or "new"; label — str name for it.
    Returns: {"id": str new slot id}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a wrong PIN, token or key.
    Feeds:   webui/routes/vault_post (add-security-key).
    Notes:   The PIN travels only in this request body over the agent socket.
    """
    return call_agent("POST", "/v1/vault/slots/add-security-key", {"actor": actor, "module": module, "token": token,
                                                              "pin": pin, "key_id": key_id, "label": label}, timeout=120)
