#!/usr/bin/env python3
"""End-to-end test of core-web against a mock Keycloak. Run in WSL/Linux:
    sudo python3 tests/webui/test_container.py
Builds a throwaway PKI with openssl, starts a TLS mock Keycloak that signs
real RS256 ID tokens, starts core-web on a unix socket and drives it the way
nginx would (forwarded client-certificate headers)."""
import base64
import hashlib
import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests") + "/webui"
shutil.rmtree(W, ignore_errors=True)
os.makedirs(W)


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, cwd=W, **kw).stdout


# ---------------------------------------------------------------- PKI
sh("openssl req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 2 -subj '/O=Test/CN=Test Root CA' "
   "-addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign")


def ca_cert(name, cn, issuer):
    sh(f"openssl req -newkey rsa:2048 -nodes -keyout {name}.key -out {name}.csr -subj '/C=US/O=Test Org/CN={cn}'")
    open(f"{W}/{name}.ext", "w").write("basicConstraints=critical,CA:TRUE,pathlen:1\nkeyUsage=critical,keyCertSign,cRLSign\n")
    sh(f"openssl x509 -req -in {name}.csr -CA {issuer}.crt -CAkey {issuer}.key -CAcreateserial -out {name}.crt -days 2 -extfile {name}.ext")


def leaf(name, cn, issuer, san=None):
    sh(f"openssl req -newkey rsa:2048 -nodes -keyout {name}.key -out {name}.csr -subj '/C=US/O=Test Org/OU=IT/CN={cn}'")
    ext = "basicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth,clientAuth\n" + (f"subjectAltName=DNS:{san}\n" if san else "")
    open(f"{W}/{name}.ext", "w").write(ext)
    sh(f"openssl x509 -req -in {name}.csr -CA {issuer}.crt -CAkey {issuer}.key -CAcreateserial -out {name}.crt -days 2 -extfile {name}.ext")


ca_cert("int", "Test Intermediate CA", "root")
ca_cert("sub", "Rogue Sub CA", "int")
leaf("sso", "sso.test", "int", san="sso.test")
open(f"{W}/sso-chain.crt", "w").write(open(f"{W}/sso.crt").read() + open(f"{W}/int.crt").read())


def dn(path, which):
    return sh(f"openssl x509 -in {path} -noout -{which} -nameopt RFC2253").split("=", 1)[1].strip()


INT_DN = dn(f"{W}/int.crt", "subject")
SUB_DN = dn(f"{W}/sub.crt", "subject")

# ------------------------------------------------------- mock Keycloak
sh("openssl genrsa -out sign.key 2048")
modulus = int(sh("openssl rsa -in sign.key -noout -modulus").split("=")[1].strip(), 16)


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


JWKS = {"keys": [{"kid": "k1", "kty": "RSA", "alg": "RS256", "use": "sig",
                  "n": b64u(modulus.to_bytes(256, "big")), "e": b64u((65537).to_bytes(3, "big"))}]}
ISSUER = "https://sso.test/realms/test"
CODES = {}          # code -> dict(nonce, challenge, user, roles, tamper)
MOCK = {"user": "alice", "roles": ["fabric-admin"], "tamper": None}


def sign_jwt(claims, kid="k1"):
    header = b64u(json.dumps({"alg": "RS256", "kid": kid, "typ": "JWT"}).encode())
    payload = b64u(json.dumps(claims).encode())
    open(f"{W}/tosign", "wb").write(f"{header}.{payload}".encode())
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", f"{W}/sign.key", f"{W}/tosign"],
                         capture_output=True, check=True).stdout
    return f"{header}.{payload}.{b64u(sig)}"


