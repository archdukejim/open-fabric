from webui.agentclient.connection import call_agent


def inspect_pem(actor, data):
    """Purpose: Decode certificates or a CSR for reading, with a trust verdict.
             Agent route: POST /v1/pki/inspect (pki:read).
    Inputs:  actor — str user name (not used by the agent for this route); data — str PEM chain, DER-as-text
             or base64.
    Returns: {"kind": "cert" | "csr", "items": [{"info", "text", "trusted", ...}]}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if nothing can be decoded.
    Feeds:   src/webui/routes/stepca_post for "inspect".
    """
    return call_agent("POST", "/v1/pki/inspect", {"actor": actor, "data": data})
