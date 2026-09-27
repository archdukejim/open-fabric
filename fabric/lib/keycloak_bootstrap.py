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
  * realm role <webui_admin_role>, granted to group <webui_admin_group>
  * confidential OIDC client "fabric-webui" (code flow + PKCE S256, exact
    redirect URI, only the admin role in scope, roles in the ID token)
  * browser flow "fabric-webui-mfa" with TOTP required, bound to fabric-webui
"""
import argparse
import os
import sys
import time
import urllib.parse

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from webui.tlsclient import TLSClient  # noqa: E402

CLIENT_ID = "fabric-webui"
MFA_FLOW = "fabric-webui-mfa"
USER_STORAGE = "org.keycloak.storage.UserStorageProvider"
LDAP_MAPPER = "org.keycloak.storage.ldap.mappers.LDAPStorageMapper"


class Admin:
    def __init__(self, tls, user, password):
        self.tls, self.user, self.password = tls, user, password
        self.token, self.expires = None, 0

    def _auth(self):
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
        self._auth()
        status, payload = self.tls.request(method, "/admin/realms" + path, body=body,
                                           headers={"Authorization": f"Bearer {self.token}"})
        if status in allow:
            return status, payload
        if status not in ok:
            raise SystemExit(f"{method} {path} failed ({status}): {payload}")
        return status, payload


def q(s):
    return urllib.parse.quote(str(s), safe="")


def step(msg):
    print(f"  - {msg}")


def ensure_realm(kc, realm, display):
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


def ensure_role(kc, realm, role):
    status, rep = kc.call("GET", f"/{q(realm)}/roles/{q(role)}", allow=(404,))
    if status == 404:
        kc.call("POST", f"/{q(realm)}/roles", {"name": role, "description": "Full access to the webui management UI"})
        rep = kc.call("GET", f"/{q(realm)}/roles/{q(role)}")[1]
        step(f"created realm role {role}")
    return rep


def grant_role_to_group(kc, realm, role_rep, group_name):
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


def ensure_client(kc, realm, v, s, role_rep, flow_id):
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

    _, scoped = kc.call("GET", f"/{q(realm)}/clients/{cid}/scope-mappings/realm")
    if not any(r["name"] == role_rep["name"] for r in scoped):
        kc.call("POST", f"/{q(realm)}/clients/{cid}/scope-mappings/realm", [role_rep])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", default="/opt/fabric/config/vars.yaml")
    ap.add_argument("--secrets", default="/opt/fabric/config/fabric-secrets.yml")
    args = ap.parse_args()
    with open(args.vars) as f:
        v = yaml.safe_load(f)
    with open(args.secrets) as f:
        s = yaml.safe_load(f)

    ca = os.path.join(v["deploy_base_dir"], "stepca/data/certs/root_ca.crt")
    kc = Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
               s["keycloak_admin_user"], s["keycloak_admin_password"])
    realm = v.get("webui_realm") or v["domain"]

    print(f"Configuring Keycloak realm {realm}...")
    realm_id = ensure_realm(kc, realm, v.get("friendly_name") or v["domain"])
    if v.get("install_ldap", True):
        ldap_id = ensure_ldap(kc, realm, realm_id, v, s)
        ensure_group_mapper(kc, realm, ldap_id, v)
    if v.get("install_webui"):
        role = ensure_role(kc, realm, v.get("webui_admin_role", "fabric-admin"))
        grant_role_to_group(kc, realm, role, v.get("webui_admin_group", "admins"))
        flow_id = ensure_mfa_flow(kc, realm)
        ensure_client(kc, realm, v, s, role, flow_id)
    print("Keycloak configuration complete.")


if __name__ == "__main__":
    main()
