from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.keycloak.quote import q


def user_has_role(v, s, user, role):
    """Purpose: Whether Keycloak grants a user a realm role, directly or through a group or composite
             (e.g. the LDAP admin group).
    Inputs:  v — fabric vars (as keycloak_admin); s — fabric's secrets (Keycloak admin credentials);
             user — username; role — realm role name.
    Returns: True if the user's effective realm roles include role; False, also when Keycloak does not
             know the user.
    Fails:   SystemExit from the admin client (keycloak/admin_client) on an admin API error or failed login; OSError / ssl
             errors if Keycloak is unreachable; KeyError on missing vars or secrets.
    Feeds:   setup/verify_install.py checks ("Keycloak grants <admin> <role>").
    Notes:   the lookup imports an LDAP user into Keycloak.
    """
    kc, realm = keycloak_admin(v, s)
    realm = q(realm)
    _, found = kc.call("GET", f"/{realm}/users?username={q(user)}&exact=true")
    if not found:
        return False
    _, roles = kc.call("GET", f"/{realm}/users/{found[0]['id']}/role-mappings/realm/composite")
    return any(r.get("name") == role for r in roles)
