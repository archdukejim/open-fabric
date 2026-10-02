from webui.agentclient.connection import call_agent


def dhcp_overview():
    """Purpose: What the Kea (DHCP) page shows, read-only.
             Agent route: GET /v1/dhcp (dhcp:read).
    Inputs:  none.
    Returns: {"enabled", "interfaces", "lease_time", "ddns_zone", "subnets": [...], "leases": [...],
             "leases_error"} (fabriclib.dhcp.dhcp_overview).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/get_page for "/kea".
    """
    return call_agent("GET", "/v1/dhcp")
