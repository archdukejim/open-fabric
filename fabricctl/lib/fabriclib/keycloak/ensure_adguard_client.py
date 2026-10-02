import urllib.parse

CLIENT_ID = "fabric-adguard"


def _q(s):
    """Purpose: URL-encode one path or query component for the Keycloak admin API (nothing kept, not "/").
    Inputs:  s — str (a realm or client id).
    Returns: the percent-encoded str.
    Fails:   never for a str.
    Feeds:   ensure_adguard_client.
    """
    return urllib.parse.quote(s, safe="")


def ensure_adguard_client(kc, realm, v, secret, role_reps, flow_id):
    """Purpose: Converge the Keycloak OIDC client (fabric-adguard) that oauth2-proxy signs people into AdGuard
             Home's UI with (design dns-filter.md §5).
    Inputs:  kc — keycloak_bootstrap.Admin client; realm — realm name; v — fabric vars: hostname_adguard;
             secret — the client secret (adguard_oidc_secret); role_reps — role representations for the
             client's scope (every fabric role); flow_id — id of the browser flow to bind (the TOTP login flow).
    Returns: "created" or "updated" ("updated" for any existing client, even when nothing changed).
    Fails:   SystemExit from kc.call on any admin API error or failed admin login; OSError / ssl errors if
             Keycloak is unreachable.
    Feeds:   keycloak_bootstrap.main (prints "<state> client fabric-adguard") when dns_filter is adguard.
    Notes:   confidential client, code flow only, the exact callback https://<hostname_adguard>/oauth2/callback,
             fullScopeAllowed off; realm roles go to a `roles` claim in the ID token, which oauth2-proxy checks
             for fabric:dns:filter. Existing attributes are kept (ours override); the mapper and scope mappings
             are only ever added.
    """
    base = f"https://{v['hostname_adguard']}"
    rep = {
        "clientId": CLIENT_ID, "name": "AdGuard Home (DNS filter)", "enabled": True, "protocol": "openid-connect",
        "publicClient": False, "clientAuthenticatorType": "client-secret", "secret": secret,
        "standardFlowEnabled": True, "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False, "fullScopeAllowed": False,
        "rootUrl": base, "baseUrl": "/",
        "redirectUris": [f"{base}/oauth2/callback"], "webOrigins": [base],
        "attributes": {"post.logout.redirect.uris": f"{base}/"},
        "authenticationFlowBindingOverrides": {"browser": flow_id},
    }
    _, found = kc.call("GET", f"/{_q(realm)}/clients?clientId={_q(CLIENT_ID)}")
    if found:
        cid = found[0]["id"]
        kc.call("PUT", f"/{_q(realm)}/clients/{cid}",
                {**found[0], **rep, "attributes": {**found[0].get("attributes", {}), **rep["attributes"]}})
        changed = "updated"
    else:
        kc.call("POST", f"/{_q(realm)}/clients", rep)
        cid = kc.call("GET", f"/{_q(realm)}/clients?clientId={_q(CLIENT_ID)}")[1][0]["id"]
        changed = "created"
    _, mappers = kc.call("GET", f"/{_q(realm)}/clients/{cid}/protocol-mappers/models")
    if not any(m.get("name") == "realm roles" for m in mappers):
        kc.call("POST", f"/{_q(realm)}/clients/{cid}/protocol-mappers/models", {
            "name": "realm roles", "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {"claim.name": "roles", "multivalued": "true", "jsonType.label": "String",
                       "id.token.claim": "true", "access.token.claim": "false", "userinfo.token.claim": "false"}})
    _, scoped = kc.call("GET", f"/{_q(realm)}/clients/{cid}/scope-mappings/realm")
    missing = [r for r in role_reps if r["name"] not in {s["name"] for s in scoped}]
    if missing:
        kc.call("POST", f"/{_q(realm)}/clients/{cid}/scope-mappings/realm", missing)
    return changed
