from webui.agentclient.connection import call_agent


def describe_csr(actor, csr):
    """Purpose: Decode an uploaded CSR and judge it before signing (the review step).
             Agent route: POST /v1/pki/describe-csr (pki:read).
    Inputs:  actor — str user name (not used by the agent for this route); csr — str PEM, DER-as-text or base64.
    Returns: dict from fabriclib.pki.describe_csr: {"pem", "subject", "cn", "sans", "key", "ca_requested",
             "problems", "text", ...}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if it is not a readable CSR.
    Feeds:   src/webui/routes/stepca_post for "sign/review".
    """
    return call_agent("POST", "/v1/pki/describe-csr", {"actor": actor, "csr": csr})
