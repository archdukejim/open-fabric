from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def rotate_tsig_key(actor, name):
    """Purpose: Give a TSIG key a new secret.
             Agent route: POST /v1/tsig/<name>/rotate (tsig:manage).
    Inputs:  actor — str user name; name — existing key name.
    Returns: {"secret": str, "ini": str} — shown once.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown key.
    Feeds:   webui/routes/tsig_post (rotate -> views.tsig_result).
    """
    return call_agent("POST", f"/v1/tsig/{quote_segment(name)}/rotate", {"actor": actor})
