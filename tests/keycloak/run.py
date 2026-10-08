"""The `keycloak` suite (manual 1.6.2, 1.6.3.11): keycloak_bootstrap against a real Keycloak and a real Samba AD
domain controller, twice (idempotent); the admin API's view of what it made; and a real browser sign-in by the first
admin, created by fabric with a one-time password: Keycloak makes them choose a new one (AD's pwdLastSet), which
lands in AD, then enrol TOTP. Refusals: a disabled person, a person outside the site's groups (D90), an unregistered
redirect URI.
    sudo python3 tests/keycloak/run.py
"""
import hashlib
import hmac
import os
import re
import shutil
import struct
import subprocess
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path[0:0] = [os.path.join(REPO, "src"), REPO, os.path.join(REPO, "tests", "samba")]
from start_dc import start_dc  # noqa: E402
from fabriclib.directory.ensure_admin import ensure_admin  # noqa: E402
from fabriclib.directory.run_op import run_op  # noqa: E402
from fabriclib.keycloak.admin_client import Admin  # noqa: E402
from fabriclib.secrets.random_password import random_password  # noqa: E402
from webui.tlsclient import TLSClient  # noqa: E402

W = os.path.join(os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests"), "keycloak")
NET, SUBNET, DC_IP, KC_IP = "kctest", "10.254.9.0/24", "10.254.9.10", "10.254.9.60"
DC, KC = "kc-dc", "kc-keycloak"
HOST, REALM = "sso.lan.j-j.family", "lan.j-j.family"
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {str(detail)[:400]}")


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if ok and res.returncode:
        raise RuntimeError(f"{cmd[:4]}: {res.stderr.strip()[-400:]}")
    return res


def cleanup():
    sh(["docker", "rm", "-f", DC, KC], ok=False)
    sh(["docker", "network", "rm", NET], ok=False)


def ntlm_signs_in(user, password):
    """Whether a password signs in to AD directly (NTLM over LDAP at the DC), Keycloak not involved."""
    auth = os.path.join(W, f"{user}.auth")
    with open(auth, "w") as f:
        f.write(f"username={user}\npassword={password}\ndomain=AD\n")
    os.chmod(auth, 0o600)
    res = sh(["docker", "run", "--rm", "--network", NET, "-v", f"{auth}:/auth:ro", "--entrypoint", "ldbsearch",
              "fabric/samba:test", "-H", f"ldap://{DC_IP}", "-A", "/auth", "--use-kerberos=off", "-b",
              dc["v"]["ad_base_dn"], "-s", "base", "dn"], ok=False)
    return res.returncode == 0


class Browser:
    """Just enough of a browser for Keycloak's forms, through curl: a cookie jar, redirects not followed, the test CA
    trusted, and Keycloak reached at its address under its name (--connect-to: nothing on this machine changes)."""

    def __init__(self, ca):
        self.ca = ca
        self.jar = os.path.join(W, f"jar-{id(self)}")

    def go(self, url, form=None):
        cmd = ["curl", "-s", "-i", "-c", self.jar, "-b", self.jar, "--cacert", self.ca,
               "--connect-to", f"{HOST}:443:{KC_IP}:8443", "--connect-to", f"{HOST}:8443:{KC_IP}:8443", url]
        for key, value in (form or {}).items():
            cmd += ["--data-urlencode", f"{key}@-" if key.startswith("password") else f"{key}={value}"]
        # a password field goes on stdin, never on the command line (one per request at most)
        secret = next((val for key, val in (form or {}).items() if key.startswith("password")), None)
        if form and sum(1 for key in form if key.startswith("password")) > 1:
            cmd = cmd[:cmd.index("--data-urlencode")]
            for key, value in form.items():
                cmd += ["--data-urlencode", f"{key}@{self._file(key, value)}"]
            secret = None
        out = subprocess.run(cmd, input=secret, capture_output=True, text=True).stdout
        # text mode: curl's CRLF arrives as LF
        head, _, body = out.partition("\n\n")
        while head.startswith("HTTP/") and " 100 " in head.split("\n", 1)[0]:
            head, _, body = body.partition("\n\n")
        lines = head.split("\n")
        status = int(lines[0].split()[1]) if lines and lines[0].startswith("HTTP/") else 0
        headers = {k.strip().lower(): val.strip() for k, _, val in (ln.partition(":") for ln in lines[1:])}
        return status, headers, body

    def _file(self, key, value):
        path = os.path.join(W, f"form-{key}")
        with open(path, "w") as f:
            f.write(value)
        os.chmod(path, 0o600)
        return path


def action(page):
    m = re.search(r'action="([^"]+)"', page)
    return m.group(1).replace("&amp;", "&") if m else ""


cleanup()
shutil.rmtree(W, ignore_errors=True)
# the DC first: Keycloak's account and the first admin come from it
dc = start_dc(os.path.join(W, "dc"), DC, NET, SUBNET, DC_IP, extra_vars={
    "ip_keycloak": KC_IP, "hostname_keycloak": HOST, "webui_realm": REALM, "install_webui": True, "install_keycloak": True,
    "hostname_mgr": "mgr.lan.j-j.family", "webui_hostname": "mgr.lan.j-j.family", "webui_admin_group": "admins"})
v, secrets, root_ca = dc["v"], dc["secrets"], dc["root_ca"]
check("a real DC from fabric's image, converged (Keycloak's service account made)", True)
state, otp = ensure_admin(v, secrets, "jim", "jim@lan.j-j.family", container=DC)
check("the first admin jim is created in the directory with a one-time password", state == "created" and otp)

# Keycloak, its certificate from the test root, the root as its truststore (fabric's LDAPS to the DC is verified)
kc_dir = os.path.join(W, "kc")
os.makedirs(kc_dir)
sh(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{kc_dir}/privkey.pem", "-out", f"{kc_dir}/kc.csr",
    "-subj", f"/CN={HOST}"])
