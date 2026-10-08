import urllib.parse

from fabriclib.rbac.permissions import BUNDLES, PERMISSIONS, PREFIX


def _q(s):
    """Purpose: URL-encode one path or query component for the Keycloak admin API (nothing kept, not "/").
    Inputs:  s — str (a realm, user name, client id or role name).
    Returns: the percent-encoded str.
    Fails:   never for a str.
    Feeds:   _role, ensure_rbac_roles.
    """
    return urllib.parse.quote(s, safe="")


def _role(kc, realm, name, description):
    """Purpose: Get a realm role, creating it first when it does not exist.
    Inputs:  kc — admin_client.Admin; realm — realm name; name — role name; description — used only
             when the role is created.
    Returns: the role representation (dict with "id", "name", ...).
    Fails:   SystemExit from kc.call on an admin API error (404 on the first lookup is expected).
    Feeds:   ensure_rbac_roles.
    """
    status, rep = kc.call("GET", f"/{_q(realm)}/roles/{_q(name)}", allow=(404,))
    if status == 404:
        kc.call("POST", f"/{_q(realm)}/roles", {"name": name, "description": description})
        rep = kc.call("GET", f"/{_q(realm)}/roles/{_q(name)}")[1]
    return rep


def ensure_rbac_roles(kc, realm, admin_role):
    """Purpose: Converge fabric's access control in Keycloak (design 2.1.6.1): one realm role per permission
             (fabric:<area>:<action>) and one composite role per bundle holding exactly its permissions.
    Inputs:  kc — admin_client.Admin; realm — realm name; admin_role — name of the "admin" bundle
             (webui_admin_role, default fabric-admin). Reads rbac/permissions PERMISSIONS, BUNDLES, PREFIX.
    Returns: {role name: representation} for every fabric role (permissions and bundles).
    Fails:   SystemExit from kc.call on any admin API error; OSError / ssl errors if Keycloak is unreachable.
    Feeds:   configure_keycloak: group grants (grant_role_to_group) and client scope mappings
             (ensure_client, ensure_openbao_client).
    Notes:   missing fabric: members of a bundle are added and extra ones removed; non-fabric composites
             are left alone. Descriptions are set only when a role is created.
    """
    reps = {PREFIX + p: _role(kc, realm, PREFIX + p, f"fabric: {about}") for p, about in PERMISSIONS.items()}
    for bundle, perms in BUNDLES.items():
        name = admin_role if bundle == "admin" else bundle
        rep = _role(kc, realm, name, f"fabric bundle: {bundle}")
        reps[name] = rep
        path = f"/{_q(realm)}/roles-by-id/{rep['id']}/composites"
        _, current = kc.call("GET", path)
        have = {r["name"] for r in current or [] if r["name"].startswith(PREFIX)}
        want = {PREFIX + p for p in perms}
        if want - have:
            kc.call("POST", path, [reps[n] for n in sorted(want - have)])
        if have - want:
            kc.call("DELETE", path, [r for r in current if r["name"] in have - want])
    return reps
