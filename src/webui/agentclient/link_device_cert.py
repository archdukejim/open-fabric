from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def link_device_cert(actor, name, sha256, link=True):
    """Purpose: Record or forget a certificate fingerprint on a device.
             Agent route: POST /v1/devices/<name>/certs (pki:link-device).
    Inputs:  actor — str user name; name — device name; sha256 — certificate fingerprint; link — bool, True to
             record, False to forget (default True).
    Returns: fabriclib.directory.link_device_cert's result, or {} (unused).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown device or bad fingerprint.
    Feeds:   src/webui/routes/dirsrv_post (devices, certs — always link=False).
    """
    return call_agent("POST", f"/v1/devices/{quote_segment(name)}/certs", {"actor": actor, "sha256": sha256,
                                                                           "link": link})
