from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def delete_role(actor, name):
    """Purpose: Delete a device role.
             Agent route: POST /v1/roles/<name>/delete (roles:admin).
    Inputs:  actor — str user name; name — role name.
    Returns: fabriclib's result, or {} (unused).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an invalid role name or a role that still has devices.
    Feeds:   src/webui/routes/directory_post (roles, delete).
    """
    return call_agent("POST", f"/v1/roles/{quote_segment(name)}/delete", {"actor": actor})
