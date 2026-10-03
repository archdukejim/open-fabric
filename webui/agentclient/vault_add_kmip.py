from webui.agentclient.connection import call_agent


def vault_add_kmip(endpoint, key_id, ca_pem, cert_pem, key_pem, server_name, label):
    """Purpose: Add a KMIP HSM/KMS as an unlock method.
             Agent route: POST /v1/vault/slots/add-hsm (vault:unlock), timeout 120 s.
    Inputs:  endpoint — host:port; key_id — key on the device; ca_pem, cert_pem, key_pem — str PEM CA, client cert
             and client key; server_name — TLS name to verify; label — str name. No actor is sent: the agent
             takes the user from the token.
    Returns: {"id": str new slot id}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if the device cannot be reached or the wrap fails.
    Feeds:   webui/routes/vault_post (add-hsm).
    Notes:   The client key travels only in this request body over the agent socket.
    """
    return call_agent("POST", "/v1/vault/slots/add-hsm",
                 {"endpoint": endpoint, "key_id": key_id, "ca": ca_pem, "cert": cert_pem, "key": key_pem,
                  "server_name": server_name, "label": label}, timeout=120)
