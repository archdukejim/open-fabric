from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def save_device(actor, name, fields, new=False):
    """Purpose: Create a device, or replace an existing device's fields.
             Agent route: POST /v1/devices (devices:enroll) when new, else POST /v1/devices/<name> (devices:admin).
    Inputs:  actor — str user name; name — device name; fields — dict from Handler.device_form (type, owner,
             description, macs, enabled, roles); new — bool, default False.
    Returns: new: {"name": str created name}; edit: fabriclib.directory.update_device's result, or {} if it returns
             none.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad fields, a duplicate or unknown device.
    Feeds:   src/webui/routes/dirsrv_post (devices).
    """
    if new:
        return call_agent("POST", "/v1/devices", {"actor": actor, "name": name, "fields": fields})
    return call_agent("POST", f"/v1/devices/{quote_segment(name)}", {"actor": actor, "fields": fields})