with open(f"{kc_dir}/kc.ext", "w") as f:
    f.write(f"subjectAltName=DNS:{HOST}\nextendedKeyUsage=serverAuth\n")
sh(["openssl", "x509", "-req", "-in", f"{kc_dir}/kc.csr", "-CA", root_ca, "-CAkey", dc["root_key"], "-CAcreateserial",
    "-out", f"{kc_dir}/fullchain.pem", "-days", "2", "-extfile", f"{kc_dir}/kc.ext"])
sh(["cp", root_ca, f"{kc_dir}/root_ca.crt"])
for name in os.listdir(kc_dir):
    os.chmod(os.path.join(kc_dir, name), 0o644)
image = sh([sys.executable, os.path.join(REPO, "tests", "image_ref.py"), "keycloak"]).stdout.strip()
sh(["docker", "run", "-d", "--name", KC, "--network", NET, "--ip", KC_IP,
    "-e", "KC_BOOTSTRAP_ADMIN_USERNAME=admin", "-e", "KC_BOOTSTRAP_ADMIN_PASSWORD=KcAdmin1",
    "-e", f"KC_HOSTNAME={HOST}", "-e", "KC_PROXY_HEADERS=xforwarded", "-e", "KC_HEALTH_ENABLED=true",
    "-e", "KC_HTTPS_CERTIFICATE_FILE=/certs/fullchain.pem", "-e", "KC_HTTPS_CERTIFICATE_KEY_FILE=/certs/privkey.pem",
    "-e", "KC_TRUSTSTORE_PATHS=/certs/root_ca.crt", "-v", f"{kc_dir}:/certs:ro", image, "start-dev"])
for _ in range(90):
    if sh(["curl", "-sf", "--cacert", root_ca, "--resolve", f"{HOST}:8443:{KC_IP}",
           f"https://{HOST}:8443/realms/master"], ok=False).returncode == 0:
        break
    time.sleep(3)
