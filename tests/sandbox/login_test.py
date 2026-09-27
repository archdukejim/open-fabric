#!/usr/bin/env python3
"""Real end-to-end web UI login, run inside the sandbox after setup.

Uses only what setup handed the admin (~/fabric-admin: the .p12, its
password, the initial password, the root CA) and drives the real stack like
a browser: nginx mTLS -> web UI -> Keycloak login -> forced password change
-> TOTP enrolment -> OIDC callback -> dashboard. Also checks the refusals.
Prints PASS/FAIL lines.

  python3 login_test.py <vars.yaml>
"""
import base64
import hashlib
import hmac
import html
import http.client
import os
import re
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse

import yaml

V = yaml.safe_load(open(sys.argv[1]))
USER = V["webui_admin_user"]
KIT = os.path.join(os.path.expanduser("~"), "fabric-admin")
ROOT_CA = os.path.join(V["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
MGR, SSO, NGINX = V["hostname_mgr"], V["hostname_keycloak"], V["ip_nginx"]
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))
    return cond


def read(name):
    return open(os.path.join(KIT, name)).read().strip()


# -- the admin's client certificate, out of the .p12 setup handed over ----
tmp = tempfile.mkdtemp()
cert_pem = os.path.join(tmp, "client.pem")
subprocess.run(["openssl", "pkcs12", "-in", os.path.join(KIT, f"{USER}.p12"), "-nodes", "-passin", "stdin",
                "-out", cert_pem], input=read("p12-password.txt"), text=True, check=True, capture_output=True)
os.chmod(cert_pem, 0o600)


class Browser:
    """Just enough of a browser: per-host cookies, manual redirects, TLS
    verified against the fabric root CA, optional client certificate."""

    def __init__(self, client_cert=None):
        self.ctx = ssl.create_default_context(cafile=ROOT_CA)
        if client_cert:
            self.ctx.load_cert_chain(client_cert)
        self.cookies = {}

    def request(self, method, url, form=None):
        u = urllib.parse.urlsplit(url)
        conn = http.client.HTTPSConnection(NGINX, 443, context=self.ctx, timeout=30)
        conn.sock = self.ctx.wrap_socket(__import__("socket").create_connection((NGINX, 443), 30),
                                         server_hostname=u.hostname)
        jar = self.cookies.setdefault(u.hostname, {})
        headers = {"Host": u.hostname}
        if jar:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
        body = None
        if form is not None:
            body = urllib.parse.urlencode(form)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = f"https://{u.hostname}"
        conn.request(method, u.path + (f"?{u.query}" if u.query else ""), body=body, headers=headers)
        resp = conn.getresponse()
        for k, v in resp.getheaders():
            if k.lower() == "set-cookie":
                name, _, rest = v.partition("=")
                value = rest.split(";", 1)[0]
                if value and "Max-Age=0" not in v:
                    jar[name] = value
                else:
                    jar.pop(name, None)
        data = resp.read().decode(errors="replace")
        loc = resp.getheader("Location")
        conn.close()
        return resp.status, (urllib.parse.urljoin(url, loc) if loc else None), data


def form_of(page):
    """(action, {field: value}) of the first form on a Keycloak page."""
    m = re.search(r'<form[^>]*action="([^"]+)"', page)
    fields = {}
    for tag in re.findall(r"<input[^>]*>", page):
        n = re.search(r'name="([^"]+)"', tag)
        if n:
            val = re.search(r'value="([^"]*)"', tag)
            fields[n.group(1)] = html.unescape(val.group(1)) if val else ""
    return (html.unescape(m.group(1)) if m else None), fields


def totp(secret, at=None):
    """Keycloak's default policy: HmacSHA1, 6 digits, 30 s, key = raw secret bytes."""
    counter = int((at or time.time()) // 30)
    mac = hmac.new(secret.encode(), struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    return f"{(struct.unpack('>I', mac[off:off + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


# -- refusals -------------------------------------------------------------
st, _, _ = Browser().request("GET", f"https://{MGR}/")
check("no client certificate -> refused by nginx (400)", st == 400, st)

# -- full login as the admin ------------------------------------------------
b = Browser(cert_pem)
st, loc, _ = b.request("GET", f"https://{MGR}/")
check("client cert, no session -> /login", st == 303 and loc.endswith("/login"), (st, loc))
st, loc, _ = b.request("GET", loc)
check("/login -> Keycloak authorization endpoint", st == 303 and loc.startswith(f"https://{SSO}/"), (st, loc))

new_password = base64.urlsafe_b64encode(os.urandom(18)).decode()
totp_secret = None
st, loc, page = b.request("GET", loc)
seen = []
for _ in range(12):                      # follow Keycloak's pages until it sends us back
    while st in (301, 302, 303) and loc and not loc.startswith(f"https://{MGR}/"):
        st, loc, page = b.request("GET", loc)
    if loc and loc.startswith(f"https://{MGR}/oidc/callback"):
        break
    action, fields = form_of(page)
    if not action:
        check("Keycloak page has a form", False, page[:600])
        break
    if "username" in fields and "password" in fields:
        seen.append("login")
        fields.update(username=USER, password=read("initial-password.txt"))
    elif "password-new" in fields:
        seen.append("update-password")
        fields.update({"password-new": new_password, "password-confirm": new_password})
    elif "totpSecret" in fields:
        seen.append("configure-totp")
        totp_secret = fields["totpSecret"]
        fields.update(totp=totp(totp_secret), userLabel="fabric sandbox")
    elif "otp" in fields and totp_secret:
        seen.append("otp")
        fields.update(otp=totp(totp_secret))
    elif {"firstName", "lastName", "email"} & set(fields):
        seen.append("update-profile")
    else:
        check("known Keycloak page", False, sorted(fields))
        break
    st, loc, page = b.request("POST", action, {k: v for k, v in fields.items() if k != "cancel-aia"})

check("Keycloak asked for login, a new password and TOTP enrolment",
      seen[:1] == ["login"] and "update-password" in seen and "configure-totp" in seen, seen)
check("Keycloak redirects back to the web UI callback",
      bool(loc) and loc.startswith(f"https://{MGR}/oidc/callback"), (st, loc, page[:300]))
st, _, page = b.request("GET", loc)
check("callback accepted (cert CN = user, fabric-admin role)",
      st == 200 and "__Host-webui" in b.cookies.get(MGR, {}), (st, page[:300]))
st, _, page = b.request("GET", f"https://{MGR}/")
check("dashboard renders for the admin", st == 200 and "DNS zones" in page and USER in page, (st, page[:300]))

# -- the initial password is dead, the new one works -------------------------
fresh = Browser(cert_pem)
st, loc, _ = fresh.request("GET", f"https://{MGR}/login")
st, loc, page = fresh.request("GET", loc)
action, fields = form_of(page)
fields.update(username=USER, password=read("initial-password.txt"))
st, loc, page = fresh.request("POST", action, fields)
check("initial password no longer accepted", st == 200 and "Invalid" in page, (st, loc))

sys.exit(1 if FAILED else 0)
