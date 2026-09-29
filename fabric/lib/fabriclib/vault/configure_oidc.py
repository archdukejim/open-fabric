import os

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import OIDC_BUNDLE_POLICIES, OIDC_CLIENT_ID, OIDC_MOUNT, OIDC_ROLE


def _call(v, token, method, path, body=None):
    status, data = bao_request(v, method, path, token=token, body=body)
    if status not in (200, 204):
        raise ValidationError(f"OpenBao {method} {path}: {data.get('errors') or status}")
    return data


def configure_oidc(v, token, client_secret):
    """Sign-in with Keycloak for people (OpenBao's own UI at
    https://vault.<domain>/ui). Converges: OIDC auth at auth/oidc, discovery
    at Keycloak's realm verified against the fabric root CA, one role
    (TOTP is enforced by the Keycloak client's login flow). OpenBao checks the discovery document when the config is written, so
    Keycloak must be up. The role admits the bundles in OIDC_BUNDLE_POLICIES
    (the `roles` claim is also the groups claim); each bundle is an external
    identity group carrying its policy, so a person gets exactly their
    bundles' policies. Returns the changes made."""
    changes = []
    if f"{OIDC_MOUNT}/" not in _call(v, token, "GET", "sys/auth"):
        _call(v, token, "POST", f"sys/auth/{OIDC_MOUNT}",
              {"type": "oidc", "description": "people: Keycloak single sign-on"})
        changes.append("OIDC auth")
    with open(os.path.join(v["deploy_base_dir"], "stepca/data/certs/root_ca.crt")) as f:
        ca = f.read()
    realm = v.get("webui_realm") or v["domain"]
    config = {"oidc_discovery_url": f"https://{v['hostname_keycloak']}/realms/{realm}",
              "oidc_discovery_ca_pem": ca, "oidc_client_id": OIDC_CLIENT_ID,
              "oidc_client_secret": client_secret, "default_role": OIDC_ROLE}
    current = bao_request(v, "GET", f"auth/{OIDC_MOUNT}/config", token=token)[1].get("data", {})
    if any(current.get(k) != config[k] for k in ("oidc_discovery_url", "oidc_discovery_ca_pem", "oidc_client_id",
                                                  "default_role")) or not current:
        changes.append("OIDC config")
    # The client secret is never read back, so the config is always written (idempotent).
    _call(v, token, "POST", f"auth/{OIDC_MOUNT}/config", config)
    base = f"https://{v['hostname_openbao']}"
    bundles = {(v.get("webui_admin_role", "fabric-admin") if b == "admin" else b): policy
               for b, policy in OIDC_BUNDLE_POLICIES.items()}
    _call(v, token, "POST", f"auth/{OIDC_MOUNT}/role/{OIDC_ROLE}", {
        "role_type": "oidc", "user_claim": "preferred_username", "oidc_scopes": ["openid"],
        "bound_audiences": [OIDC_CLIENT_ID],
        "allowed_redirect_uris": [f"{base}/ui/vault/auth/{OIDC_MOUNT}/oidc/callback"],
        "bound_claims": {"roles": sorted(bundles)}, "groups_claim": "roles",
        "token_policies": [], "token_ttl": "1h", "token_max_ttl": "8h", "token_type": "service"})
    accessor = _call(v, token, "GET", "sys/auth")[f"{OIDC_MOUNT}/"]["accessor"]
    for bundle, policy in bundles.items():
        status, group = bao_request(v, "GET", f"identity/group/name/{bundle}", token=token)
        if status != 200:
            group = _call(v, token, "POST", "identity/group",
                          {"name": bundle, "type": "external", "policies": [policy]})
            changes.append(f"group {bundle}")
        elif group["data"].get("policies") != [policy]:
            _call(v, token, "POST", f"identity/group/name/{bundle}", {"type": "external", "policies": [policy]})
        gid = group["data"]["id"]
        alias = (group["data"].get("alias") or {}) if status == 200 else {}
        if alias.get("name") != bundle or alias.get("mount_accessor") != accessor:
            _call(v, token, "POST", "identity/group-alias", {"name": bundle, "mount_accessor": accessor,
                                                              "canonical_id": gid})
    return changes
