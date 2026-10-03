from webui.agentclient.connection import call_agent


def host_changes():
    """Purpose: What fabric may change on this host, by group, for the overview page (design host-consent.md §3,
             step 7). Agent route: GET /v1/host-changes (status:read).
    Inputs:  none.
    Returns: list of {"group", "title", "state": "approved"|"declined"|"not asked", "when", "by", "relaxation"};
             [] for an install set up before fabric asked.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/get_page for "/" (views.overview).
    """
    return call_agent("GET", "/v1/host-changes")
