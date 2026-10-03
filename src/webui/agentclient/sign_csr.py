from webui.agentclient.connection import call_agent


def sign_csr(actor, csr, days, device=""):
    """Purpose: Sign a device's CSR with the fabric CA.
             Agent route: POST /v1/pki/sign (pki:sign), timeout 120 s.
    Inputs:  actor — str user name; csr — str PEM; days — validity as typed in the form (the agent validates it
             against the CA limit); device — optional device name to link the certificate to, default "".
    Returns: dict from fabriclib.pki.sign_csr: {"name", "cert", "chain", "fullchain", ..., "info", "device"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a bad CSR, days or device.
    Feeds:   src/webui/routes/stepca_post for "sign" (views.pki_result).
    """
    return call_agent("POST", "/v1/pki/sign", {"actor": actor, "csr": csr, "days": days, "device": device}, timeout=120)
