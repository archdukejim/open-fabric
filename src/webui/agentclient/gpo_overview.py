from webui.agentclient.connection import call_agent


def gpo_overview(match=""):
    """Purpose: The Group Policy section: the central store's templates, what the site's admin settings GPO sets, and
             the policies matching a search.
             Agent routes: GET /v1/gpo, or POST /v1/gpo/search with a search text (domain:read).
    Inputs:  match — text to search policy names and titles for ("" lists none).
    Returns: dict from fabriclib.samba.gpo_overview: site, templates, settings, match, policies, more.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   src/webui/routes/directory_page (view "gpo").
    """
    if match.strip():
        return call_agent("POST", "/v1/gpo/search", {"match": match})
    return call_agent("GET", "/v1/gpo")