cfg = os.path.join(W, "opt", "fabric", "config")
os.makedirs(cfg)
os.makedirs(os.path.join(W, "opt", "stepca", "data", "certs"))
sh(["cp", root_ca, os.path.join(W, "opt", "stepca", "data", "certs", "root_ca.crt")])
with open(os.path.join(cfg, "vars.yaml"), "w") as f:
    yaml.safe_dump({**v, "deploy_base_dir": os.path.join(W, "opt")}, f)
with open(os.path.join(cfg, "fabric-secrets.yml"), "w") as f:
    yaml.safe_dump({"keycloak_admin_user": "admin", "keycloak_admin_password": "KcAdmin1",
                    "ad_keycloak_password": secrets["ad_keycloak_password"], "webui_oidc_secret": "OidcSecret1"}, f)
boot = [sys.executable, os.path.join(REPO, "src", "ux", "cli", "keycloak_bootstrap.py"),
        "--vars", os.path.join(cfg, "vars.yaml"), "--secrets", os.path.join(cfg, "fabric-secrets.yml")]
env = dict(os.environ, PYTHONPATH=f"{REPO}/src:{REPO}")
run1 = sh(boot, ok=False, env=env)
check("bootstrap run 1 succeeds", "Keycloak configuration complete" in run1.stdout, (run1.stdout + run1.stderr)[-600:])
run2 = sh(boot, ok=False, env=env)
check("bootstrap run 2 converges (no creates)", "complete" in run2.stdout and "created" not in run2.stdout,
      run2.stdout[-400:])

# the admin API's view
kc = Admin(TLSClient(KC_IP, 8443, HOST, root_ca), "admin", "KcAdmin1")
R = f"/{REALM}"
comps = kc.call("GET", f"{R}/components?type=org.keycloak.storage.UserStorageProvider")[1]
ldap = [c for c in comps if c["providerId"] == "ldap"]
check("exactly one LDAP provider: Samba AD, AD mode, LDAPS to the DC's address, verified",
      len(ldap) == 1 and ldap[0]["config"]["vendor"] == ["ad"]
      and ldap[0]["config"]["connectionUrl"] == [f"ldaps://{DC_IP}:636"]
      and ldap[0]["config"]["useTruststoreSpi"] == ["always"], ldap and ldap[0]["config"].get("connectionUrl"))
st, sync = kc.call("POST", f"{R}/user-storage/{ldap[0]['id']}/sync?action=triggerFullSync")
check("a full sync from AD over LDAPS works", st == 200 and not sync.get("failed"), sync)
users = kc.call("GET", f"{R}/users?username=jim&exact=true")[1]
check("jim (in the site's people) is visible in Keycloak", len(users) == 1, users)
if users:
    roles = kc.call("GET", f"{R}/users/{users[0]['id']}/role-mappings/realm/composite")[1]
    check("jim gets fabric-admin through AD's admins group", any(r["name"] == "fabric-admin" for r in roles),
          [r["name"] for r in roles])
client = kc.call("GET", f"{R}/clients?clientId=fabric-webui")[1][0]
check("client: confidential, code flow only, exact redirect, PKCE S256, fullScopeAllowed off",
      not client["publicClient"] and client["standardFlowEnabled"] and not client["implicitFlowEnabled"]
      and not client["directAccessGrantsEnabled"] and client["redirectUris"] == ["https://mgr.lan.j-j.family/oidc/callback"]
      and client["attributes"].get("pkce.code.challenge.method") == "S256" and client["fullScopeAllowed"] is False)
flows = {f["alias"]: f["id"] for f in kc.call("GET", f"{R}/authentication/flows")[1]}
otp_steps = [e for e in kc.call("GET", f"{R}/authentication/flows/fabric-webui-mfa/executions")[1]
             if e.get("providerId") == "auth-otp-form"]
check("the web UI's MFA flow requires TOTP", flows.get("fabric-webui-mfa") and otp_steps
      and all(e["requirement"] == "REQUIRED" for e in otp_steps))

