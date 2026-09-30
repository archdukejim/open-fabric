#!/usr/bin/env python3
"""Idempotently configure Keycloak for fabric.

  sudo python3 keycloak_bootstrap.py [--vars /opt/fabric/config/vars.yaml]
                                     [--secrets /opt/fabric/config/fabric-secrets.yml]

Talks to the Keycloak admin REST API over TLS pinned to the core root CA
(no credentials on any command line). Safe to re-run: it converges.

  * realm <webui_realm> with brute-force protection
  * LDAP user federation -> 389 Directory Server (an existing LDAP
    provider is updated in place)
  * group mapper for ou=groups, synced into Keycloak
  * fabric's access control (design D19): a realm role per permission
    (fabric:<area>:<action>) and a composite role per bundle; <webui_admin_role>
    is the admin bundle, granted to <webui_admin_group>; other bundles are
    granted to the ldap_groups that name them (fabriclib/keycloak/ensure_rbac_roles.py)
  * confidential OIDC client "fabric-webui" (code flow + PKCE S256, exact
    redirect URI, only the admin role in scope, roles in the ID token)
  * browser flow "fabric-webui-mfa" with TOTP required, bound to fabric-webui
  * confidential OIDC client "fabric-openbao" for OpenBao's own UI (same
    flow and role claim; fabriclib/keycloak/ensure_openbao_client.py)
"""
import argparse
import os
import sys
import time
import urllib.parse

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from webui.tlsclient import TLSClient  # noqa: E402
from fabriclib.keycloak.ensure_openbao_client import ensure_openbao_client  # noqa: E402
from fabriclib.keycloak.ensure_rbac_roles import ensure_rbac_roles  # noqa: E402
from fabriclib.secrets.load_secrets import load_secrets  # noqa: E402

CLIENT_ID = "fabric-webui"
MFA_FLOW = "fabric-webui-mfa"
USER_STORAGE = "org.keycloak.storage.UserStorageProvider"
LDAP_MAPPER = "org.keycloak.storage.ldap.mappers.LDAPStorageMapper"


class Admin:
    def __init__(self, tls, user, password):
        """Purpose: a Keycloak admin REST client that logs in as the master-realm admin on first use.
        Inputs:  tls — a webui.tlsclient.TLSClient pinned to the fabric root CA; user, password — str, the Keycloak
                 admin credentials from fabric's secrets (never on a command line).
        Returns: None (no request is made yet; token and expiry start empty).
        Fails:   never.
        Feeds:   main; fabriclib/keycloak/keycloak_admin.py, require_password_change.py, user_has_role.py;
                 tests/keycloak/verify.py, tests/host/reset_user.py."""
        self.tls, self.user, self.password = tls, user, password
        self.token, self.expires = None, 0

    def _auth(self):
        """Purpose: get or refresh the admin access token (password grant, client admin-cli, master realm).
        Inputs:  none; uses self.tls, self.user, self.password; reuses the token until 15 s before it expires.
        Returns: None; sets self.token and self.expires.
        Fails:   SystemExit("Keycloak admin login failed (<status>): <body>") on any non-200 reply; OSError/ssl errors
                 from the TLS connection propagate.
        Feeds:   Admin.call."""
        if self.token and time.time() < self.expires - 15:
            return
        status, body = self.tls.request("POST", "/realms/master/protocol/openid-connect/token", form={
            "grant_type": "password", "client_id": "admin-cli",
            "username": self.user, "password": self.password})
        if status != 200:
            raise SystemExit(f"Keycloak admin login failed ({status}): {body}")
        self.token = body["access_token"]
        self.expires = time.time() + int(body.get("expires_in", 60))

    def call(self, method, path, body=None, ok=(200, 201, 204), allow=()):
        """Purpose: make one authenticated call to the admin API under /admin/realms.
        Inputs:  method — HTTP method; path — str appended to /admin/realms (callers quote names with q); body —
                 JSON-able object or None; ok — statuses treated as success (default 200, 201, 204); allow — extra
                 statuses returned to the caller instead of failing (e.g. 404).
        Returns: (status, payload) — payload is parsed JSON, text, or {"location": ...} for an empty reply with
                 Location.
        Fails:   SystemExit("<method> <path> failed (<status>): <payload>") for any other status; SystemExit from _auth;
                 OSError/ssl errors from the connection.
        Feeds:   every ensure_* function here, grant_role_to_group; fabriclib/keycloak/* (ensure_rbac_roles,
                 ensure_openbao_client and the admin helpers); tests/keycloak/verify.py."""
        self._auth()
        status, payload = self.tls.request(method, "/admin/realms" + path, body=body,
                                           headers={"Authorization": f"Bearer {self.token}"})
        if status in allow:
            return status, payload
        if status not in ok:
            raise SystemExit(f"{method} {path} failed ({status}): {payload}")
        return status, payload


