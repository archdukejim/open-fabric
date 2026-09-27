#!/usr/bin/env python3
"""core-web: browser front end for core-mgr.

Security model (every request must pass all of these):
  1. nginx requires a client certificate issued by the core Step-CA
     intermediate (ssl_verify_client on, depth 2) and forwards the verified
     subject/issuer/fingerprint. This server listens only on a unix socket
     that nobody but nginx can reach, so those headers cannot be forged.
  2. The issuer must be the Step-CA intermediate itself (sub-CAs rejected).
  3. The user logs in through Keycloak (OIDC code flow + PKCE). The
     Keycloak username must equal the client certificate CN and the user
     must hold the admin realm role.
  4. The session is bound to the certificate fingerprint; presenting the
     cookie with any other certificate ends the session.
  5. State-changing requests are POST-only with a per-session CSRF token
     and a same-origin Origin header.
"""
import argparse
import grp
import hmac
import json
import os
import secrets
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coreweb import actions  # noqa: E402
from coreweb.oidc import KeycloakOIDC, OIDCError  # noqa: E402
from coreweb.tlsclient import TLSClient  # noqa: E402
from coreweb import views  # noqa: E402

SESSION_COOKIE = "__Host-coreweb"
LOGIN_COOKIE = "__Host-coreweb-login"
MAX_BODY = 64 * 1024
LOGIN_TTL = 600


def parse_dn(dn):
    """Parse an RFC 2253 DN (as nginx's $ssl_client_s_dn gives it) into a
    list of (attr, value), honouring backslash escapes."""
    parts, cur, esc = [], "", False
    for ch in dn:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ",":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    out = []
    for p in parts:
        k, _, v = p.partition("=")
        out.append((k.strip().upper(), v.strip()))
    return out


def cert_subject_rfc2253(path):
    res = subprocess.run(["openssl", "x509", "-in", path, "-noout", "-subject", "-nameopt", "RFC2253"],
                         capture_output=True, text=True, check=True)
    return res.stdout.strip().removeprefix("subject=").strip()


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        kc = cfg["keycloak"]
        self.public_url = cfg["public_url"].rstrip("/")
        self.oidc = KeycloakOIDC(
            TLSClient(kc["ip"], kc.get("port", 8443), kc["hostname"], cfg["ca_file"]),
            public_base=f"https://{kc['hostname']}", realm=kc["realm"],
            client_id=kc["client_id"], client_secret=kc["client_secret"],
            redirect_uri=f"{self.public_url}/oidc/callback")
        self.sso_origin = f"https://{kc['hostname']}"
        self.admin_role = cfg["admin_role"]
        self.issuer_dn = parse_dn(cert_subject_rfc2253(cfg["intermediate_ca"]))
        self.idle = int(cfg.get("session_idle", 900))
        self.max_age = int(cfg.get("session_max", 28800))
        self.sessions = {}
        self.pending = {}
        self.lock = threading.Lock()

    def sweep(self):
        now = time.time()
        with self.lock:
            for sid, s in list(self.sessions.items()):
                if now - s["last"] > self.idle or now - s["created"] > self.max_age:
                    del self.sessions[sid]
            for k, p in list(self.pending.items()):
                if now - p["created"] > LOGIN_TTL:
                    del self.pending[k]


