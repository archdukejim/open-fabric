from webui.agentclient.connection import call_agent


def dns_filter_overview():
    """Purpose: What the DNS filter tab shows: its lists and their state, rules, upstreams, statistics and AdGuard's
             catalogue. Agent route: GET /v1/dns-filter (dns:filter).
    Inputs:  none.
    Returns: fabriclib.dns_filter.filter_overview's dict ("on", "lists", "allow", "block", "upstreams",
             "memory_limit", "stats", "catalogue").
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/dns_filter_page."""
    return call_agent("GET", "/v1/dns-filter", timeout=120)
