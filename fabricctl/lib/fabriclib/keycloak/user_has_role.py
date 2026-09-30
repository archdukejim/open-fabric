import os


def user_has_role(v, s, user, role):
    """Purpose: Whether Keycloak grants a user a realm role, directly or through a group or composite
             (e.g. the LDAP admin group).
    Inputs:  v — fabric vars (as keycloak_admin); s — fabric's secrets (Keycloak admin credentials);
             user — username; role — realm role name.
    Returns: True if the user's effective realm roles include role; False, also when Keycloak does not
             know the user.
    Fails:   SystemExit from keycloak_bootstrap.Admin on an admin API error or failed login; OSError / ssl
             errors if Keycloak is unreachable; KeyError on missing vars or secrets.
    Feeds:   setup/verify_install.py checks ("Keycloak grants <admin> <role>").
    Notes:   the lookup imports an LDAP user into Keycloak. Builds its own admin client.
    """
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