def q(s):
    """Purpose: URL-quote one path or query component (every character outside [A-Za-z0-9_.-~] escaped, "/" too).
    Inputs:  s — any value, converted with str().
    Returns: str, the quoted text.
    Fails:   never.
    Feeds:   every Admin.call path here; fabriclib/keycloak/require_password_change.py, user_has_role.py;
             tests/keycloak/verify.py, tests/host/reset_user.py."""
    return urllib.parse.quote(str(s), safe="")


def step(msg):
    """Purpose: print one progress line ("  - <msg>").
    Inputs:  msg — str.
    Returns: None.
    Fails:   never.
    Feeds:   main and every ensure_* function here."""
    print(f"  - {msg}")


def ensure_realm(kc, realm, display):
    """Purpose: create the realm if missing and set its login protections (brute-force lockout after 5 failures,
             temporary lockout up to 15 min, no e-mail login, no duplicate e-mails).
    Inputs:  kc — Admin; realm — realm name; display — display name, used only on creation.
    Returns: str, the realm's internal id.
    Fails:   SystemExit from Admin.call on any unexpected status.
    Feeds:   main (the id is the parent of the LDAP federation in ensure_ldap)."""
    status, rep = kc.call("GET", f"/{q(realm)}", allow=(404,))
    if status == 404:
        kc.call("POST", "", {"realm": realm, "enabled": True, "displayName": display})
        step(f"created realm {realm}")
    kc.call("PUT", f"/{q(realm)}", {
        "bruteForceProtected": True, "permanentLockout": False, "failureFactor": 5,
        "maxFailureWaitSeconds": 900, "waitIncrementSeconds": 60,
        "loginWithEmailAllowed": False, "duplicateEmailsAllowed": False,
    })
    return kc.call("GET", f"/{q(realm)}")[1]["id"]


def ensure_ldap(kc, realm, realm_id, v, s):
    """Purpose: create or update the realm's LDAP user federation to 389-DS ("389-DS": ldaps on port 3636, users under
             ou=users,ou=accounts, bound as cn=keycloak_admin, writable, imports users).
    Inputs:  kc — Admin; realm — realm name; realm_id — parent id from ensure_realm; v — vars (ldap_base_dn,
             hostname_ldap); s — secrets (ldap_keycloak_password).
    Returns: str, the federation component id. An existing ldap provider is updated in place (fabric's settings win,
             other settings kept).
    Fails:   SystemExit from Admin.call; KeyError if a needed var or secret is missing; StopIteration if a created
             provider cannot be found again.
    Feeds:   main (the id is passed to ensure_group_mapper)."""
    base = v["ldap_base_dn"]
    config = {
        "enabled": ["true"],
        "vendor": ["rhds"],
        "editMode": ["WRITABLE"],
        "syncRegistrations": ["true"],
        "importEnabled": ["true"],
        "usernameLDAPAttribute": ["uid"],
        "rdnLDAPAttribute": ["uid"],
        "uuidLDAPAttribute": ["entryUUID"],
        "userObjectClasses": ["inetOrgPerson, organizationalPerson"],
        "connectionUrl": [f"ldaps://{v['hostname_ldap']}:3636"],
        "usersDn": [f"ou=users,ou=accounts,{base}"],
        "authType": ["simple"],
        "bindDn": [f"cn=keycloak_admin,ou=admins,ou=accounts,{base}"],
        "bindCredential": [s["ldap_keycloak_password"]],
        "searchScope": ["1"],
        "useTruststoreSpi": ["always"],
        "startTls": ["false"],
        "connectionPooling": ["true"],
        "pagination": ["true"],
        "usePasswordModifyExtendedOp": ["true"],
        "trustEmail": ["true"],
        "batchSizeForSync": ["1000"],
    }
    _, comps = kc.call("GET", f"/{q(realm)}/components?type={q(USER_STORAGE)}")
    ldap = next((c for c in comps if c.get("providerId") == "ldap"), None)
    if ldap is None:
        status, created = kc.call("POST", f"/{q(realm)}/components", {
            "name": "389-DS", "providerId": "ldap", "providerType": USER_STORAGE,
            "parentId": realm_id, "config": config})
        _, comps = kc.call("GET", f"/{q(realm)}/components?type={q(USER_STORAGE)}")
        ldap = next(c for c in comps if c.get("providerId") == "ldap")
        step("created LDAP federation (389-DS)")
    else:
        ldap["name"] = "389-DS"
        ldap["config"] = {**ldap.get("config", {}), **config}
        kc.call("PUT", f"/{q(realm)}/components/{ldap['id']}", ldap)
        step(f"updated LDAP federation {ldap['id']} -> {config['connectionUrl'][0]}")
    return ldap["id"]


