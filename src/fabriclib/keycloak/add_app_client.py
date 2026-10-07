import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.keycloak.app_client_id import app_client_id
from fabriclib.keycloak.quote import q


def _redirects(urls):
    """Purpose: an app's redirect URLs, checked: https only, a host, no wildcard (a stolen sign-in code could
             otherwise be sent anywhere).
    Inputs:  urls — list of str.
    Returns: (redirect URIs list, web origins list).
    Fails:   ValidationError for none, or a URL that is not https://host/…, or holds a "*".
    Feeds:   add_app_client."""
    if not urls:
        raise ValidationError("give the app's redirect URL (--redirect https://…), as the app shows it")
    origins = []
    for url in urls:
        u = urllib.parse.urlsplit(url)
        if u.scheme != "https" or not u.hostname or "*" in url:
            raise ValidationError(f"{url}: a redirect URL is https://<host>/… without wildcards")
        origin = f"https://{u.netloc}"
        if origin not in origins:
            origins.append(origin)
    return list(urls), origins


def add_app_client(kc, realm, v, name, redirects):
    """Purpose: register an app (Proxmox VE, TrueNAS, …) for single sign-on through this site's Keycloak (manual
             3.8.2): a confidential OpenID Connect client, the authorization-code flow only, the given redirect
             URLs exactly, sign-in through the realm's flow (fabric-signin: Kerberos or a password, and the second
             factor every sign-in needs), and the person's groups in a
             `groups` claim, for the app to map to its roles. Keycloak makes the client secret.
    Inputs:  kc — keycloak/admin_client Admin; realm — fabric's realm; v — vars (hostname_keycloak); name — the
             app's short name (app_client_id); redirects — list of https URLs.
    Returns: {"client_id", "secret", "issuer", "discovery"} — the secret is returned once, never kept by fabric.
    Fails:   ValidationError for a bad name or redirect URL, or an app of that name already registered;
             SystemExit from kc.call on an admin API error.
    Feeds:   keycloak/run_sso_command (`fabricctl sso add`)."""
    client_id = app_client_id(name)
    uris, origins = _redirects(redirects)
    _, found = kc.call("GET", f"/{q(realm)}/clients?clientId={q(client_id)}")
    if found:
        raise ValidationError(f"an app named {name} is registered already (fabricctl sso remove {name} first)")
    rep = {"clientId": client_id, "name": f"{name} (single sign-on)", "enabled": True, "protocol": "openid-connect",
           "publicClient": False, "clientAuthenticatorType": "client-secret", "standardFlowEnabled": True,
           "implicitFlowEnabled": False, "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False,
           "redirectUris": uris, "webOrigins": origins,
           "attributes": {"pkce.code.challenge.method": "", "post.logout.redirect.uris": "+"}}
    kc.call("POST", f"/{q(realm)}/clients", rep)
    cid = kc.call("GET", f"/{q(realm)}/clients?clientId={q(client_id)}")[1][0]["id"]
    kc.call("POST", f"/{q(realm)}/clients/{cid}/protocol-mappers/models", {
        "name": "groups", "protocol": "openid-connect", "protocolMapper": "oidc-group-membership-mapper",
        "config": {"claim.name": "groups", "full.path": "false", "id.token.claim": "true",
                   "access.token.claim": "true", "userinfo.token.claim": "true"}})
    secret = kc.call("GET", f"/{q(realm)}/clients/{cid}/client-secret")[1]["value"]
    issuer = f"https://{v['hostname_keycloak']}/realms/{realm}"
    return {"client_id": client_id, "secret": secret, "issuer": issuer,
            "discovery": f"{issuer}/.well-known/openid-configuration"}
