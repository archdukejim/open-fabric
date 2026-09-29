import urllib.parse

from fabriclib.vault.constants import OIDC_CLIENT_ID, OIDC_MOUNT


def _q(s):
    return urllib.parse.quote(s, safe="")


def ensure_openbao_client(kc, realm, v, secret, role_rep, flow_id):
    """Keycloak client for signing in to OpenBao's own UI: confidential,
    code flow only, the exact OpenBao UI callback as redirect URI, the same
    TOTP login flow as the web UI, and only the admin realm role in its
    tokens (a `roles` claim in the ID token, which OpenBao's role is bound
    to). `kc` is keycloak_bootstrap's admin client. Converges."""
    base = f"https://{v['hostname_openbao']}"
    rep = {
        "clientId": OIDC_CLIENT_ID, "name": "OpenBao (secrets)", "enabled": True, "protocol": "openid-connect",
        "publicClient": False, "clientAuthenticatorType": "client-secret", "secret": secret,
        "standardFlowEnabled": True, "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False, "fullScopeAllowed": False,
        "rootUrl": base, "baseUrl": "/ui/",
        "redirectUris": [f"{base}/ui/vault/auth/{OIDC_MOUNT}/oidc/callback"], "webOrigins": [base],
        "attributes": {"post.logout.redirect.uris": f"{base}/ui/"},
        "authenticationFlowBindingOverrides": {"browser": flow_id},
    }
    _, found = kc.call("GET", f"/{_q(realm)}/clients?clientId={_q(OIDC_CLIENT_ID)}")
    if found:
        cid = found[0]["id"]
        kc.call("PUT", f"/{_q(realm)}/clients/{cid}",
                {**found[0], **rep, "attributes": {**found[0].get("attributes", {}), **rep["attributes"]}})
        changed = "updated"
    else:
        kc.call("POST", f"/{_q(realm)}/clients", rep)
        cid = kc.call("GET", f"/{_q(realm)}/clients?clientId={_q(OIDC_CLIENT_ID)}")[1][0]["id"]
        changed = "created"
    _, mappers = kc.call("GET", f"/{_q(realm)}/clients/{cid}/protocol-mappers/models")
    if not any(m.get("name") == "realm roles" for m in mappers):
        kc.call("POST", f"/{_q(realm)}/clients/{cid}/protocol-mappers/models", {
            "name": "realm roles", "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {"claim.name": "roles", "multivalued": "true", "jsonType.label": "String",
                       "id.token.claim": "true", "access.token.claim": "false", "userinfo.token.claim": "false"}})
    _, scoped = kc.call("GET", f"/{_q(realm)}/clients/{cid}/scope-mappings/realm")
    if not any(r["name"] == role_rep["name"] for r in scoped):
        kc.call("POST", f"/{_q(realm)}/clients/{cid}/scope-mappings/realm", [role_rep])
    return changed
