"""Assert the Keycloak state produced by keycloak_bootstrap.py via the admin API."""
import os
import sys

sys.path[0:0] = [os.path.join(os.environ["REPO"], "src"), os.environ["REPO"]]
from fabriclib.keycloak.admin_client import Admin  # noqa: E402
from webui.tlsclient import TLSClient  # noqa: E402

W = os.environ["W"]
kc = Admin(TLSClient("10.254.9.60", 8443, "sso.lan.j-j.family", f"{W}/opt/stepca/data/certs/root_ca.crt"),
           "admin", "KcAdmin1")
R = "/lan.j-j.family"


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


realm = kc.call("GET", R)[1]
check("realm has brute-force protection", realm.get("bruteForceProtected") is True)

comps = kc.call("GET", f"{R}/components?type=org.keycloak.storage.UserStorageProvider")[1]
ldap = [c for c in comps if c["providerId"] == "ldap"]
check("exactly one LDAP provider", len(ldap) == 1, comps)
cfg = ldap[0]["config"]
check("LDAP provider points at 389-DS over LDAPS", cfg["connectionUrl"] == ["ldaps://ldap.lan.j-j.family:3636"]
      and cfg["vendor"] == ["rhds"], cfg.get("connectionUrl"))
st, sync = kc.call("POST", f"{R}/user-storage/{ldap[0]['id']}/sync?action=triggerFullSync")
check("full user sync over LDAPS works", st == 200 and not sync.get("failed"), sync)

users = kc.call("GET", f"{R}/users?username=jim&exact=true")[1]
check("LDAP user jim visible in Keycloak", len(users) == 1, users)
if users:
    roles = kc.call("GET", f"{R}/users/{users[0]['id']}/role-mappings/realm/composite")[1]
    check("jim gets fabric-admin via LDAP admins group", any(r["name"] == "fabric-admin" for r in roles),
          [r["name"] for r in roles])

client = kc.call("GET", f"{R}/clients?clientId=fabric-webui")[1][0]
check("client: confidential, code flow only", not client["publicClient"] and client["standardFlowEnabled"]
      and not client["implicitFlowEnabled"] and not client["directAccessGrantsEnabled"]
      and not client.get("serviceAccountsEnabled"))
check("client: exact redirect URI", client["redirectUris"] == ["https://mgr.lan.j-j.family/oidc/callback"],
      client["redirectUris"])
check("client: PKCE S256 required", client["attributes"].get("pkce.code.challenge.method") == "S256")
check("client: fullScopeAllowed off", client["fullScopeAllowed"] is False)
secret = kc.call("GET", f"{R}/clients/{client['id']}/client-secret")[1]
check("client: secret matches fabric-secrets.yml", secret.get("value") == "OidcSecret1")
scoped = kc.call("GET", f"{R}/clients/{client['id']}/scope-mappings/realm")[1]
names = {r["name"] for r in scoped}
check("client: only fabric's roles in scope (permissions + bundles), nothing else",
      "fabric-admin" in names and "fabric:dns:write" in names and "fabric-auditor" in names
      and all(n.startswith("fabric:") or n.startswith("fabric-") for n in names), sorted(names))
admin = kc.call("GET", f"{R}/roles/fabric-admin")[1]
comp = {r["name"] for r in kc.call("GET", f"{R}/roles-by-id/{admin['id']}/composites")[1]}
aud = kc.call("GET", f"{R}/roles/fabric-auditor")[1]
aud_comp = {r["name"] for r in kc.call("GET", f"{R}/roles-by-id/{aud['id']}/composites")[1]}
check("bundles: fabric-admin holds every permission; fabric-auditor only read ones",
      "fabric:vault:unlock" in comp and "fabric:dns:read" in aud_comp
      and not any(n.endswith((":write", ":admin", ":unlock", ":issue", ":sign")) for n in aud_comp), (comp, aud_comp))

flows = {f["alias"]: f["id"] for f in kc.call("GET", f"{R}/authentication/flows")[1]}
check("client bound to MFA browser flow", flows.get("fabric-webui-mfa")
      and client.get("authenticationFlowBindingOverrides", {}).get("browser") == flows["fabric-webui-mfa"],
      (sorted(flows), client.get("authenticationFlowBindingOverrides")))
execs = kc.call("GET", f"{R}/authentication/flows/fabric-webui-mfa/executions")[1]
otp = [e for e in execs if e.get("providerId") == "auth-otp-form"]
check("OTP form REQUIRED in MFA flow", otp and all(e["requirement"] == "REQUIRED" for e in otp),
      [(e.get("displayName"), e["requirement"], e.get("level")) for e in execs])
browser = kc.call("GET", f"{R}/authentication/flows/browser/executions")[1]
check("realm default browser flow untouched",
      all(e["requirement"] != "REQUIRED" for e in browser if e.get("providerId") == "auth-otp-form"))