def ensure_group_mapper(kc, realm, ldap_id, v):
    """Purpose: create or update the LDAP group mapper (groupOfNames under ou=groups, LDAP_ONLY) and sync the
             directory's groups into Keycloak.
    Inputs:  kc — Admin; realm — realm name; ldap_id — federation id from ensure_ldap; v — vars (ldap_base_dn).
    Returns: None.
    Fails:   SystemExit from Admin.call (including a failed sync); KeyError if ldap_base_dn is missing; StopIteration if
             a created mapper cannot be found again.
    Feeds:   main (the synced groups are what grant_role_to_group looks up)."""
    config = {
        "groups.dn": [f"ou=groups,{v['ldap_base_dn']}"],
        "group.name.ldap.attribute": ["cn"],
        "group.object.classes": ["groupOfNames"],
        "preserve.group.inheritance": ["false"],
        "membership.ldap.attribute": ["member"],
        "membership.attribute.type": ["DN"],
        "membership.user.ldap.attribute": ["uid"],
        "memberof.ldap.attribute": ["memberOf"],
        "mode": ["LDAP_ONLY"],
        "user.roles.retrieve.strategy": ["LOAD_GROUPS_BY_MEMBER_ATTRIBUTE"],
        "drop.non.existing.groups.during.sync": ["false"],
    }
    _, mappers = kc.call("GET", f"/{q(realm)}/components?parent={ldap_id}&type={q(LDAP_MAPPER)}")
    mapper = next((m for m in mappers if m.get("providerId") == "group-ldap-mapper"), None)
    if mapper is None:
        kc.call("POST", f"/{q(realm)}/components", {
            "name": "LDAP Groups", "providerId": "group-ldap-mapper", "providerType": LDAP_MAPPER,
            "parentId": ldap_id, "config": config})
        _, mappers = kc.call("GET", f"/{q(realm)}/components?parent={ldap_id}&type={q(LDAP_MAPPER)}")
        mapper = next(m for m in mappers if m.get("providerId") == "group-ldap-mapper")
        step("created LDAP group mapper")
    else:
        mapper["config"] = {**mapper.get("config", {}), **config}
        kc.call("PUT", f"/{q(realm)}/components/{mapper['id']}", mapper)
    kc.call("POST", f"/{q(realm)}/user-storage/{ldap_id}/mappers/{mapper['id']}/sync?direction=fedToKeycloak")
    step("synced LDAP groups into Keycloak")


def grant_role_to_group(kc, realm, role_rep, group_name):
    """Purpose: give a Keycloak group a realm role, if it does not have it yet.
    Inputs:  kc — Admin; realm — realm name; role_rep — the role representation (needs "name"); group_name — exact group
             name.
    Returns: None; prints a step when granted. A missing group prints "! group '<name>' not found ... manually" and
             returns without error.
    Fails:   SystemExit from Admin.call.
    Feeds:   main (the admin bundle to webui_admin_group, and each ldap_groups bundle)."""
    _, groups = kc.call("GET", f"/{q(realm)}/groups?search={q(group_name)}&exact=true&briefRepresentation=true")
    group = next((g for g in groups if g.get("name") == group_name), None)
    if group is None:
        print(f"  ! group '{group_name}' not found in Keycloak; assign role '{role_rep['name']}' to admins manually")
        return
    _, mapped = kc.call("GET", f"/{q(realm)}/groups/{group['id']}/role-mappings/realm")
    if not any(r["name"] == role_rep["name"] for r in mapped):
        kc.call("POST", f"/{q(realm)}/groups/{group['id']}/role-mappings/realm", [role_rep])
        step(f"granted {role_rep['name']} to group {group_name}")