class KC(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/realms/test/protocol/openid-connect/certs":
            return self.reply(200, JWKS)
        self.reply(404, {})

    def do_POST(self):
        form = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers["Content-Length"])).decode()))
        if self.path != "/realms/test/protocol/openid-connect/token":
            return self.reply(404, {})
        entry = CODES.pop(form.get("code"), None)
        if not entry or form.get("client_secret") != "s3cret" or form.get("client_id") != "fabric-webui":
            return self.reply(400, {"error": "invalid_grant"})
        if b64u(hashlib.sha256(form["code_verifier"].encode()).digest()) != entry["challenge"]:
            return self.reply(400, {"error": "invalid_grant", "error_description": "PKCE"})
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": "fabric-webui", "azp": "fabric-webui", "sub": "u1", "iat": now, "exp": now + 300,
                  "nonce": entry["nonce"], "preferred_username": entry["user"], "roles": entry["roles"]}
        t = entry["tamper"]
        if t == "nonce":
            claims["nonce"] = "wrong"
        if t == "aud":
            claims["aud"] = "other-client"
        if t == "expired":
            claims["exp"] = now - 600
        token = sign_jwt(claims)
        if t == "sig":
            h, p, s = token.split(".")
            p = b64u(json.dumps({**claims, "roles": ["fabric-admin", "x"]}).encode())
            token = f"{h}.{p}.{s}"
        self.reply(200, {"id_token": token, "access_token": "unused", "token_type": "Bearer"})


kc = ThreadingHTTPServer(("0.0.0.0", 18443), KC)
ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ctx.load_cert_chain(f"{W}/sso-chain.crt", f"{W}/sso.key")
kc.socket = ctx.wrap_socket(kc.socket, server_side=True)
threading.Thread(target=kc.serve_forever, daemon=True).start()

# ------------------------------------------- fabric-agent (host, root)
shutil.copytree(os.path.join(REPO, "fabric", "lib"), f"{W}/fabric/lib")
os.makedirs(f"{W}/fabric/config")
open(f"{W}/fabric/VERSION", "w").write("9.9.9\n")
open(f"{W}/fabric/config/vars.yaml", "w").write(
    "domain: lan.test\ndns:\n  dynamic_zone_var:\n    zone_authority: true\n    A:\n    - {name: pi-core, ip: 192.168.7.53}\n"
    "    CNAME:\n    - {name: calibre, canonical: nas25-apps}\n")
UID = 912
for d, owner, group, mode in [("agent", 0, UID, 0o750), ("run", UID, 0, 0o750), ("config", 0, UID, 0o750),
                              ("certs", 0, 0, 0o755)]:
    os.makedirs(f"{W}/{d}", exist_ok=True)
    os.chown(f"{W}/{d}", owner, group)
    os.chmod(f"{W}/{d}", mode)
