from webui.agentclient.connection import call_agent


def raise_signin_layer(layer, value):
    """Purpose: raise one sign-in layer, or turn Kerberos sign-in on or off (layer "kerberos"); saved, audited and
             applied at once. Agent routes: POST /v1/security/raise and /v1/security/kerberos (security:raise),
             timeout 600 s (the apply and Keycloak's configuration).
    Inputs:  layer — "admin-2fa", "everyone-2fa", "client-cert" or "kerberos"; value — a level, or on/off.
    Returns: {"layer", "from", "to", "changed", "applied": bool, "output": str}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400: a lowering, an
             unknown layer or value), AuthError (401), PermissionDenied (403).
    Feeds:   src/webui/routes/security_post.
    """
    if layer == "kerberos":
        return call_agent("POST", "/v1/security/kerberos", {"value": value}, timeout=600)
    return call_agent("POST", "/v1/security/raise", {"layer": layer, "value": value}, timeout=600)
