from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def delete_device(actor, name):
    """Purpose: Delete a device and take it out of every role.
             Agent route: POST /v1/devices/<name>/delete (devices:admin).
    Inputs:  actor — str user name; name — device name.
    Returns: fabriclib's result, or {} (unused).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown device.
    Feeds:   webui/routes/dirsrv_post (devices, delete).
    """
    return call_agent("POST", f"/v1/devices/{quote_segment(name)}/delete", {"actor": actor})