def ensure_mfa_flow(kc, realm):
    """Purpose: make sure the "fabric-webui-mfa" browser flow exists (a copy of the stock browser flow) with its
             conditional second-factor sub-flow forced to REQUIRED, OTP REQUIRED and its "user configured" conditions
             DISABLED, so every user must enrol and use TOTP.
    Inputs:  kc — Admin; realm — realm name.
    Returns: str, the flow's id.
    Fails:   SystemExit from Admin.call; StopIteration if the flow is missing after the copy.
    Feeds:   main -> ensure_client and fabriclib/keycloak/ensure_openbao_client.py (browser flow override)."""
    _, flows = kc.call("GET", f"/{q(realm)}/authentication/flows")
    if not any(f["alias"] == MFA_FLOW for f in flows):
        kc.call("POST", f"/{q(realm)}/authentication/flows/browser/copy", {"newName": MFA_FLOW})
        step(f"created authentication flow {MFA_FLOW}")
    _, execs = kc.call("GET", f"/{q(realm)}/authentication/flows/{q(MFA_FLOW)}/executions")

    # The stock browser flow ends in a CONDITIONAL "... Conditional OTP/2FA"
    # sub-flow. Make it REQUIRED with OTP REQUIRED (users without TOTP are
    # made to enrol) and switch off its "user configured" conditions.
    in_second_factor = False
    changed = False
    for ex in execs:
        level = ex.get("level", 0)
        if ex.get("authenticationFlow") and "conditional" in ex.get("displayName", "").lower() and level == 1:
            in_second_factor, desired = True, "REQUIRED"
        elif in_second_factor and level >= 2:
            pid = ex.get("providerId", "")
            if pid == "auth-otp-form":
                desired = "REQUIRED"
            elif pid.startswith("conditional-"):
                desired = "DISABLED"
            else:
                continue
        else:
            in_second_factor = False
            continue
        if ex.get("requirement") != desired and desired in ex.get("requirementChoices", [desired]):
            ex["requirement"] = desired
            kc.call("PUT", f"/{q(realm)}/authentication/flows/{q(MFA_FLOW)}/executions", ex)
            changed = True
    if changed:
        step("enforced TOTP in the fabric-webui login flow")
    _, flows = kc.call("GET", f"/{q(realm)}/authentication/flows")
    return next(f["id"] for f in flows if f["alias"] == MFA_FLOW)


def ensure_client(kc, realm, v, s, role_reps, flow_id):
    """Purpose: create or update the confidential OIDC client "fabric-webui" for the web UI: code flow with PKCE S256,
             exact redirect https://<hostname_mgr>/oidc/callback, no direct/implicit grants, the TOTP flow bound, a
             "roles" claim in the ID token, and every given realm role in its scope.
    Inputs:  kc — Admin; realm — realm name; v — vars (hostname_mgr); s — secrets (webui_oidc_secret); role_reps — list
             of role representations to put in scope; flow_id — from ensure_mfa_flow.
    Returns: None. Existing attributes are merged; missing scope roles are added (none are removed).
    Fails:   SystemExit from Admin.call; KeyError if hostname_mgr or webui_oidc_secret is missing.
    Feeds:   main (when install_webui)."""
    base = f"https://{v['hostname_mgr']}"
    rep = {
        "clientId": CLIENT_ID,
        "name": "Fabric web UI",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": s["webui_oidc_secret"],
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "frontchannelLogout": True,
        "fullScopeAllowed": False,
        "rootUrl": base,
        "baseUrl": "/",
        "redirectUris": [f"{base}/oidc/callback"],
        "webOrigins": [base],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": f"{base}/",
        },
        "authenticationFlowBindingOverrides": {"browser": flow_id},
    }
    _, found = kc.call("GET", f"/{q(realm)}/clients?clientId={q(CLIENT_ID)}")
    if found:
        cid = found[0]["id"]
        kc.call("PUT", f"/{q(realm)}/clients/{cid}", {**found[0], **rep,
                                                       "attributes": {**found[0].get("attributes", {}), **rep["attributes"]}})
        step(f"updated client {CLIENT_ID}")
    else:
        kc.call("POST", f"/{q(realm)}/clients", rep)
        cid = kc.call("GET", f"/{q(realm)}/clients?clientId={q(CLIENT_ID)}")[1][0]["id"]
        step(f"created client {CLIENT_ID}")

    _, mappers = kc.call("GET", f"/{q(realm)}/clients/{cid}/protocol-mappers/models")
    if not any(m.get("name") == "realm roles" for m in mappers):
        kc.call("POST", f"/{q(realm)}/clients/{cid}/protocol-mappers/models", {
            "name": "realm roles", "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {"claim.name": "roles", "multivalued": "true", "jsonType.label": "String",
                       "id.token.claim": "true", "access.token.claim": "false",
                       "userinfo.token.claim": "false"}})
        step("added roles claim to fabric-webui ID tokens")

    # every fabric role in scope, so the roles claim carries the person's permissions
    _, scoped = kc.call("GET", f"/{q(realm)}/clients/{cid}/scope-mappings/realm")
    missing = [r for r in role_reps if r["name"] not in {s["name"] for s in scoped}]
    if missing:
        kc.call("POST", f"/{q(realm)}/clients/{cid}/scope-mappings/realm", missing)


