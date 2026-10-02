from webui.agentclient.connection import call_agent


def vault_add_usb(actor, disk, label):
    """Purpose: Add a USB stick as an unlock method.
             Agent route: POST /v1/vault/slots/add-usb (vault:unlock), timeout 180 s.
    Inputs:  actor — str user name; disk — device path chosen from vault_devices; label — str name for it.
    Returns: {"id": str new slot id}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown disk or a failed write/read-back.
    Feeds:   webui/routes/vault_post (add-usb).
    """
    return call_agent("POST", "/v1/vault/slots/add-usb", {"actor": actor, "disk": disk, "label": label}, timeout=180)
