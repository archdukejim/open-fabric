import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import AGENT_CREDS, KV_MOUNTS, POLICIES, SETUP_CREDS

# AppRole -> (policy, credentials file)
ROLES = {"fabric-setup": ("fabric-setup", SETUP_CREDS), "fabric-agent": ("fabric-agent", AGENT_CREDS)}


def _call(v, token, method, path, body=None, ok=(200, 204)):
    status, data = bao_request(v, method, path, token=token, body=body)
    if status not in ok:
        raise ValidationError(f"OpenBao {method} {path}: {data.get('errors') or status}")
    return data


def _login_works(v, creds):
    status, _ = bao_request(v, "POST", "auth/approle/login",
                            body={"role_id": creds.get("role_id"), "secret_id": creds.get("secret_id")})
    return status == 200


def configure_openbao(v, token):
    """Bring OpenBao to fabric's configuration; safe to re-run (converges):
    AppRole auth, KV v2 at fabric/ and apps/, the
    fabric-setup and fabric-agent policies and AppRoles (tokens and secret
    IDs only usable from fabric_net, i.e. this host), and their credentials
    in <openbao_key_dir> (root, 0400). Returns the list of changes made."""
    changes = []
    if "approle/" not in _call(v, token, "GET", "sys/auth"):
        _call(v, token, "POST", "sys/auth/approle", {"type": "approle"})
        changes.append("AppRole auth")
    mounts = _call(v, token, "GET", "sys/mounts")
    for mount, about in KV_MOUNTS.items():
        if mount not in mounts:
            _call(v, token, "POST", f"sys/mounts/{mount.rstrip('/')}",
                  {"type": "kv", "options": {"version": "2"}, "description": about})
            changes.append(f"KV {mount}")
    for name, policy in POLICIES.items():
        current = bao_request(v, "GET", f"sys/policies/acl/{name}", token=token)[1].get("data", {}).get("policy")
        if (current or "").strip() != policy.strip():
            _call(v, token, "PUT", f"sys/policies/acl/{name}", {"policy": policy})
            changes.append(f"policy {name}")
    cidrs = [v.get("fabric_subnet", "10.255.0.0/24")]
    for role, (policy, creds_name) in ROLES.items():
        _call(v, token, "POST", f"auth/approle/role/{role}",
              {"token_policies": [policy], "token_ttl": "15m", "token_max_ttl": "30m",
               "token_bound_cidrs": cidrs, "secret_id_bound_cidrs": cidrs, "secret_id_num_uses": 0,
               "secret_id_ttl": "0"})
        path = os.path.join(v["openbao_key_dir"], creds_name)
        creds = {}
        if os.path.exists(path):
            with open(path) as f:
                creds = json.load(f)
        if not creds or not _login_works(v, creds):
            role_id = _call(v, token, "GET", f"auth/approle/role/{role}/role-id")["data"]["role_id"]
            secret_id = _call(v, token, "POST", f"auth/approle/role/{role}/secret-id")["data"]["secret_id"]
            write_private_file(path, json.dumps({"role_id": role_id, "secret_id": secret_id}) + "\n", 0, 0, 0o400)
            changes.append(f"AppRole {role} credentials")
    return changes
