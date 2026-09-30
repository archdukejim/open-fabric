import json
import os
import threading

from fabriclib.common.errors import ValidationError

_lock = threading.Lock()
_oidc = {}            # config path -> KeycloakOIDC (keeps its JWKS cache between requests)


def _client(v):
    """Purpose: The cached ID-token verifier, configured exactly like the web UI's.
    Inputs:  v — fabric vars: deploy_base_dir. Reads <base>/webui/config/webui.json "keycloak" (ip, port
             default 8443, hostname, realm, client_id) and the fabric root CA path.
    Returns: a webui.oidc.KeycloakOIDC, one per config path, kept for the process life (JWKS cache).
    Fails:   OSError if webui.json is missing; KeyError / ValueError (JSON) if it is malformed.
    Feeds:   verify_user_token.
    Notes:   cached for the life of the process: a changed webui.json needs an agent restart.
    """
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
    """Purpose: Check a signed-in person's Keycloak ID token in the agent itself and return its claims.
    Inputs:  v — fabric vars (via _client); token — the bearer token string ("" when absent).
    Returns: the verified claims (dict), with preferred_username and the `roles` claim.
    Fails:   ValidationError "not signed in" (no token); "sign-in token refused: <reason>" (OIDCError:
             signature, issuer, audience, expiry); "sign-in cannot be checked: <error>" (config or keys
             unreachable); "sign-in token has no user".
    Feeds:   agent/server.py Handler.authorize (then required_permission, user_permissions).
    Notes:   RS256 signature against the realm's keys fetched over TLS pinned to the fabric root CA, issuer,
             audience (the web UI client), expiry. The web UI forwards the token with every call, so a
             compromised web UI container cannot act beyond a signed-in user's rights.
    """
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