# a real browser sign-in by the first admin, with fabric's one-time password
AUTH = (f"https://{HOST}/realms/{REALM}/protocol/openid-connect/auth?client_id=fabric-webui&response_type=code"
        "&scope=openid&redirect_uri=https%3A%2F%2Fmgr.lan.j-j.family%2Foidc%2Fcallback&state=s&nonce=n"
        "&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256")
b = Browser(root_ca)
_, _, page = b.go(AUTH)
st, hdr, page = b.go(action(page), {"username": "jim", "password": otp})
if st in (302, 303):
    st, hdr, page = b.go(hdr.get("location"))
if os.environ.get("KEYCLOAK_TEST_DEBUG"):
    print("DEBUG", st, re.findall(r"<title>([^<]*)", page), re.findall(r'name="([a-z-]+)"', page)[:12],
          re.findall(r'class="[^"]*(?:alert|error)[^"]*"[^>]*>\s*([^<]{0,200})', page)[:3])
check("jim signs in with fabric's one-time password", st == 200 and ("totp" in page or "password-new" in page),
      page[:300])
# Keycloak's required actions, in its own order: TOTP enrolment (MFA) and a new password (AD's must-change)
seen, new_pw, location = set(), "Kc-" + random_password(20), ""
for _ in range(4):
    if 'name="totp"' in page:
        fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
        key = fields.get("totpSecret", "").encode()
        counter = int(time.time()) // 30
        mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        code = (struct.unpack(">I", mac[mac[-1] & 0x0F:(mac[-1] & 0x0F) + 4])[0] & 0x7FFFFFFF) % 1000000
        st, hdr, page = b.go(action(page), {**fields, "totp": f"{code:06d}", "userLabel": "test"})
        seen.add("totp")
    elif 'name="password-new"' in page:
        st, hdr, page = b.go(action(page), {"password-new": new_pw, "password-confirm": new_pw})
        seen.add("password")
    else:
        break
    location = hdr.get("location") or ""
    if st in (302, 303) and "code=" in location:
        break
    if st in (302, 303):
        st, hdr, page = b.go(location)
check("Keycloak forces TOTP enrolment (MFA) and a new password (AD's must-change), then signs jim in",
      seen == {"totp", "password"} and "mgr.lan.j-j.family/oidc/callback" in location and "code=" in location,
      (seen, location[:120], page[:200]))
check("the new password chosen in Keycloak landed in AD", ntlm_signs_in("jim", new_pw))
check("the one-time password no longer signs in to AD", not ntlm_signs_in("jim", otp))

# refusals
def person(uid):
    """A person made by fabric's own operation (in the site's people and <site>-users); their one-time password."""
    pw = "Tst-" + random_password(20)
    run_op(v, secrets, "create_person", {"uid": uid, "first": uid, "last": "T", "email": f"{uid}@lan.j-j.family",
                                        "password": pw, "gid": 5000, "home_base": "/home", "shell": "/bin/bash"}, DC)
    return pw


bob_pw = person("bob")
sh(["docker", "exec", DC, "samba-tool", "user", "disable", "bob", "-s", "/data/etc/smb.conf"])
b2 = Browser(root_ca)
_, _, page = b2.go(AUTH)
_, _, page = b2.go(action(page), {"username": "bob", "password": bob_pw})
check("refused: a person disabled in AD", re.search(r"disabled|Invalid username or password", page, re.I), page[:300])
eve_pw = person("eve")
sh(["docker", "exec", DC, "samba-tool", "group", "removemembers", "lan-users", "eve", "-s",
    "/data/etc/smb.conf"])               # in the site's people, but in none of the admitted groups
b3 = Browser(root_ca)
_, _, page = b3.go(AUTH)
_, _, page = b3.go(action(page), {"username": "eve", "password": eve_pw})
check("refused: a person outside the site's groups (D90)", "Invalid username or password" in page, page[:300])
_, _, bad = Browser(root_ca).go(AUTH.replace("mgr.lan.j-j.family%2Foidc", "evil.test%2Foidc"))
check("refused: a redirect URI that is not registered", "Invalid parameter: redirect_uri" in bad, bad[:200])

