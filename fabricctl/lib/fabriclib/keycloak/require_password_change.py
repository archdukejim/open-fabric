import os
import time

from fabriclib.common.errors import ValidationError


def require_password_change(v, s, user):
    """Purpose: Make Keycloak ask an LDAP-federated user for a new password at the next login, so a
             generated initial password works only once.
    Inputs:  v — fabric vars (as keycloak_admin); s — fabric's secrets (Keycloak admin credentials);
             user — username.
    Returns: None (UPDATE_PASSWORD added to the user's required actions if missing).
    Fails:   ValidationError "Keycloak does not see LDAP user <user>" after 10 lookups 3 s apart;
             SystemExit from keycloak_bootstrap.Admin on an admin API error or failed login (not
             converted); OSError / ssl errors if Keycloak is unreachable.
    Feeds:   setup/create_admin.py run (only when ensure_admin_user created the user).
    Notes:   the lookup also imports the user from 389-DS into Keycloak; the retries cover federation
             still settling right after bootstrap. Builds its own admin client (same as keycloak_admin).
    """
    import keycloak_bootstrap as kb          # fabric/lib: admin client pinned to the fabric root CA
    from webui.tlsclient import TLSClient

    ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    kc = kb.Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
                  s["keycloak_admin_user"], s["keycloak_admin_password"])
    realm = kb.q(v.get("webui_realm") or v["domain"])
    for _ in range(10):                     # federation may still be settling right after bootstrap
        _, found = kc.call("GET", f"/{realm}/users?username={kb.q(user)}&exact=true")
        if found:
            break
        time.sleep(3)
    else:
        raise ValidationError(f"Keycloak does not see LDAP user {user}")
    rep = found[0]
    actions = set(rep.get("requiredActions") or [])
    if "UPDATE_PASSWORD" not in actions:
        rep["requiredActions"] = sorted(actions | {"UPDATE_PASSWORD"})
        kc.call("PUT", f"/{realm}/users/{rep['id']}", rep)
