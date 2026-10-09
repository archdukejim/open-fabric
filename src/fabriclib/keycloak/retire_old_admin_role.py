import urllib.parse

from fabriclib.rbac.permissions import OLD_ADMIN_ROLE


def retire_old_admin_role(kc, realm, admin_role):
    """Purpose: remove the admin role's name before 0.6.4 (fabric-admin, now the first admin's user name: 2.1.6.33)
             once the realm has the new one, so one name never means both a person and a role.
    Inputs:  kc — admin_client.Admin; realm — realm name; admin_role — the admin role in use (webui_admin_role).
    Returns: True when the old role was removed; False when there was none, or when it is still the one in use (an
             install that set webui_admin_role: fabric-admin itself), or when it is not fabric's (another
             description: left alone).
    Fails:   SystemExit from kc.call on an admin API error.
    Feeds:   configure_keycloak."""
    if admin_role == OLD_ADMIN_ROLE:
        return False
    path = f"/{urllib.parse.quote(realm, safe='')}/roles/{OLD_ADMIN_ROLE}"
    status, rep = kc.call("GET", path, allow=(404,))
    if status == 404 or (rep or {}).get("description") != "fabric bundle: admin":
        return False
    kc.call("DELETE", path)
    return True
