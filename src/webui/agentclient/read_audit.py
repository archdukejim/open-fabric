from webui.agentclient.connection import call_agent


def read_audit(limit=200):
    """Purpose: Recent audit-log lines for the Audit page.
             Agent route: GET /v1/audit (audit:read).
    Inputs:  limit — int, default 200; the client keeps only the first `limit` lines (the agent already sends at
             most 200).
    Returns: list of str log lines, newest first.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for "/audit".
    """
    return call_agent("GET", "/v1/audit")[:limit]
