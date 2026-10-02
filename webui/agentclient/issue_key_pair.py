from webui.agentclient.connection import call_agent


def issue_key_pair(actor, cn, sans, key_type, days, device=""):
    """Purpose: Generate a private key and certificate for a device that cannot make its own CSR.
             Agent route: POST /v1/pki/issue (pki:issue), timeout 180 s.
    Inputs:  actor — str user name; cn — common name; sans — list of str names/IPs; key_type — e.g. "RSA-2048";
             days — validity as typed; device — optional device name to link, default "".
    Returns: dict from fabriclib.pki.issue_key_pair: cert fields plus "key", "p12_b64" and "p12_password"
             (the key is returned this once).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad names, key type or days.
    Feeds:   webui/routes/stepca_post for "issue" (views.pki_result).
    """
    return call_agent("POST", "/v1/pki/issue", {"actor": actor, "cn": cn, "sans": sans, "key_type": key_type,
                                           "days": days, "device": device}, timeout=180)
