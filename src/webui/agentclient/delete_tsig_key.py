from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def delete_tsig_key(actor, name):
    """Purpose: Remove a TSIG key (published by the next apply).
             Agent route: POST /v1/tsig/<name>/delete (tsig:manage).
    Inputs:  actor — str user name; name — existing key name.
    Returns: {} (empty dict).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown key.
    Feeds:   src/webui/routes/tsig_post (result unused).
    """
    return call_agent("POST", f"/v1/tsig/{quote_segment(name)}/delete", {"actor": actor})
