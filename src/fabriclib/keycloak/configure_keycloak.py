import os

import yaml

from fabriclib.keycloak.admin_client import Admin
from fabriclib.keycloak.ensure_adguard_client import ensure_adguard_client
from fabriclib.keycloak.ensure_group_mapper import ensure_group_mapper
from fabriclib.keycloak.ensure_ldap_federation import ensure_ldap_federation
from fabriclib.keycloak.ensure_mfa_flow import ensure_mfa_flow
from fabriclib.keycloak.ensure_openbao_client import ensure_openbao_client
from fabriclib.keycloak.ensure_rbac_roles import ensure_rbac_roles
from fabriclib.keycloak.ensure_realm import ensure_realm
from fabriclib.keycloak.ensure_webui_client import ensure_webui_client
from fabriclib.keycloak.grant_role_to_group import grant_role_to_group
from fabriclib.keycloak.step import step
from fabriclib.federation.common.is_root_site import is_root_site
from fabriclib.secrets.load_secrets import load_secrets


def configure_keycloak(vars_path, secrets_path):
    """Purpose: configure Keycloak for fabric, idempotently: realm, LDAP federation and group sync, fabric's permission
             and bundle roles with their group grants, the TOTP login flow, and the fabric-webui / fabric-openbao
             clients (and fabric-adguard with the DNS filter on).
    Inputs:  vars_path — vars.yaml; secrets_path — the secrets file (or OpenBao once imported: load_secrets). Talks to
             ip_keycloak:8443 with TLS pinned to <deploy_base_dir>/stepca/data/certs/root_ca.crt.
    Returns: None; prints progress and "Keycloak configuration complete.".
    Fails:   SystemExit (with the message) from any failed admin call or login; OSError/yaml errors reading the vars;
             ValidationError from load_secrets (OpenBao locked); KeyError when a required var or secret is missing.
    Feeds:   lib/keycloak_bootstrap.py (setup's start step, `fabricctl --keycloak-sync`, tests/keycloak/run.sh)."""
    from webui.tlsclient import TLSClient          # fabric/lib/webui: the TLS client the web UI uses too
    with open(vars_path) as f:
        v = yaml.safe_load(f)
    s = load_secrets(secrets_path, v)
    ca = os.path.join(v["deploy_base_dir"], "stepca/data/certs/root_ca.crt")
    kc = Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
               s["keycloak_admin_user"], s["keycloak_admin_password"])
    realm = v.get("webui_realm") or v["domain"]

    print(f"Configuring Keycloak realm {realm}...")
    realm_id = ensure_realm(kc, realm, v.get("friendly_name") or v["domain"])
    # fabric's directory, Samba AD (manual 1.6.3.11): people and groups
    writable = is_root_site(os.path.join(v["deploy_base_dir"], "fabric", "config", "federation.yaml"))
    ensure_group_mapper(kc, realm, ensure_ldap_federation(kc, realm, realm_id, v, s, writable), v)
    # The admin role and the TOTP flow serve the web UI, OpenBao's UI and AdGuard's.
    admin_role = v.get("webui_admin_role", "fabric-admin")
    reps = ensure_rbac_roles(kc, realm, admin_role)
    step(f"access control: {len(reps)} fabric roles (permissions and bundles)")
    grant_role_to_group(kc, realm, reps[admin_role], v.get("webui_admin_group", "admins"))
    for group in v.get("ldap_groups") or []:
        if group.get("bundle") in reps:
            grant_role_to_group(kc, realm, reps[group["bundle"]], group["name"])
    flow_id = ensure_mfa_flow(kc, realm)
    roles = list(reps.values())
    if v.get("install_webui"):
        ensure_webui_client(kc, realm, v, s, roles, flow_id)
    if s.get("openbao_oidc_secret"):
        step(f"{ensure_openbao_client(kc, realm, v, s['openbao_oidc_secret'], roles, flow_id)} client fabric-openbao")
    if v.get("install_adguard") and s.get("adguard_oidc_secret"):
        step(f"{ensure_adguard_client(kc, realm, v, s['adguard_oidc_secret'], roles, flow_id)} client fabric-adguard")
    print("Keycloak configuration complete.")
