from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def machine_action(name, action):
    """Purpose: Enable, disable or remove one of this site's machines.
             Agent routes: POST /v1/machines/<name>/enable|disable|delete (machines:admin).
    Inputs:  name — the machine's host name; action — "enable", "disable" or "delete".
    Returns: dict from fabriclib (set_machine_enabled or remove_machine).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
             ValidationError when the site has no such machine.
    Feeds:   src/webui/routes/directory_post (machines).
    """
    return call_agent("POST", f"/v1/machines/{quote_segment(name)}/{action}")
