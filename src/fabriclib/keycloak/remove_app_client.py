from fabriclib.common.errors import ValidationError
from fabriclib.keycloak.app_client_id import app_client_id
from fabriclib.keycloak.quote import q


def remove_app_client(kc, realm, name):
    """Purpose: unregister an app from single sign-on (manual 3.8.2): its Keycloak client goes, and with it every
             session and token the app held.
    Inputs:  kc — keycloak/admin_client Admin; realm — fabric's realm; name — the app's short name.
    Returns: str, the client id removed.
    Fails:   ValidationError for a bad name or an app not registered; SystemExit from kc.call.
    Feeds:   keycloak/run_sso_command (`fabricctl sso remove`)."""
    client_id = app_client_id(name)
    _, found = kc.call("GET", f"/{q(realm)}/clients?clientId={q(client_id)}")
    if not found:
        raise ValidationError(f"no app named {name} is registered")
    kc.call("DELETE", f"/{q(realm)}/clients/{found[0]['id']}")
    return client_id
