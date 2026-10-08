from webui.agentclient.connection import call_agent


def revoke_cert(actor, target, reason):
    """Purpose: Revoke a certificate fabric issued (manual 2.1.5.10); the CRLs are published at once.
             Agent route: POST /v1/pki/revoke (pki:revoke), timeout 120 s.
    Inputs:  actor — str user name; target — a serial or a certificate's name; reason — one of the CRL reasons.
    Returns: dict from fabriclib.pki.revoke_cert: {"serial", "subject", "issuer", "reason"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400: unknown reason
             or certificate, already revoked), AuthError (401), PermissionDenied (403).
    Feeds:   src/webui/routes/stepca_post for "revoke".
    """
    return call_agent("POST", "/v1/pki/revoke", {"actor": actor, "target": target, "reason": reason}, timeout=120)