class Handler(BaseHTTPRequestHandler):
    server_version = "core-web"
    sys_version = ""
    app: App = None

    # -- plumbing ------------------------------------------------------
    def address_string(self):
        return self.headers.get("X-Real-IP", "nginx")

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

    def send(self, status, body=b"", content_type="text/html; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; img-src 'self'; "
                         f"form-action 'self' {self.app.sso_origin}; frame-ancestors 'none'; base-uri 'none'")
        for k, v in (headers or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def redirect(self, location, headers=None):
        self.send(303, b"", headers=[("Location", location)] + list(headers or []))

    def deny(self, status, message):
        self.send(status, views.error_page(status, message))

    def cookie(self, name):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None
        return jar[name].value if name in jar else None

    @staticmethod
    def set_cookie(name, value, max_age, samesite="Strict"):
        return ("Set-Cookie", f"{name}={value}; Path=/; Secure; HttpOnly; SameSite={samesite}; Max-Age={max_age}")

    def read_form(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("request too large")
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

    # -- gate 1+2: client certificate ------------------------------------
    def client_cert(self):
        if self.headers.get("X-SSL-Client-Verify") != "SUCCESS":
            return None
        issuer = parse_dn(self.headers.get("X-SSL-Client-I-DN", ""))
        if sorted(issuer) != sorted(self.app.issuer_dn):
            return None
        subject = parse_dn(self.headers.get("X-SSL-Client-S-DN", ""))
        cns = [v for k, v in subject if k == "CN"]
        fp = self.headers.get("X-SSL-Client-Fingerprint", "")
        if len(cns) != 1 or not cns[0] or not fp:
            return None
        return {"cn": cns[0], "fp": fp}

    # -- gate 3+4: session ------------------------------------------------
    def session(self, cert):
        sid = self.cookie(SESSION_COOKIE)
        if not sid:
            return None
        now = time.time()
        with self.app.lock:
            s = self.app.sessions.get(sid)
            if not s:
                return None
            if (now - s["last"] > self.app.idle or now - s["created"] > self.app.max_age
                    or not hmac.compare_digest(s["fp"], cert["fp"]) or s["user"] != cert["cn"]):
                del self.app.sessions[sid]
                return None
            s["last"] = now
            return dict(s, sid=sid)

    # -- dispatch -----------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        try:
            self.app.sweep()
            cert = self.client_cert()
            if not cert:
                return self.deny(403, "A client certificate issued by this core's certificate authority is required.")
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}

            if path == "/static/app.css" and method == "GET":
                return self.send(200, views.css(), "text/css; charset=utf-8")
            if path == "/login" and method == "GET":
                return self.login(cert)
            if path == "/oidc/callback" and method == "GET":
                return self.callback(cert, query)

            sess = self.session(cert)
            if not sess:
                return self.redirect("/login")

            if method == "POST":
                origin = self.headers.get("Origin", "")
                form = self.read_form()
                if origin != self.app.public_url or not hmac.compare_digest(form.get("csrf", ""), sess["csrf"]):
                    return self.deny(403, "Request rejected (CSRF check failed). Reload the page and try again.")
                return self.post(sess, path, form)
            return self.get(sess, path, query)
        except actions.ValidationError as exc:
            self.deny(400, str(exc))
        except Exception:
            traceback.print_exc()
            self.deny(500, "Internal error. See `journalctl -u coreweb`.")

    # -- auth ---------------------------------------------------------------
    def login(self, cert):
        url, state, nonce, verifier = self.app.oidc.start_login()
        with self.app.lock:
            self.app.pending[state] = {"nonce": nonce, "verifier": verifier, "fp": cert["fp"], "created": time.time()}
        # Lax: the cookie must accompany the top-level redirect back from Keycloak.
        self.redirect(url, [self.set_cookie(LOGIN_COOKIE, state, LOGIN_TTL, "Lax")])

    def callback(self, cert, query):
        state = query.get("state", "")
        with self.app.lock:
            pending = self.app.pending.pop(state, None)
        if (not pending or not hmac.compare_digest(self.cookie(LOGIN_COOKIE) or "", state)
                or pending["fp"] != cert["fp"]):
            return self.deny(400, "Login expired or was started in another browser. Sign in again.")
        if "error" in query or "code" not in query:
            return self.deny(401, "Login was cancelled or refused by the identity provider.")
        try:
            claims, id_token = self.app.oidc.finish_login(query["code"], pending["verifier"], pending["nonce"])
        except OIDCError as exc:
            return self.deny(401, f"Login failed: {exc}")

        user = claims.get("preferred_username", "")
        if user != cert["cn"]:
            actions.audit(user or "?", "LOGIN_DENIED", f"cert CN {cert['cn']!r} does not match user")
            return self.deny(403, "Your client certificate does not belong to this user.")
        if self.app.admin_role not in (claims.get("roles") or []):
            actions.audit(user, "LOGIN_DENIED", f"missing role {self.app.admin_role}")
            return self.deny(403, f"Your account is missing the '{self.app.admin_role}' role.")

        sid = secrets.token_urlsafe(32)
        now = time.time()
        with self.app.lock:
            self.app.sessions[sid] = {"user": user, "fp": cert["fp"], "csrf": secrets.token_urlsafe(32),
                                      "id_token": id_token, "created": now, "last": now}
        actions.audit(user, "LOGIN", f"cert={cert['fp'][:16]}")
        # A 200 + meta refresh (rather than a redirect) so the first request
        # carrying the Strict session cookie is initiated from this origin.
        self.send(200, views.continue_page("/"), headers=[
            self.set_cookie(SESSION_COOKIE, sid, self.app.max_age),
            self.set_cookie(LOGIN_COOKIE, "", 0, "Lax")])

    # -- pages --------------------------------------------------------------
    def get(self, sess, path, query):
        ctx = {"user": sess["user"], "csrf": sess["csrf"], "version": actions.version_info()}
        if path == "/":
            return self.send(200, views.dashboard(ctx, actions.service_status(), actions.list_zones()))
        if path.startswith("/zone/"):
            key = urllib.parse.unquote(path[len("/zone/"):])
            return self.send(200, views.zone(ctx, actions.zone_detail(key), actions.RECORD_TYPES,
                                             query.get("msg", ""), query.get("err", "")))
        if path == "/audit":
            return self.send(200, views.audit(ctx, actions.read_audit()))
        return self.deny(404, "Not found.")

    def post(self, sess, path, form):
        user = sess["user"]
        if path == "/logout":
            with self.app.lock:
                self.app.sessions.pop(sess["sid"], None)
            actions.audit(user, "LOGOUT", "")
            return self.redirect(self.app.oidc.logout_url(sess["id_token"], self.app.public_url + "/"),
                                 [self.set_cookie(SESSION_COOKIE, "", 0)])
        if path.startswith("/zone/"):
            rest = urllib.parse.unquote(path[len("/zone/"):])
            key, _, op = rest.rpartition("/")
            back = "/zone/" + urllib.parse.quote(key)
            try:
                if op == "add":
                    rtype = form.get("type", "")
                    if rtype not in actions.RECORD_TYPES:
                        raise actions.ValidationError("unsupported record type")
                    rec = actions.add_record(user, key, rtype, form)
                    msg = f"Added {rtype} {rec['name']}. Apply to publish."
                elif op == "delete":
                    actions.delete_record(user, key, form.get("type", ""), int(form.get("index", -1)),
                                          form.get("name", ""))
                    msg = "Record deleted. Apply to publish."
                else:
                    return self.deny(404, "Not found.")
                return self.redirect(back + "?" + urllib.parse.urlencode({"msg": msg}))
            except actions.ValidationError as exc:
                return self.redirect(back + "?" + urllib.parse.urlencode({"err": str(exc)}))
        if path == "/apply":
            ok, output = actions.apply_changes(user)
            ctx = {"user": user, "csrf": sess["csrf"], "version": actions.version_info()}
            return self.send(200, views.apply_result(ctx, ok, output))
        return self.deny(404, "Not found.")


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config) as f:
        cfg = json.load(f)

    Handler.app = App(cfg)
    sock = cfg["socket"]
    if os.path.exists(sock):
        os.unlink(sock)
    old_umask = os.umask(0o117)
    try:
        server = UnixServer(sock, Handler)
    finally:
        os.umask(old_umask)
    gid = cfg["socket_gid"]
    os.chown(sock, 0, gid if isinstance(gid, int) else grp.getgrnam(gid).gr_gid)
    os.chmod(sock, 0o660)
    print(f"core-web listening on {sock}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
