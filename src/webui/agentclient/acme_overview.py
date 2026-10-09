from webui.agentclient.connection import call_agent


def acme_overview():
    """Purpose: ACME from fabric's CA for LAN machines (manual 1.5.1.4): how a machine's client uses it, and the
             machines enrolled for DNS-01. Agent route: GET /v1/pki/acme (pki:read).
    Inputs:  none.
    Returns: {"info": [str lines], "machines": [{"name", "fqdn", "key", "records"}], "domain": str}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/stepca_page (view acme).
    """
    return call_agent("GET", "/v1/pki/acme")
