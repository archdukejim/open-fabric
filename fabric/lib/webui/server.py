#!/usr/bin/env python3
"""webui: browser front end for fabricctl.

Runs unprivileged in its own container (read-only, no capabilities, no
Docker socket). It holds no power of its own: every read and change goes
through fabric-agent on the host (agentclient.py), which exposes a fixed,
validated set of operations and audits each one.

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
import base64
import email.parser
import email.policy
import grp
import re
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
from webui import agentclient as actions  # noqa: E402  (fabric-agent API)
from webui.oidc import KeycloakOIDC, OIDCError  # noqa: E402
from webui.tlsclient import TLSClient  # noqa: E402
from webui import views  # noqa: E402

SESSION_COOKIE = "__Host-webui"
LOGIN_COOKIE = "__Host-webui-login"
MAX_BODY = 64 * 1024
LOGIN_TTL = 600
STEP_UP = 300            # vault changes need a sign-in no older than this (seconds)


PERM_PREFIX = "fabric:"          # fabric's permission roles (fabriclib/rbac/permissions.py)
REFRESH_BEFORE = 60              # renew the ID token this many seconds before it expires


def token_perms(claims):
    """fabric permissions in a verified ID token's roles claim."""
    return sorted({r[len(PERM_PREFIX):] for r in claims.get("roles") or []
                   if isinstance(r, str) and r.startswith(PERM_PREFIX)})


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
    server_version = "fabric-web"
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
        """Form fields as {name: str}; file uploads (multipart) as {name: bytes}."""
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("request too large")
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data"):
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                f"Content-Type: {ctype}\r\n\r\n".encode() + body)
            form = {}
            for part in msg.iter_parts() if msg.is_multipart() else []:
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                data = part.get_payload(decode=True) or b""
                form[name] = data if part.get_filename() is not None else data.decode("utf-8", "replace")
            return form
        raw = body.decode("utf-8", "replace")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

    @staticmethod
    def upload(form, file_field, text_field):
        """A pasted value, or an uploaded file (binary DER goes to the agent as base64)."""
        data = form.get(file_field)
        if isinstance(data, bytes) and data:
            try:
                return data.decode("ascii")
            except UnicodeDecodeError:
                return base64.b64encode(data).decode()
        text = form.get(text_field, "")
        return text if isinstance(text, str) else ""

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
            sess = dict(s, sid=sid)
        if sess["exp"] - now < REFRESH_BEFORE and not self.renew(sess):
            return None
        return sess

    def renew(self, sess):
        """A fresh ID token (current roles) for the session; False (and the
        session ends) if Keycloak refuses: signed out, disabled, role gone."""
        try:
            claims, id_token, refresh_token = self.app.oidc.refresh(sess["refresh_token"])
        except OIDCError:
            with self.app.lock:
                self.app.sessions.pop(sess["sid"], None)
            return False
        perms = token_perms(claims)
        with self.app.lock:
            if not perms or claims.get("preferred_username") != sess["user"]:
                self.app.sessions.pop(sess["sid"], None)
                return False
            stored = self.app.sessions.get(sess["sid"])
            if stored is None:
                return False
            stored.update(id_token=id_token, refresh_token=refresh_token, perms=perms,
                          exp=float(claims.get("exp") or 0))
        sess.update(id_token=id_token, refresh_token=refresh_token, perms=perms, exp=float(claims.get("exp") or 0))
        return True

    # -- dispatch -----------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        actions.set_token(None)          # this thread may have served someone else before
        try:
            self.app.sweep()
            cert = self.client_cert()
            if not cert:
                return self.deny(403, "A client certificate issued by this fabric's certificate authority is required.")
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}

            if path == "/static/app.css" and method == "GET":
                return self.send(200, views.css(), "text/css; charset=utf-8")
            if path == "/login" and method == "GET":
                return self.login(cert, query.get("next", "/"))
            if path == "/oidc/callback" and method == "GET":
                return self.callback(cert, query)

            sess = self.session(cert)
            if not sess:
                return self.redirect("/login")
            actions.set_token(sess["id_token"])

            if method == "POST":
                origin = self.headers.get("Origin", "")
                form = self.read_form()
                csrf = form.get("csrf", "")
                if (origin != self.app.public_url or not isinstance(csrf, str)
                        or not hmac.compare_digest(csrf, sess["csrf"])):
                    return self.deny(403, "Request rejected (CSRF check failed). Reload the page and try again.")
                return self.post(sess, path, form)
            return self.get(sess, path, query)
        except actions.ValidationError as exc:
            self.deny(400, str(exc))
        except actions.AuthError:
            self.redirect("/login")
        except actions.PermissionDenied as exc:
            self.deny(403, f"Not allowed: {exc}.")
        except actions.AgentError:
            traceback.print_exc()
            self.deny(503, "The fabric-agent service is unavailable. See `journalctl -u fabric-agent`.")
        except Exception:
            traceback.print_exc()
            self.deny(500, "Internal error. See `journalctl -u webui`.")

    # -- auth ---------------------------------------------------------------
    def login(self, cert, next_path="/"):
        # Only a local path may follow the login (no open redirect).
        if not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
            next_path = "/"
        url, state, nonce, verifier = self.app.oidc.start_login()
        with self.app.lock:
            self.app.pending[state] = {"nonce": nonce, "verifier": verifier, "fp": cert["fp"], "created": time.time(),
                                       "next": next_path}
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
            claims, id_token, refresh_token = self.app.oidc.finish_login(query["code"], pending["verifier"],
                                                                         pending["nonce"])
        except OIDCError as exc:
            return self.deny(401, f"Login failed: {exc}")

        user = claims.get("preferred_username", "")
        actions.set_token(id_token)          # the audit calls below go to fabric-agent as this user
        if user != cert["cn"]:
            actions.audit(user or "unknown", "LOGIN_DENIED", f"cert CN {cert['cn']!r} does not match user")
            return self.deny(403, "Your client certificate does not belong to this user.")
        perms = token_perms(claims)
        if not perms:
            actions.audit(user, "LOGIN_DENIED", "no fabric role")
            return self.deny(403, f"Your account has no fabric role (for example '{self.app.admin_role}'). "
                                  "Ask an administrator to add you to a fabric group.")

        sid = secrets.token_urlsafe(32)
        now = time.time()
        with self.app.lock:
            self.app.sessions[sid] = {"user": user, "fp": cert["fp"], "csrf": secrets.token_urlsafe(32),
                                      "id_token": id_token, "refresh_token": refresh_token, "perms": perms,
                                      "exp": float(claims.get("exp") or now), "created": now, "last": now,
                                      # when the person last proved password + TOTP (step-up for vault changes)
                                      "auth_at": min(float(claims.get("auth_time") or now), now)}
        actions.audit(user, "LOGIN", f"cert={cert['fp'][:16]}")
        # A 200 + meta refresh (rather than a redirect) so the first request
        # carrying the Strict session cookie is initiated from this origin.
        self.send(200, views.continue_page(pending.get("next") or "/"), headers=[
            self.set_cookie(SESSION_COOKIE, sid, self.app.max_age),
            self.set_cookie(LOGIN_COOKIE, "", 0, "Lax")])

    # -- pages --------------------------------------------------------------
    @staticmethod
    def ctx(sess):
        return {"user": sess["user"], "csrf": sess["csrf"], "perms": sess.get("perms") or [],
                "version": actions.version_info()}

    def bind9_page(self, ctx, query, status=200):
        section = query.get("view") if query.get("view") in ("reverse", "tsig") else "forward"
        zones = actions.list_zones()
        forward = [z for z in zones if not z.get("reverse")]
        key = query.get("zone") or (forward[0]["key"] if forward else "")
        return self.send(status, views.bind9(
            ctx, section, zones, zone=actions.zone_detail(key) if section == "forward" and key else None,
            types=actions.RECORD_TYPES, msg=query.get("msg", ""), err=query.get("err", ""),
            tsig_keys=actions.list_tsig_keys() if section == "tsig" else None,
            reverse=actions.reverse_zones() if section == "reverse" else None))

    def stepca_page(self, ctx, view, status=200, **extra):
        if view not in views.STEPCA_VIEWS:
            view = "ca"
        try:
            ca = actions.ca_summary()
        except (actions.AgentError, actions.ValidationError):
            ca = None
        devices = []
        if view in ("sign", "issue"):
            try:                                # linking to a device is optional; the directory may be down
                devices = actions.device_overview()["devices"]
            except (actions.AgentError, actions.ValidationError):
                pass
        issued = actions.list_issued() if view == "issued" else None
        return self.send(status, views.stepca(ctx, view, ca, issued=issued, devices=devices, **extra))

    def openbao_page(self, ctx, query):
        view = query.get("view") if query.get("view") in views.OPENBAO_VIEWS else "status"
        slots = actions.vault_slots()
        devices = actions.vault_devices() if view in ("add-security-key", "add-usb") else None
        return self.send(200, views.openbao(ctx, actions.vault_status(), view, slots["slots"], devices,
                                            slot_id=query.get("slot", ""), host=slots["host"], live=True,
                                            msg=query.get("msg", ""), err=query.get("err", ""),
                                            add_live={"security-key": True, "usb": True, "hsm": True}))

    def vault_post(self, sess, parts, form):
        """Unlock-method changes: a fresh sign-in (step-up) and the host name
        typed as confirmation, then one fabric-agent call."""
        back = {"view": "unlock"}
        if time.time() - sess.get("auth_at", 0) > STEP_UP:
            return self.redirect("/login?" + urllib.parse.urlencode({"next": "/openbao?view=unlock&msg=" + urllib.parse.quote(
                "Signed in again. Repeat the change: vault changes need a sign-in from the last 5 minutes.")}))
        host = actions.vault_slots()["host"]
        if not host or form.get("confirm", "") != host:
            return self.redirect("/openbao?" + urllib.parse.urlencode({**back, "err": f"Type this host's name ({host}) "
                                                                                       "to confirm."}))
        try:
            if parts == ["rotate"]:
                res = actions.vault_rotate(sess["user"])
                msg = f"Vault key rotated to {res['key_id']}." + (
                    f" Methods without their device removed: {', '.join(res['dropped'])}." if res["dropped"] else "")
            elif len(parts) == 3 and parts[0] == "slots" and parts[2] in ("test", "remove"):
                actions.vault_slot_action(sess["user"], parts[1], parts[2])
                msg = "Test passed: the method unwrapped and verified the vault key." if parts[2] == "test" else \
                    "Unlock method removed."
            elif parts == ["slots", "add-usb"]:
                slot = actions.vault_add_usb(sess["user"], form.get("disk", ""), form.get("label", ""))["id"]
                msg = f"USB stick added ({slot}), read back and verified."
            elif parts == ["slots", "add-security-key"]:
                module, _, serial = form.get("token", "").rpartition("|")
                key_id = form.get("key_id", "") if form.get("key") == "existing" else "new"
                slot = actions.vault_add_security_key(sess["user"], module, serial, form.get("pin", ""), key_id,
                                                      form.get("label", ""))["id"]
                msg = f"Security key added ({slot}): the token wrapped and unwrapped the vault key."
            elif parts == ["slots", "add-hsm"]:
                pems = {f: (form.get(f) or b"").decode(errors="replace") if isinstance(form.get(f), bytes)
                        else str(form.get(f) or "") for f in ("ca_file", "cert_file", "key_file")}
                slot = actions.vault_add_kmip(form.get("endpoint", ""), form.get("key_id", ""), pems["ca_file"],
                                              pems["cert_file"], pems["key_file"], form.get("server_name", ""),
                                              form.get("label", ""))["id"]
                msg = f"HSM added ({slot}): the device wrapped and unwrapped the vault key."
            elif len(parts) == 2 and parts[0] == "slots" and parts[1].startswith("add-"):
                raise actions.ValidationError("Adding this kind of unlock method arrives in the next update.")
            else:
                return self.deny(404, "Not found.")
        except actions.ValidationError as exc:
            return self.redirect("/openbao?" + urllib.parse.urlencode({**back, "err": str(exc)}))
        return self.redirect("/openbao?" + urllib.parse.urlencode({**back, "msg": msg}))

    def dirsrv_page(self, ctx, query, status=200):
        view = query.get("view") if query.get("view") in ("device", "roles", "role", "people") else "devices"
        kw = {"msg": query.get("msg", ""), "err": query.get("err", "")}
        try:
            if view == "people":
                return self.send(status, views.dirsrv(ctx, view, people=actions.list_people(), **kw))
            data = actions.device_overview()
        except (actions.AgentError, actions.ValidationError) as exc:
            return self.send(status, views.dirsrv(ctx, view, unavailable=str(exc), **kw))
        if view == "device":
            kw["device"] = next((d for d in data["devices"] if d["name"] == query.get("name")), None)
            view = view if kw["device"] else "devices"
        if view == "role":
            kw["role"] = next((r for r in data["roles"] if r["name"] == query.get("name")), None)
            view = view if kw["role"] else "roles"
        return self.send(status, views.dirsrv(ctx, view, data=data, **kw))

    def get(self, sess, path, query):
        ctx = self.ctx(sess)
        if path == "/":
            return self.send(200, views.overview(ctx, actions.service_status()))
        if path == "/bind9":
            return self.bind9_page(ctx, query)
        if path == "/stepca":
            return self.stepca_page(ctx, query.get("view", "ca"), device=query.get("device", ""))
        if path == "/dirsrv":
            return self.dirsrv_page(ctx, query)
        if path == "/openbao":
            return self.openbao_page(ctx, query)
        if path == "/kea":
            return self.send(200, views.kea(ctx, actions.dhcp_overview(), query.get("msg", ""), query.get("err", "")))
        if path.lstrip("/") in views.PLACEHOLDERS:
            return self.send(200, views.placeholder(ctx, path.lstrip("/")))
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
        if path.startswith("/bind9/zone/"):
            rest = urllib.parse.unquote(path[len("/bind9/zone/"):])
            key, _, op = rest.rpartition("/")
            back = "/bind9?zone=" + urllib.parse.quote(key)
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
                return self.redirect(back + "&" + urllib.parse.urlencode({"msg": msg}))
            except actions.ValidationError as exc:
                return self.redirect(back + "&" + urllib.parse.urlencode({"err": str(exc)}))
        if path == "/apply":
            ok, output = actions.apply_changes(user)
            return self.send(200, views.apply_result(self.ctx(sess), ok, output))
        if path.startswith("/stepca/"):
            return self.stepca_post(sess, path[len("/stepca/"):], form)
        if path.startswith("/openbao/"):
            return self.vault_post(sess, [urllib.parse.unquote(p) for p in path.split("/")[2:]], form)
        if path.startswith("/dirsrv/"):
            return self.dirsrv_post(sess, [urllib.parse.unquote(p) for p in path.split("/")[2:]], form)
        if path.startswith("/kea/reservations"):
            parts = [urllib.parse.unquote(p) for p in path.split("/")[3:]]
            try:
                if not parts:
                    res = actions.add_reservation(form.get("mac", ""), form.get("ip", ""), form.get("hostname", ""))
                    msg = f"Reserved {res['reservation']['ip']} for {res['reservation']['mac']}."
                elif len(parts) == 2 and parts[1] == "delete":
                    res = actions.remove_reservation(parts[0])
                    msg = f"Reservation for {parts[0]} removed."
                else:
                    return self.deny(404, "Not found.")
                if not res.get("applied"):
                    return self.redirect("/kea?" + urllib.parse.urlencode({"err": msg + " Saved, but applying failed: "
                                                                          + res.get("output", "")[-300:]}))
            except actions.ValidationError as exc:
                return self.redirect("/kea?" + urllib.parse.urlencode({"err": str(exc)}))
            return self.redirect("/kea?" + urllib.parse.urlencode({"msg": msg}))
        if path.startswith("/bind9/tsig/"):
            return self.tsig_post(sess, urllib.parse.unquote(path[len("/bind9/tsig/"):]), form)
        return self.deny(404, "Not found.")

    def stepca_post(self, sess, op, form):
        """Manual PKI: each form maps to one fabric-agent operation."""
        ctx, user = self.ctx(sess), sess["user"]
        back = {"sign/review": "sign", "sign": "sign", "issue": "issue", "inspect": "inspect",
                "convert": "convert"}.get(op)
        if not back:
            return self.deny(404, "Not found.")
        try:
            if op == "sign/review":
                req = actions.describe_csr(user, self.upload(form, "csr_file", "csr"))
                return self.stepca_page(ctx, "sign", review=req, device=form.get("device", ""))
            if op == "sign":
                result = actions.sign_csr(user, form.get("csr", ""), form.get("days", ""), form.get("device", ""))
                return self.send(200, views.pki_result(ctx, "sign", result))
            if op == "issue":
                sans = [n for n in re.split(r"[\s,]+", form.get("sans", "")) if n]
                result = actions.issue_key_pair(user, form.get("cn", ""), sans, form.get("key_type", ""),
                                                form.get("days", ""), form.get("device", ""))
                return self.send(200, views.pki_result(ctx, "issue", result))
            if op == "inspect":
                return self.stepca_page(ctx, "inspect",
                                        inspected=actions.inspect_pem(user, self.upload(form, "file", "data")))
            result = actions.convert_cert(user, self.upload(form, "cert_file", "cert"),
                                          self.upload(form, "key_file", "key"))
            return self.send(200, views.pki_result(ctx, "convert", result))
        except actions.ValidationError as exc:
            return self.stepca_page(ctx, back, status=400, err=str(exc))

    @staticmethod
    def device_form(form):
        return {"type": form.get("type", ""), "owner": form.get("owner", ""), "description": form.get("description", ""),
                "macs": [m for m in re.split(r"[\s,]+", form.get("macs", "")) if m],
                "enabled": bool(form.get("enabled")),
                "roles": [k[5:] for k, val in form.items() if k.startswith("role_") and val]}

    @staticmethod
    def role_form(form):
        return {"description": form.get("description", ""), "vlan": form.get("vlan", ""),
                "priority": form.get("priority", ""),
                "permissions": [k[5:] for k, val in form.items() if k.startswith("perm_") and val]}

    def dirsrv_post(self, sess, parts, form):
        """Devices, device roles and people: each form maps to one fabric-agent call."""
        user = sess["user"]
        kind, name, op = (parts + ["", "", ""])[:3]
        if kind == "people":
            try:
                if name == "_new" and not op:
                    uid, what = form.get("uid", ""), "created"
                    password = actions.create_person(uid, form.get("first", ""), form.get("last", ""),
                                                     form.get("email", ""))
                elif name and op == "reset":
                    uid, what = name, "reset"
                    password = actions.reset_sign_in(uid)
                else:
                    return self.deny(404, "Not found.")
            except actions.ValidationError as exc:
                return self.redirect("/dirsrv?" + urllib.parse.urlencode({"view": "people", "err": str(exc)}))
            return self.send(200, views.person_result(self.ctx(sess), uid, what, password))
        if kind not in ("devices", "roles") or not name:
            return self.deny(404, "Not found.")
        listing = {"view": kind}
        here = {"view": kind[:-1], "name": name}
        save, delete = ((actions.save_device, actions.delete_device) if kind == "devices"
                        else (actions.save_role, actions.delete_role))
        fields = self.device_form(form) if kind == "devices" else self.role_form(form)
        try:
            if name == "_new" and not op:
                created = save(user, form.get("name", ""), fields, new=True)["name"]
                back, msg = {"view": kind[:-1], "name": created}, f"{created} created."
            elif op == "delete":
                delete(user, name)
                back, msg = listing, f"{name} deleted."
            elif kind == "devices" and op == "certs":
                actions.link_device_cert(user, name, form.get("sha256", ""), link=False)
                back, msg = here, "Certificate unlinked."
            elif not op:
                save(user, name, fields)
                back, msg = here, "Saved."
            else:
                return self.deny(404, "Not found.")
            return self.redirect("/dirsrv?" + urllib.parse.urlencode({**back, "msg": msg}))
        except actions.ValidationError as exc:
            back = listing if name == "_new" else here
            return self.redirect("/dirsrv?" + urllib.parse.urlencode({**back, "err": str(exc)}))

    def tsig_post(self, sess, rest, form):
        """TSIG keys for a zone: create, rotate, delete (apply publishes them)."""
        ctx, user = self.ctx(sess), sess["user"]
        name, _, op = rest.rpartition("/")
        back = {"view": "tsig"}
        try:
            if rest == "create":
                hosts = [h for h in re.split(r"[\s,]+", form.get("hosts", "")) if h]
                types = [t for t in actions.RECORD_TYPES if form.get(f"type_{t}")]
                r = actions.create_tsig_key(user, form.get("name", ""), form.get("zone", ""), form.get("scope", ""),
                                            hosts, types, form.get("secret", ""))
                return self.send(200, views.tsig_result(ctx, r["key"]["name"], r["secret"], r["ini"], "created"))
            if op == "rotate":
                r = actions.rotate_tsig_key(user, name)
                return self.send(200, views.tsig_result(ctx, name, r["secret"], r["ini"], "rotated"))
            if op == "delete":
                actions.delete_tsig_key(user, name)
                return self.redirect("/bind9?" + urllib.parse.urlencode(
                    {**back, "msg": f"TSIG key {name} removed. Apply to publish."}))
            return self.deny(404, "Not found.")
        except actions.ValidationError as exc:
            return self.bind9_page(ctx, {**back, "err": str(exc)}, status=400)


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config) as f:
        cfg = json.load(f)

    actions.configure(cfg["agent_socket"])
    Handler.app = App(cfg)
    sock = cfg["socket"]
    if os.path.exists(sock):
        os.unlink(sock)
    old_umask = os.umask(0o117)
    try:
        server = UnixServer(sock, Handler)
    finally:
        os.umask(old_umask)
    # Group-owned by nginx (this container's user is a member via group_add).
    gid = cfg["socket_gid"]
    os.chown(sock, -1, gid if isinstance(gid, int) else grp.getgrnam(gid).gr_gid)
    os.chmod(sock, 0o660)
    print(f"webui listening on {sock}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
