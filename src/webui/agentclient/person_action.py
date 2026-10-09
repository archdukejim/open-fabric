from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def person_action(uid, action, body=None):
    """Purpose: Disable, enable or remove a person, or change their groups.
             Agent routes: POST /v1/people/<uid>/disable|enable (people:disable), /delete (people:remove; body:
             confirm), /groups (people:groups; body: action add|remove, group).
    Inputs:  uid — the user name; action — "disable", "enable", "delete" or "groups"; body — dict for delete and groups.
    Returns: dict from fabriclib (set_person_enabled, remove_person or set_person_group).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
             ValidationError for another site's person, a fabric-group member without system:admin, yourself, the
             last admin, or a user name not typed back.
    Feeds:   src/webui/routes/directory_post (people).
    """
    return call_agent("POST", f"/v1/people/{quote_segment(uid)}/{action}", body or {})
