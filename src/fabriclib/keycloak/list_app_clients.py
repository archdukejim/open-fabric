from fabriclib.keycloak.app_client_id import PREFIX
from fabriclib.keycloak.quote import q


def list_app_clients(kc, realm):
    """Purpose: the apps registered for single sign-on (manual 3.8.2), never their secrets.
    Inputs:  kc — keycloak/admin_client Admin; realm — fabric's realm.
    Returns: list of {"name", "client_id", "redirects"}, by name.
    Fails:   SystemExit from kc.call.
    Feeds:   keycloak/run_sso_command (`fabricctl sso list`)."""
    _, clients = kc.call("GET", f"/{q(realm)}/clients?max=500")
    return sorted(({"name": c["clientId"][len(PREFIX):], "client_id": c["clientId"],
                    "redirects": c.get("redirectUris") or []}
                   for c in clients if c.get("clientId", "").startswith(PREFIX)), key=lambda a: a["name"])
