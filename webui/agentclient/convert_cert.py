from webui.agentclient.connection import call_agent


def convert_cert(actor, cert, key):
    """Purpose: Re-package a certificate (and optional key) into other formats.
             Agent route: POST /v1/pki/convert (pki:issue).
    Inputs:  actor — str user name; cert — str certificate data; key — str private key PEM, or "" for none.
    Returns: dict from fabriclib.pki.convert_cert: {"name", "cert", "fullchain", "der_b64", "p7b_b64", "p12_b64",
             "p12_password", "info"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for unreadable input or a key that does not match.
    Feeds:   webui/routes/stepca_post for "convert" (views.pki_result).
    """
    return call_agent("POST", "/v1/pki/convert", {"actor": actor, "cert": cert, "key": key})
