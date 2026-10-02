from webui.agentclient.connection import call_agent


def vault_devices():
    """Purpose: Unlock-capable devices plugged into the host, for the add-method forms.
             Agent route: GET /v1/vault/devices (vault:status).
    Inputs:  none.
    Returns: {"tokens": [...], "disks": [...], "pkcs11": [...]} (fabriclib.vault.detect_devices).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/routes/openbao_page (views "add-security-key" and "add-usb").
    """
    return call_agent("GET", "/v1/vault/devices")
