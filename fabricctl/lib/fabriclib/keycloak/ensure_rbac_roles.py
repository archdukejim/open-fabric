import urllib.parse

from fabriclib.rbac.permissions import BUNDLES, PERMISSIONS, PREFIX


def _q(s):
    return urllib.parse.quote(s, safe="")


def _role(kc, realm, name, description):
    status, rep = kc.call("GET", f"/{_q(realm)}/roles/{_q(name)}", allow=(404,))
    if status == 404:
        kc.call("POST", f"/{_q(realm)}/roles", {"name": name, "description": description})
        rep = kc.call("GET", f"/{_q(realm)}/roles/{_q(name)}")[1]
    return rep


def ensure_rbac_roles(kc, realm, admin_role):
    """fabric's access control in Keycloak (design D19), converged: one realm
    role per permission (fabric:<area>:<action>) and one composite role per
    bundle holding exactly its permissions; the admin bundle is the web UI
    admin role (`admin_role`, default fabric-admin). Returns {role name:
    representation} for every fabric role (permissions and bundles), for
    client scope mappings and group grants. `kc` is keycloak_bootstrap's
    admin client."""
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
