from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def save_role(actor, name, fields, new=False):
    """Purpose: Create a device role, or replace an existing role's fields.
             Agent route: POST /v1/roles when new, else POST /v1/roles/<name> (roles:admin).
    Inputs:  actor — str user name; name — role name; fields — dict from Handler.role_form (description, vlan,
             priority, permissions); new — bool, default False.
    Returns: new: {"name": str created name}; edit: fabriclib.ldap.update_role's result, or {}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad fields, a duplicate or unknown role.
    Feeds:   webui/routes/dirsrv_post (roles).
    """
    if new:
        return call_agent("POST", "/v1/roles", {"actor": actor, "name": name, "fields": fields})
    return call_agent("POST", f"/v1/roles/{quote_segment(name)}", {"actor": actor, "fields": fields})