# ---- apps signing people in through Keycloak (fabricctl sso, manual 3.8.2)
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.keycloak.add_app_client import add_app_client  # noqa: E402
from fabriclib.keycloak.list_app_clients import list_app_clients  # noqa: E402
from fabriclib.keycloak.remove_app_client import remove_app_client  # noqa: E402

SSO_V = {"hostname_keycloak": HOST}


def refused(fn, *a):
    try:
        fn(*a)
        return False
    except ValidationError:
        return True


app = add_app_client(kc, REALM, SSO_V, "proxmox", ["https://pve.lan.test:8006"])
rep = kc.call("GET", f"{R}/clients?clientId=app-proxmox")[1][0]
mappers = kc.call("GET", f"{R}/clients/{rep['id']}/protocol-mappers/models")[1]
flows = {f["id"]: f["alias"] for f in kc.call("GET", f"{R}/authentication/flows")[1]}
check("sso add: a confidential code-flow client, the exact redirect, fabric's TOTP sign-in, a groups claim",
      rep["publicClient"] is False and rep["standardFlowEnabled"] and not rep["directAccessGrantsEnabled"]
      and not rep["implicitFlowEnabled"] and rep["redirectUris"] == ["https://pve.lan.test:8006"]
      and flows.get(rep.get("authenticationFlowBindingOverrides", {}).get("browser")) == "fabric-webui-mfa"
      and any(m["protocolMapper"] == "oidc-group-membership-mapper" and m["config"]["claim.name"] == "groups"
              for m in mappers), rep)
oidc = TLSClient(KC_IP, 8443, HOST, root_ca)
token_path = f"/realms/{REALM}/protocol/openid-connect/token"
st_ok, body_ok = oidc.request("POST", token_path, form={"grant_type": "authorization_code", "code": "x",
                                                        "client_id": "app-proxmox", "client_secret": app["secret"],
                                                        "redirect_uri": "https://pve.lan.test:8006"})
st_bad, _ = oidc.request("POST", token_path, form={"grant_type": "authorization_code", "code": "x",
                                                   "client_id": "app-proxmox", "client_secret": "wrong",
                                                   "redirect_uri": "https://pve.lan.test:8006"})
check("the secret it printed is the client's (a bogus code is refused as such; a wrong secret as a bad client)",
      st_ok == 400 and "invalid_grant" in str(body_ok) and st_bad == 401, (st_ok, body_ok, st_bad))
st, disc = oidc.request("GET", f"/realms/{REALM}/.well-known/openid-configuration")
check("the discovery document it names answers with the issuer it names",
      st == 200 and disc.get("issuer") == app["issuer"] and app["discovery"].endswith("openid-configuration"),
      (st, str(disc)[:200]))
check("refused: the same name again, an http or wildcard redirect, no redirect, a bad name",
      refused(add_app_client, kc, REALM, SSO_V, "proxmox", ["https://other.test/cb"])
      and refused(add_app_client, kc, REALM, SSO_V, "nas", ["http://nas.lan.test/cb"])
      and refused(add_app_client, kc, REALM, SSO_V, "nas", ["https://*.lan.test/cb"])
      and refused(add_app_client, kc, REALM, SSO_V, "nas", [])
      and refused(add_app_client, kc, REALM, SSO_V, "Bad Name!", ["https://nas.lan.test/cb"]))
listed = list_app_clients(kc, REALM)
check("sso list: the app, its redirect, no secret and none of fabric's own clients",
      [a["name"] for a in listed] == ["proxmox"] and app["secret"] not in str(listed), listed)
remove_app_client(kc, REALM, "proxmox")
check("sso remove: the client is gone; removing it again is refused",
      kc.call("GET", f"{R}/clients?clientId=app-proxmox")[1] == []
      and refused(remove_app_client, kc, REALM, "proxmox"))

if not os.environ.get("KEYCLOAK_TEST_KEEP"):
    cleanup()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
