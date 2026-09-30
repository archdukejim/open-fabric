import json
import os
import threading

from fabriclib.common.errors import ValidationError

_lock = threading.Lock()
_oidc = {}            # config path -> KeycloakOIDC (keeps its JWKS cache between requests)


def _client(v):
    from webui.oidc import KeycloakOIDC              # fabric/lib/webui: the same verification the web UI uses
    from webui.tlsclient import TLSClient
    path = os.path.join(v["deploy_base_dir"], "webui", "config", "webui.json")
    with _lock:
        if path not in _oidc:
            with open(path) as f:
                kc = json.load(f)["keycloak"]
            ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
            _oidc[path] = KeycloakOIDC(TLSClient(kc["ip"], kc.get("port", 8443), kc["hostname"], ca),
                                       public_base=f"https://{kc['hostname']}", realm=kc["realm"],
                                       client_id=kc["client_id"], client_secret="", redirect_uri="")
        return _oidc[path]


def verify_user_token(v, token):
    """The claims of a signed-in person's Keycloak ID token, checked by
    fabric-agent itself: RS256 signature against the realm's keys (fetched
    over TLS pinned to the fabric root CA), issuer, audience (the web UI
    client), expiry. The web UI forwards it with every call, so a
    compromised web UI container cannot act beyond a signed-in user's
    rights. Raises ValidationError."""
    from webui.oidc import OIDCError
    if not token:
        raise ValidationError("not signed in")
    try:
        claims = _client(v).verify_id_token(token)
    except OIDCError as exc:
        raise ValidationError(f"sign-in token refused: {exc}")
    except (OSError, KeyError, ValueError) as exc:
        raise ValidationError(f"sign-in cannot be checked: {exc}")
    if not claims.get("preferred_username"):
        raise ValidationError("sign-in token has no user")
    return claims