shutil.copy(f"{W}/root.crt", f"{W}/certs/root_ca.crt")
shutil.copy(f"{W}/int.crt", f"{W}/certs/intermediate_ca.crt")
agent = subprocess.Popen([sys.executable, f"{W}/fabric/lib/agent/server.py", "--socket", f"{W}/agent/agent.sock",
                          "--socket-gid", str(UID), "--allow-uid", str(UID)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# ------------------------------------------- webui container (uid 912)
sh("docker rm -f cwebui >/dev/null 2>&1; docker network rm cwnet >/dev/null 2>&1; true")
sh("docker network create --subnet 10.254.8.0/24 --gateway 10.254.8.1 cwnet >/dev/null")
cfg = {"socket": "/run/webui/web.sock", "socket_gid": 0, "agent_socket": "/agent/agent.sock",
       "public_url": "https://mgr.test", "ca_file": "/certs/root_ca.crt", "intermediate_ca": "/certs/intermediate_ca.crt",
       "admin_role": "fabric-admin", "session_idle": 900, "session_max": 28800,
       "keycloak": {"ip": "10.254.8.1", "port": 18443, "hostname": "sso.test", "realm": "test",
                    "client_id": "fabric-webui", "client_secret": "s3cret"}}
json.dump(cfg, open(f"{W}/config/webui.json", "w"))
os.chown(f"{W}/config/webui.json", UID, UID)
os.chmod(f"{W}/config/webui.json", 0o400)
os.makedirs(f"{W}/build")
sh(f"cp -a {REPO}/fabric/jinja/webui/build/. {W}/build/ && cp -a {REPO}/fabric/lib/webui {W}/build/app")
sh(f"docker build -q --build-arg WEBUI_UID={UID} --build-arg WEBUI_GID={UID} -t fabric/webui:test {W}/build >/dev/null")
sh(f"docker run -d --name cwebui --network cwnet --ip 10.254.8.80 --user {UID}:{UID} --group-add 0 "
   f"--read-only --security-opt no-new-privileges:true --cap-drop ALL --tmpfs /tmp:noexec,nosuid,size=16m "
   f"-v {W}/config:/config:ro -v {W}/certs:/certs:ro -v {W}/run:/run/webui -v {W}/agent:/agent:ro "
   f"fabric/webui:test >/dev/null")
for _ in range(100):
    if os.path.exists(f"{W}/run/web.sock"):
        break
    time.sleep(0.2)
os.symlink(f"{W}/run/web.sock", f"{W}/web.sock")


class UConn(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(f"{W}/web.sock")


ALICE = {"X-SSL-Client-Verify": "SUCCESS", "X-SSL-Client-S-DN": "CN=alice,OU=IT,O=Test Org,C=US",
         "X-SSL-Client-I-DN": INT_DN, "X-SSL-Client-Fingerprint": "aa" * 20}


def req(method, path, headers=None, body=None, cookie=None):
    h = dict(headers or {})
    if cookie:
        h["Cookie"] = cookie
    if body is not None:
        body = urllib.parse.urlencode(body)
        h["Content-Type"] = "application/x-www-form-urlencoded"
    c = UConn("x")
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    data = r.read().decode()
    return r.status, dict(r.getheaders()), r.getheader("Set-Cookie") or "", data


def cookie_val(set_cookie, name):
    for part in set_cookie.split(", "):
        if part.startswith(name + "="):
            return part.split(";")[0]
    return ""


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


def login(cert=ALICE, user="alice", roles=("fabric-admin",), tamper=None, callback_cert=None):
    st, hd, sc, _ = req("GET", "/login", cert)
    loc = urllib.parse.urlparse(hd.get("Location", ""))
    q = dict(urllib.parse.parse_qsl(loc.query))
    code = os.urandom(8).hex()
    CODES[code] = {"nonce": q.get("nonce"), "challenge": q.get("code_challenge"), "user": user,
                   "roles": list(roles), "tamper": tamper}
    lc = cookie_val(sc, "__Host-webui-login")
    return req("GET", f"/oidc/callback?code={code}&state={q.get('state')}", callback_cert or cert, cookie=lc), q, hd


# ---------------------------------------------------------------- tests
st, *_ = req("GET", "/")
check("no client cert -> 403", st == 403, st)
st, *_ = req("GET", "/", {**ALICE, "X-SSL-Client-Verify": "FAILED:unable to verify"})
check("unverified cert -> 403", st == 403, st)
st, *_ = req("GET", "/", {**ALICE, "X-SSL-Client-I-DN": SUB_DN})
check("cert from subordinate CA -> 403", st == 403, st)
st, hd, *_ = req("GET", "/", ALICE)
check("valid cert, no session -> redirect to /login", st == 303 and hd.get("Location") == "/login", (st, hd))

st, hd, sc, _ = req("GET", "/login", ALICE)
q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(hd["Location"]).query))
check("login redirects to Keycloak auth endpoint",
      hd["Location"].startswith(ISSUER + "/protocol/openid-connect/auth?"), hd["Location"])
check("login uses PKCE S256 + state + nonce + exact redirect_uri",
      q.get("code_challenge_method") == "S256" and q.get("state") and q.get("nonce")
      and q.get("redirect_uri") == "https://mgr.test/oidc/callback", q)
check("login cookie is __Host-, Secure, HttpOnly", "__Host-webui-login=" in sc and "Secure" in sc and "HttpOnly" in sc, sc)

(st, hd, sc, body), _, _ = login(user="bob")
check("Keycloak user != cert CN -> 403", st == 403, st)
(st, *_), _, _ = login(roles=())
check("user without fabric-admin role -> 403", st == 403, st)
for t in ("nonce", "aud", "expired", "sig"):
    (st, *_), _, _ = login(tamper=t)
    check(f"ID token with bad {t} -> 401", st == 401, st)
BOB_CERT = {**ALICE, "X-SSL-Client-Fingerprint": "bb" * 20}
(st, *_), _, _ = login(callback_cert=BOB_CERT)
check("callback presented with a different cert -> 400", st == 400, st)
st, *_ = req("GET", "/oidc/callback?code=x&state=forged", ALICE)
check("forged state -> 400", st == 400, st)

(st, hd, sc, body), _, _ = login()
session = cookie_val(sc, "__Host-webui")
check("valid login -> session cookie (Strict)", st == 200 and session and "SameSite=Strict" in sc, (st, sc))
check("security headers present", "default-src 'none'" in hd.get("Content-Security-Policy", "")
      and hd.get("X-Frame-Options") == "DENY" and hd.get("Cache-Control") == "no-store", hd)

st, hd, sc, body = req("GET", "/", ALICE, cookie=session)
check("dashboard renders", st == 200 and "DNS zones" in body and "lan.test" in body, st)
check("footer shows real version", "fabricctl 9.9.9" in body, body[-300:])
st, hd, sc, body = req("GET", "/zone/dynamic_zone_var", ALICE, cookie=session)
check("zone page shows CNAME targets", st == 200 and "nas25-apps" in body and "192.168.7.53" in body, body[:500])
csrf = body.split('name="csrf" value="')[1].split('"')[0]

st, hd, sc, body = req("GET", "/", BOB_CERT, cookie=session)
check("session cookie replayed with another cert -> redirect to login", st == 303, st)
st, hd, sc, body = req("GET", "/", ALICE, cookie=session)
check("...and that session is now destroyed", st == 303, st)

(st, hd, sc, body), _, _ = login()
session = cookie_val(sc, "__Host-webui")
st, hd, sc, body = req("GET", "/zone/dynamic_zone_var", ALICE, cookie=session)
csrf = body.split('name="csrf" value="')[1].split('"')[0]
POSTH = {**ALICE, "Origin": "https://mgr.test"}
add = {"csrf": csrf, "type": "CNAME", "name": "shelfmark", "target": "nas25-apps"}
st, *_ = req("POST", "/zone/dynamic_zone_var/add", ALICE, dict(add), cookie=session)
check("POST without Origin -> 403", st == 403, st)
st, *_ = req("POST", "/zone/dynamic_zone_var/add", POSTH, {**add, "csrf": "nope"}, cookie=session)
check("POST with bad CSRF -> 403", st == 403, st)
st, *_ = req("POST", "/zone/dynamic_zone_var/add", {**POSTH, "Origin": "https://evil.test"}, dict(add), cookie=session)
check("POST from foreign origin -> 403", st == 403, st)
st, hd, *_ = req("POST", "/zone/dynamic_zone_var/add", POSTH, dict(add), cookie=session)
vars_text = open(f"{W}/fabric/config/vars.yaml").read()
check("add CNAME -> saved to vars.yaml", st == 303 and "shelfmark" in vars_text and "msg=" in hd["Location"], (st, hd))
st, hd, *_ = req("POST", "/zone/dynamic_zone_var/add", POSTH,
                 {"csrf": csrf, "type": "A", "name": "bad name;rm", "ip": "1.2.3.4"}, cookie=session)
check("invalid record name rejected", st == 303 and "err=" in hd["Location"], hd)
st, hd, *_ = req("POST", "/zone/dynamic_zone_var/add", POSTH,
                 {"csrf": csrf, "type": "TXT", "name": "x", "text": 'a"\n$INCLUDE /etc/shadow'}, cookie=session)
check("zone-file injection via TXT rejected", st == 303 and "err=" in hd["Location"], hd)
st, hd, sc, body = req("GET", "/zone/dynamic_zone_var", ALICE, cookie=session)
idx = [l for l in body.split("<tr>") if "shelfmark" in l][0].split('name="index" value="')[1].split('"')[0]
st, hd, *_ = req("POST", "/zone/dynamic_zone_var/delete", POSTH,
                 {"csrf": csrf, "type": "CNAME", "index": idx, "name": "wrong-name"}, cookie=session)
check("stale delete (name mismatch) refused", "err=" in hd.get("Location", ""), hd)
st, hd, *_ = req("POST", "/zone/dynamic_zone_var/delete", POSTH,
                 {"csrf": csrf, "type": "CNAME", "index": idx, "name": "shelfmark"}, cookie=session)
check("delete CNAME -> removed from vars.yaml", "shelfmark" not in open(f"{W}/fabric/config/vars.yaml").read(), hd)
st, hd, sc, body = req("GET", "/audit", ALICE, cookie=session)
check("audit log records web actions with user", "User: alice (web) | Action: DNS_ADD" in body
      and "LOGIN_DENIED" in body, body[:400])
st, hd, sc, body = req("POST", "/logout", POSTH, {"csrf": csrf}, cookie=session)
check("logout -> Keycloak end-session with id_token_hint",
      st == 303 and "/protocol/openid-connect/logout?id_token_hint=" in hd.get("Location", ""), hd)
st, *_ = req("GET", "/", ALICE, cookie=session)
check("session invalid after logout", st == 303, st)

print("--- isolation")
def dexec(cmd):
    return subprocess.run(["docker", "exec", "cwebui", "sh", "-c", cmd], capture_output=True, text=True)
check("container runs as uid 912", dexec("id -u").stdout.strip() == "912", dexec("id -u").stdout)
check("container has no capabilities", "CapEff:\t0000000000000000" in dexec("cat /proc/1/status").stdout)
check("container root filesystem is read-only", dexec("touch /app/x").returncode != 0)
check("container cannot write the agent mount", dexec("touch /agent/x").returncode != 0)
check("no Docker socket in the container", dexec("test -e /var/run/docker.sock").returncode != 0)
check("container cannot read host fabric config", dexec("test -e /fabric").returncode != 0)
probe = ("import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); "
         "s.sendall(b'GET /v1/zones HTTP/1.0\\r\\n\\r\\n'); print(s.recv(200).split(b'\\r\\n')[0].decode())")
r = subprocess.run(["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", sys.executable, "-c", probe,
                    f"{W}/agent/agent.sock"], capture_output=True, text=True)
check("other users cannot reach the agent socket", "Permission denied" in r.stderr, r.stdout + r.stderr[-200:])
r = subprocess.run(["setpriv", "--reuid=913", f"--regid={UID}", "--clear-groups", sys.executable, "-c", probe,
                    f"{W}/agent/agent.sock"], capture_output=True, text=True)
check("agent rejects a wrong uid even with the right group (SO_PEERCRED)", "403" in r.stdout, r.stdout + r.stderr[-200:])
r = subprocess.run(["docker", "exec", "cwebui", "python3", "-c", probe.replace("/v1/zones", "/v1/nope"),
                    "/agent/agent.sock"], capture_output=True, text=True)
check("agent only serves its fixed API", "404" in r.stdout, r.stdout + r.stderr[-200:])
subprocess.run("docker rm -f cwebui >/dev/null; docker network rm cwnet >/dev/null; docker rmi fabric/webui:test >/dev/null",
               shell=True)
agent.terminate()
srv = agent
srv.terminate()
kc.shutdown()
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
if failed:
    print(srv.stdout.read()[-3000:]); print(subprocess.run(['docker','logs','cwebui'],capture_output=True,text=True).stdout[-2000:])
sys.exit(1 if failed else 0)
