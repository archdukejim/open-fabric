import os


def user_has_role(v, s, user, role):
    """True if Keycloak grants `user` the realm role `role` (directly or via a
    group, e.g. the LDAP admin group). The lookup imports an LDAP user."""
    import keycloak_bootstrap as kb          # fabric/lib: admin client pinned to the fabric root CA
    from webui.tlsclient import TLSClient

    ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    kc = kb.Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
                  s["keycloak_admin_user"], s["keycloak_admin_password"])
    realm = kb.q(v.get("webui_realm") or v["domain"])
    _, found = kc.call("GET", f"/{realm}/users?username={kb.q(user)}&exact=true")
    if not found:
        return False
    _, roles = kc.call("GET", f"/{realm}/users/{found[0]['id']}/role-mappings/realm/composite")
    return any(r.get("name") == role for r in roles)
