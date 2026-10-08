from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step

CLIENT_ID = "fabric-webui"


def ensure_webui_client(kc, realm, v, s, role_reps, flow_id):
    """Purpose: create or update the confidential OIDC client "fabric-webui" for the web UI: code flow with PKCE S256,
             exact redirect https://<hostname_mgr>/oidc/callback, no direct/implicit grants, the admin sign-in flow
             bound, a "roles" claim in the ID token, and every given realm role in its scope.
    Inputs:  kc — Admin; realm — realm name; v — vars (hostname_mgr); s — secrets (webui_oidc_secret); role_reps — list
             of role representations to put in scope; flow_id — the admin sign-in flow (ensure_signin_flows).
    Returns: None. Existing attributes are merged; missing scope roles are added (none are removed).
    Fails:   SystemExit from Admin.call; KeyError if hostname_mgr or webui_oidc_secret is missing.
    Feeds:   configure_keycloak (when install_webui)."""
    base = f"https://{v['hostname_mgr']}"
    rep = {
        "clientId": CLIENT_ID,
        "name": "Fabric web UI",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": s["webui_oidc_secret"],
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "frontchannelLogout": True,
        "fullScopeAllowed": False,
        "rootUrl": base,
        "baseUrl": "/",
        "redirectUris": [f"{base}/oidc/callback"],
        "webOrigins": [base],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": f"{base}/",
        },
        "authenticationFlowBindingOverrides": {"browser": flow_id},
    }
    _, found = kc.call("GET", f"/{q(realm)}/clients?clientId={q(CLIENT_ID)}")
    if found:
        cid = found[0]["id"]
        kc.call("PUT", f"/{q(realm)}/clients/{cid}",
                {**found[0], **rep, "attributes": {**found[0].get("attributes", {}), **rep["attributes"]}})
        step(f"updated client {CLIENT_ID}")
    else:
        kc.call("POST", f"/{q(realm)}/clients", rep)
        cid = kc.call("GET", f"/{q(realm)}/clients?clientId={q(CLIENT_ID)}")[1][0]["id"]
        step(f"created client {CLIENT_ID}")

    _, mappers = kc.call("GET", f"/{q(realm)}/clients/{cid}/protocol-mappers/models")
    if not any(m.get("name") == "realm roles" for m in mappers):
        kc.call("POST", f"/{q(realm)}/clients/{cid}/protocol-mappers/models", {
            "name": "realm roles", "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {"claim.name": "roles", "multivalued": "true", "jsonType.label": "String",
                       "id.token.claim": "true", "access.token.claim": "false",
                       "userinfo.token.claim": "false"}})
        step("added roles claim to fabric-webui ID tokens")

    # every fabric role in scope, so the roles claim carries the person's permissions
    _, scoped = kc.call("GET", f"/{q(realm)}/clients/{cid}/scope-mappings/realm")
    missing = [r for r in role_reps if r["name"] not in {m["name"] for m in scoped}]
    if missing:
        kc.call("POST", f"/{q(realm)}/clients/{cid}/scope-mappings/realm", missing)
