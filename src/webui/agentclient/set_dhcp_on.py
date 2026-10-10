from webui.agentclient.connection import call_agent


def set_dhcp_on(on, interface="", subnet="", pool="", router=""):
    """Purpose: Turn DHCP on (with its first subnet when it has none yet) or off; the agent saves, applies and brings
             the host firewall in line (manual 1.10.3.5). Agent route: POST /v1/dhcp/on or /v1/dhcp/off (dhcp:write),
             timeout 600 s (an apply, then the firewall step).
    Inputs:  on — bool; interface, subnet, pool, router — str as typed (on, first subnet only). No actor: the agent
             uses the token's user.
    Returns: {"dhcp": {"on", "interfaces", "subnets"}, "applied": bool, "output": last 2000 chars}.
    Fails:   the call_agent exceptions: AgentError, ValidationError (400: already in that state, a missing or bad
             first subnet, an interface the host lacks), AuthError (401), PermissionDenied (403).
    Feeds:   src/webui/routes/kea_post."""
    body = {"interface": interface, "subnet": subnet, "pool": pool, "router": router} if on else {}
    return call_agent("POST", "/v1/dhcp/on" if on else "/v1/dhcp/off", body, timeout=600)