def main():
    """Purpose: configure Keycloak for fabric, idempotently: realm, LDAP federation and group sync, fabric's permission
             and bundle roles with their group grants, the TOTP login flow, and the fabric-webui / fabric-openbao
             clients.
    Inputs:  command-line --vars (default /opt/fabric/config/vars.yaml) and --secrets (default
             /opt/fabric/config/fabric-secrets.yml); secrets come from that file or OpenBao (load_secrets). Talks to
             ip_keycloak:8443 with TLS pinned to <deploy_base_dir>/stepca/data/certs/root_ca.crt.
    Returns: None; prints progress and "Keycloak configuration complete.".
    Fails:   SystemExit (exit 1 with the message) from any failed admin call or login; argparse exits 2 on bad
             arguments; OSError/yaml errors reading the vars; ValidationError from load_secrets (OpenBao locked);
             KeyError when a required var or secret is missing.
    Feeds:   `python3 keycloak_bootstrap.py`: fabriclib/setup/start_services.py (setup), manage.sh --keycloak-sync,
             tests/keycloak/run.sh."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", default="/opt/fabric/config/vars.yaml")
    ap.add_argument("--secrets", default="/opt/fabric/config/fabric-secrets.yml")
    args = ap.parse_args()
    with open(args.vars) as f:
        v = yaml.safe_load(f)
    s = load_secrets(args.secrets, v)      # the file, or OpenBao once imported

    ca = os.path.join(v["deploy_base_dir"], "stepca/data/certs/root_ca.crt")
    kc = Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
               s["keycloak_admin_user"], s["keycloak_admin_password"])
    realm = v.get("webui_realm") or v["domain"]

    print(f"Configuring Keycloak realm {realm}...")
    realm_id = ensure_realm(kc, realm, v.get("friendly_name") or v["domain"])
    if v.get("install_ldap", True):
        ldap_id = ensure_ldap(kc, realm, realm_id, v, s)
        ensure_group_mapper(kc, realm, ldap_id, v)
    # The admin role and the TOTP flow serve both the web UI and OpenBao's UI.
    admin_role = v.get("webui_admin_role", "fabric-admin")
    reps = ensure_rbac_roles(kc, realm, admin_role)
    step(f"access control: {len(reps)} fabric roles (permissions and bundles)")
    grant_role_to_group(kc, realm, reps[admin_role], v.get("webui_admin_group", "admins"))
    for group in v.get("ldap_groups") or []:
        if group.get("bundle") in reps:
            grant_role_to_group(kc, realm, reps[group["bundle"]], group["name"])
    flow_id = ensure_mfa_flow(kc, realm)
    if v.get("install_webui"):
        ensure_client(kc, realm, v, s, list(reps.values()), flow_id)
    if s.get("openbao_oidc_secret"):
        step(f"{ensure_openbao_client(kc, realm, v, s['openbao_oidc_secret'], list(reps.values()), flow_id)}"
             " client fabric-openbao")
    print("Keycloak configuration complete.")


if __name__ == "__main__":
    main()
