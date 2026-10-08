from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def reset_sign_in(uid):
    """Purpose: Reset a person's sign-in: new one-time password, TOTP removed, sessions ended.
             Agent route: POST /v1/people/<uid>/reset (people:reset).
    Inputs:  uid — user name (quoted).
    Returns: str new one-time password (shown once).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown user, or a fabric-group member when the caller lacks
             system:admin; KeyError if a 200 reply had no "password".
    Feeds:   src/webui/routes/directory_post (people/<uid>/reset -> views.person_result).
    """
    return call_agent("POST", f"/v1/people/{quote_segment(uid)}/reset", {})["password"]
