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
    """Purpose: List the fabric permissions in a verified ID token: every role in the 'roles' claim that starts with
             'fabric:', with the prefix removed.
    Inputs:  claims — dict of verified ID token claims; reads claims['roles'] (a list; non-str entries are ignored;
             missing or empty means none).
    Returns: sorted list of unique permission names, e.g. ['dns:read', 'dns:write']; [] if there are none.
    Fails:   never for a list or missing 'roles'; TypeError if 'roles' is a truthy non-iterable value.
    Feeds:   Handler.callback (none → 403) and Handler.renew (none → session ends); stored as sess['perms'] and shown
             to pages through Handler.ctx → views._render's can().
    """
    return sorted({r[len(PERM_PREFIX):] for r in claims.get("roles") or []
                   if isinstance(r, str) and r.startswith(PERM_PREFIX)})


def parse_dn(dn):
    """Purpose: Split an RFC 2253 distinguished name (as nginx's $ssl_client_s_dn / _i_dn gives it) into (attribute,
             value) pairs, honouring backslash escapes.
    Inputs:  dn — str, e.g. 'CN=jim,O=Fabric'; may be empty.
    Returns: list of (ATTRIBUTE upper-cased, value) tuples, whitespace stripped, in the order given; an empty dn
             gives [('', '')].
    Fails:   never.
    Feeds:   App.__init__ (issuer_dn of the Step-CA intermediate) and Handler.client_cert (issuer and subject of the
             presented certificate).
    Notes:   An escaped character is kept literally (so an escaped comma does not split); hex escapes (such as an
             escaped 2C) are not decoded and multi-valued RDNs ('+') are not split. Both sides are parsed the same
             way, so the issuer comparison still works.
    """
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
    """Purpose: Read a PEM certificate's subject DN in RFC 2253 form with openssl.
    Inputs:  path — str, path to a PEM certificate (the Step-CA intermediate from the config).
    Returns: the subject str without the 'subject=' prefix, e.g. 'CN=Fabric Intermediate CA,O=Fabric'.
    Fails:   subprocess.CalledProcessError when openssl cannot read the file; FileNotFoundError if openssl is not
             installed. Both stop the server at start.
    Feeds:   App.__init__ → parse_dn → App.issuer_dn.
    """
    res = subprocess.run(["openssl", "x509", "-in", path, "-noout", "-subject", "-nameopt", "RFC2253"],
                         capture_output=True, text=True, check=True)
    return res.stdout.strip().removeprefix("subject=").strip()


class App:
    def __init__(self, cfg):
        """Purpose: Hold the web UI's shared state: config, the Keycloak OIDC client, the expected client-certificate
                 issuer, and the in-memory sessions and pending logins.
        Inputs:  cfg — dict from webui.json: public_url, ca_file, intermediate_ca, admin_role, session_idle (default
                 900 s), session_max (default 28800 s), keycloak {ip, port (default 8443), hostname, realm,
                 client_id, client_secret}.
        Returns: None (constructor); sets oidc, sso_origin, admin_role, issuer_dn, idle, max_age, sessions {sid:
                 session}, pending {state: login}, lock.
        Fails:   KeyError for a missing required config key; ValueError from int() on bad session limits;
                 CalledProcessError from cert_subject_rfc2253. All stop the server at start.
        Feeds:   main, which sets it as Handler.app for every request.
        Notes:   admin_role is only named in the 'no fabric role' refusal; access is decided by the fabric:
                 permission roles in the token. Sessions live only in memory: a restart signs everyone out.
        """
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
        """Purpose: Drop expired sessions (idle longer than idle or older than max_age) and login attempts older than
                 LOGIN_TTL (600 s).
        Inputs:  none (reads and changes self.sessions and self.pending under self.lock).
        Returns: None.
        Fails:   never.
        Feeds:   Handler.handle_request, at the start of every request.
        """
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
        """Purpose: Name the client in log lines: the address nginx forwarded, since the unix socket has none.
        Inputs:  none (reads the X-Real-IP request header).
        Returns: the X-Real-IP value, or 'nginx' when it is absent.
        Fails:   never.
        Feeds:   log_message.
        """
        return self.headers.get("X-Real-IP", "nginx")

    def log_message(self, fmt, *args):
        """Purpose: Write one request or error log line to stderr (the container log), prefixed with the client address.
        Inputs:  fmt — %-format str; args — its values (both from BaseHTTPRequestHandler).
        Returns: None.
        Fails:   never in practice (TypeError only if fmt and args did not match).
        Feeds:   — (called by BaseHTTPRequestHandler).
        """
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

    def send(self, status, body=b"", content_type="text/html; charset=utf-8", headers=None):
        """Purpose: Send a complete response with the fixed security headers.
        Inputs:  status — int HTTP status; body — bytes or str (str is UTF-8 encoded), default empty; content_type —
                 default text/html; headers — list of (name, value) extra headers, e.g. Location, Set-Cookie.
        Returns: None; the response is written (no body for HEAD).
        Fails:   OSError (e.g. BrokenPipeError) when nginx has closed the connection.
        Feeds:   —; used by every handler, redirect and deny.
        Notes:   Cache-Control no-store, nosniff, no referrer, no framing, COOP same-origin and a CSP without any
                 script source: styles and images from self only, forms may post to self and the Keycloak origin (its
                 login form).
        """
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
        """Purpose: Send a 303 See Other to a location.
        Inputs:  location — str URL or path; headers — optional list of extra (name, value) headers such as
                 Set-Cookie.
        Returns: None; the 303 response is sent.
        Fails:   as send.
        Feeds:   —.
        """
        self.send(303, b"", headers=[("Location", location)] + list(headers or []))

    def deny(self, status, message):
        """Purpose: Send an error page with a status and a message.
        Inputs:  status — int HTTP status (400, 401, 403, 404, 500, 503); message — str shown to the person
                 (autoescaped).
        Returns: None; the error page is sent.
        Fails:   as send.
        Feeds:   —.
        """
        self.send(status, views.error_page(status, message))

    def cookie(self, name):
        """Purpose: Read one cookie from the request.
        Inputs:  name — str cookie name; reads the Cookie header.
        Returns: the cookie value str, or None when it is absent or the Cookie header does not parse.
        Fails:   never.
        Feeds:   session (__Host-webui) and callback (__Host-webui-login).
        """
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None
        return jar[name].value if name in jar else None

    @staticmethod
    def set_cookie(name, value, max_age, samesite="Strict"):
        """Purpose: Build a Set-Cookie header for the web UI's host-only cookies.
        Inputs:  name — str; value — str, written as is (callers pass URL-safe tokens or ''); max_age — int seconds,
                 0 deletes the cookie; samesite — 'Strict' (default) or 'Lax'.
        Returns: ('Set-Cookie', '<name>=<value>; Path=/; Secure; HttpOnly; SameSite=<samesite>; Max-Age=<max_age>').
        Fails:   never.
        Feeds:   login, callback and post (/logout), which pass it to send / redirect.
        Notes:   The __Host- cookie names require Secure, Path=/ and no Domain, so no other host can set them.
        """
        return ("Set-Cookie", f"{name}={value}; Path=/; Secure; HttpOnly; SameSite={samesite}; Max-Age={max_age}")

    def read_form(self):
        """Purpose: Read and parse a POST body: urlencoded or multipart form data.
        Inputs:  none; reads the Content-Length and Content-Type headers and the request body (at most MAX_BODY, 64
                 KiB).
        Returns: dict: urlencoded → {name: str} (first value of each, blanks kept); multipart → {name: str} for text
                 parts and {name: bytes} for file parts.
        Fails:   ValueError 'request too large' above MAX_BODY, and ValueError from int() on a bad Content-Length;
                 neither is a ValidationError, so handle_request answers 500.
        Feeds:   handle_request (the CSRF check), then post and its vault_post, radius_post, stepca_post, dirsrv_post
                 and tsig_post.
        """
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
        """Purpose: Take a value from an upload field or, if none was uploaded, from its paste field; binary files (DER)
                 are base64-encoded for the agent.
        Inputs:  form — dict from read_form; file_field — str name of the file input; text_field — str name of the
                 textarea.
        Returns: str: the uploaded file as ASCII text (PEM), or base64 of it if it is not ASCII, else the pasted
                 text, else ''.
        Fails:   never.
        Feeds:   stepca_post (sign/review, inspect, convert) → agentclient describe_csr, inspect_pem, convert_cert.
        """
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
        """Purpose: Gates 1 and 2: the verified client certificate nginx forwarded, accepted only if it was issued
                 directly by the fabric Step-CA intermediate.
        Inputs:  none; reads the headers X-SSL-Client-Verify, X-SSL-Client-I-DN, X-SSL-Client-S-DN and
                 X-SSL-Client-Fingerprint (set by nginx) and self.app.issuer_dn.
        Returns: {'cn': str, 'fp': str} — the subject CN and certificate fingerprint; None when verification did not
                 succeed, the issuer DN differs from the intermediate's (compared as a set of attributes), the
                 subject does not have exactly one non-empty CN, or the fingerprint is missing.
        Fails:   never — refusal is the None return.
        Feeds:   handle_request (None → 403), then login, callback and session.
        Notes:   The headers can be trusted only because this server listens on a unix socket that nobody but nginx
                 can reach.
        """
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
        """Purpose: Gates 3 and 4: the signed-in session for this request, bound to the presented certificate, renewing
                 its ID token shortly before it expires.
        Inputs:  cert — dict from client_cert; reads the __Host-webui cookie and self.app.sessions.
        Returns: a copy of the session plus 'sid': {user, fp, csrf, id_token, refresh_token, perms, exp, created,
                 last, auth_at, sid}; None when there is no cookie, the id is unknown, the session is idle or too
                 old, the certificate fingerprint or CN differs (the session is then deleted), or renewal failed.
        Fails:   OIDC refusals are a None return (via renew); OSError / ssl.SSLError from the Keycloak refresh
                 propagate to handle_request (500).
        Feeds:   handle_request (None → redirect to /login; else the ID token goes to agentclient and the session to
                 get / post).
        Notes:   It updates 'last' (idle timer) and renews when fewer than REFRESH_BEFORE (60 s) remain on the ID
                 token, so role changes in Keycloak apply within one token lifetime.
        """
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
        """Purpose: Replace a session's ID token with a fresh one from Keycloak, picking up the person's current roles;
                 end the session if Keycloak refuses.
        Inputs:  sess — dict from session (uses sid, refresh_token, user); updated in place on success.
        Returns: True if renewed (stored session and sess get id_token, refresh_token, perms, exp); False if Keycloak
                 refused (OIDCError), the new token has no fabric permission, or the username changed — these remove
                 the stored session — or the session vanished meanwhile.
        Fails:   OSError / ssl.SSLError from the Keycloak call propagate (500 in handle_request).
        Feeds:   session.
        Notes:   auth_at is not changed: a refresh is not a new sign-in, so the vault step-up still needs one.
        """
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
        """Purpose: Answer HEAD exactly like GET; send leaves out the body.
        Inputs:  the request, as do_GET.
        Returns: None; the response is sent.
        Fails:   as handle_request.
        Feeds:   — (called by BaseHTTPRequestHandler).
        """
        self.do_GET()

    def do_GET(self):
        """Purpose: Entry point for GET requests.
        Inputs:  the request (path, headers).
        Returns: None; the response is sent by handle_request('GET').
        Fails:   as handle_request.
        Feeds:   — (called by BaseHTTPRequestHandler and do_HEAD).
        """
        self.handle_request("GET")

    def do_POST(self):
        """Purpose: Entry point for POST requests.
        Inputs:  the request (path, headers, body).
        Returns: None; the response is sent by handle_request('POST').
        Fails:   as handle_request.
        Feeds:   — (called by BaseHTTPRequestHandler).
        """
        self.handle_request("POST")

    def handle_request(self, method):
        """Purpose: Run every request through the security gates, then route it, and turn errors into error pages.
        Inputs:  method — 'GET' or 'POST'. Reads the path and query (first value per key), the client-certificate
                 headers, the session cookie, and for POST the Origin header and the form's csrf field.
        Returns: the response: GET /static/app.css → 200 stylesheet; GET /login and GET /oidc/callback → login /
                 callback (no session needed); no valid session → 303 to /login; POST → post; GET → get.
        Fails:   403 without an accepted client certificate; 403 'CSRF check failed' when Origin is not public_url or
                 csrf does not match the session's; 400 with the message on agentclient.ValidationError; 303 to
                 /login on AuthError; 403 'Not allowed: …' on PermissionDenied; 503 on AgentError; 500 on anything
                 else (traceback to stderr).
        Feeds:   — (called by do_GET, do_HEAD, do_POST).
        Notes:   It first clears the agent token for this thread, then sets the session's ID token so every
                 fabric-agent call runs as the signed-in person; fabric-agent enforces the permissions.
        """
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
        """Purpose: Start a Keycloak sign-in: remember the attempt (bound to this certificate) and send the browser to
                 Keycloak.
        Inputs:  cert — dict from client_cert (fp is stored); next_path — str from ?next=, where to go after sign-in;
                 anything that is not a local path (not starting with '/', starting with '//', or containing a
                 backslash) becomes '/'.
        Returns: 303 to the Keycloak authorization URL, setting __Host-webui-login (the state, SameSite=Lax, 600 s);
                 App.pending[state] gets nonce, verifier, fp, created, next.
        Fails:   never refuses.
        Feeds:   handle_request (GET /login), reached from session failures and the vault step-up in vault_post.
        Notes:   The login cookie is Lax because it must come back with the top-level redirect from Keycloak.
        """
        if not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
            next_path = "/"
        url, state, nonce, verifier = self.app.oidc.start_login()
        with self.app.lock:
            self.app.pending[state] = {"nonce": nonce, "verifier": verifier, "fp": cert["fp"], "created": time.time(),
                                       "next": next_path}
        # Lax: the cookie must accompany the top-level redirect back from Keycloak.
        self.redirect(url, [self.set_cookie(LOGIN_COOKIE, state, LOGIN_TTL, "Lax")])

    def callback(self, cert, query):
        """Purpose: Finish a Keycloak sign-in: check the attempt, verify the tokens, check the person against the
                 certificate and their fabric roles, and create the session.
        Inputs:  cert — dict from client_cert; query — dict with state, code or error; reads the __Host-webui-login
                 cookie and App.pending.
        Returns: 200 'Signed in' page (meta refresh to the stored next path) that sets __Host-webui (the session id,
                 Max-Age session_max) and clears the login cookie; the session gets a new CSRF token, the tokens,
                 perms and auth_at; LOGIN is audited.
        Fails:   400 when the state is unknown or expired, the login cookie does not match, or another certificate
                 started the login (the attempt is used up either way); 401 when Keycloak returned an error or no
                 code; 401 'Login failed: …' on OIDCError; 403 when the Keycloak username is not the certificate CN,
                 and 403 when the token has no fabric role (both audited as LOGIN_DENIED). agent errors from
                 agentclient (ValidationError, AuthError, PermissionDenied, AgentError) propagate to handle_request
                 (400, redirect to /login, 403, 503) from the audit calls.
        Feeds:   handle_request (GET /oidc/callback).
        Notes:   A 200 with meta refresh rather than a redirect, so the first request carrying the Strict session
                 cookie starts from this origin. auth_at is the token's auth_time (never later than now), used by the
                 vault step-up.
        """
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
        """Purpose: The page context every view needs: who is signed in, the CSRF token, their permissions and the
                 installed version.
        Inputs:  sess — dict from session.
        Returns: {'user': str, 'csrf': str, 'perms': list, 'version': actions.version_info()}.
        Fails:   Agent errors from agentclient (ValidationError, AuthError, PermissionDenied, AgentError) propagate
                 to handle_request (400, redirect to /login, 403, 503) from version_info.
        Feeds:   get, post (/apply), radius_post, stepca_post, dirsrv_post, tsig_post → every views page.
        """
        return {"user": sess["user"], "csrf": sess["csrf"], "perms": sess.get("perms") or [],
                "version": actions.version_info()}

    def bind9_page(self, ctx, query, status=200):
        """Purpose: Render the BIND9 tab: forward zone records, generated reverse zones or TSIG keys.
        Inputs:  ctx — dict from ctx; query — dict: view ('reverse' or 'tsig', anything else is forward), zone (a
                 zone key; default the first forward zone), msg, err; status — int, default 200.
        Returns: the BIND9 page with the given status.
        Fails:   Agent errors from agentclient (ValidationError, AuthError, PermissionDenied, AgentError) propagate
                 to handle_request (400, redirect to /login, 403, 503) (e.g. an unknown zone key → 400).
        Feeds:   get (/bind9) and tsig_post (re-shows the TSIG section with 400 on a validation error).
        """
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
        """Purpose: Render the Step-CA tab for one sub-view, with the CA summary, linkable devices and the issued list
                 where needed.
        Inputs:  ctx — dict from ctx; view — str, one of views.STEPCA_VIEWS (anything else → 'ca'); status — int,
                 default 200; extra — passed to views.stepca (review, inspected, err, device).
        Returns: the Step-CA page with the given status.
        Fails:   a failing CA summary shows as unreadable and a failing device list as no devices (AgentError,
                 ValidationError only); errors from list_issued on the 'issued' view propagate to handle_request.
        Feeds:   get (/stepca) and stepca_post (review and inspect results, validation errors with 400).
        """
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
        """Purpose: Render the OpenBao tab: status, unlock methods and their add/rotate/remove forms, secrets, disk
                 encryption.
        Inputs:  ctx — dict from ctx; query — dict: view (one of views.OPENBAO_VIEWS, else 'status'), slot (for the
                 remove view), msg, err.
        Returns: 200 OpenBao page; slot changes are live and every add type is enabled.
        Fails:   Agent errors from agentclient (ValidationError, AuthError, PermissionDenied, AgentError) propagate
                 to handle_request (400, redirect to /login, 403, 503) from vault_slots, vault_status and
                 vault_devices (the last only for add-security-key and add-usb).
        Feeds:   get (/openbao).
        """
        view = query.get("view") if query.get("view") in views.OPENBAO_VIEWS else "status"
        slots = actions.vault_slots()
        devices = actions.vault_devices() if view in ("add-security-key", "add-usb") else None
        return self.send(200, views.openbao(ctx, actions.vault_status(), view, slots["slots"], devices,
                                            slot_id=query.get("slot", ""), host=slots["host"], live=True,
                                            msg=query.get("msg", ""), err=query.get("err", ""),
                                            add_live={"security-key": True, "usb": True, "hsm": True}))

    def vault_post(self, sess, parts, form):
        """Purpose: Change the vault's unlock methods: rotate the key, test or remove a method, or add a USB stick,
                 security key or KMIP HSM — each one fabric-agent call after a recent sign-in and the host name typed
                 as confirmation.
        Inputs:  sess — dict from session (user, auth_at); parts — path segments after /openbao/: ['rotate'],
                 ['slots', <id>, 'test'|'remove'], ['slots', 'add-usb'], ['slots', 'add-security-key'], ['slots',
                 'add-hsm']; form — confirm (must equal the host name), label, and per kind: disk; token
                 ('<module>|<serial>'), key ('existing' uses key_id, else 'new'), pin; endpoint, key_id, server_name,
                 ca_file / cert_file / key_file (uploads or text).
        Returns: 303 to /login?next=/openbao?view=unlock… when the last sign-in is older than STEP_UP (300 s);
                 otherwise 303 to /openbao?view=unlock with msg (success) or err.
        Fails:   303 with err when the confirmation is not the host name, on ValidationError, and for other 'add-…'
                 kinds ('arrives in the next update'); 404 for any other path; AgentError, PermissionDenied and
                 AuthError propagate to handle_request; KeyError if the agent's answer lacks key_id, dropped or id.
        Feeds:   post (/openbao/…).
        Notes:   The step-up is checked before the path, so even an unknown path asks for a fresh sign-in first.
        """
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
        """Purpose: Render the 389-DS tab: devices, one device, roles, one role, or people.
        Inputs:  ctx — dict from ctx; query — dict: view ('device', 'roles', 'role', 'people', else 'devices'), name
                 (device or role; unknown → the list), msg, err; status — int, default 200.
        Returns: the directory page with the given status; when the directory cannot be read (AgentError,
                 ValidationError) the page shows why instead of the data.
        Fails:   PermissionDenied and AuthError propagate to handle_request (403, redirect to /login).
        Feeds:   get (/dirsrv).
        """
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
        """Purpose: Route a signed-in GET to its page.
        Inputs:  sess — dict from session; path — str: /, /bind9, /stepca, /dirsrv, /openbao, /kea, /freeradius,
                 /audit; query — dict (view, zone, device, name, slot, msg, err as each page uses them).
        Returns: 200 page (overview, BIND9, Step-CA, directory, OpenBao, Kea, FreeRADIUS with its setup guides for
                 view switches / windows, audit log).
        Fails:   404 for any other path; agent errors from agentclient (ValidationError, AuthError, PermissionDenied,
                 AgentError) propagate to handle_request (400, redirect to /login, 403, 503).
        Feeds:   handle_request.
        """
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
        if path == "/freeradius":
            view = query.get("view", "overview")
            guides = actions.radius_guides() if view in ("switches", "windows") else None
            return self.send(200, views.freeradius(ctx, actions.radius_overview(), query.get("msg", ""),
                                                   query.get("err", ""), view, guides))
        if path == "/audit":
            return self.send(200, views.audit(ctx, actions.read_audit()))
        return self.deny(404, "Not found.")

    def post(self, sess, path, form):
        """Purpose: Route a signed-in, CSRF-checked POST to its action.
        Inputs:  sess — dict from session; path — str; form — dict from read_form. Routes: /logout;
                 /bind9/zone/<key>/add (type, name, ip, target, text, priority, weight, port) and …/delete (type,
                 index, name); /apply; /stepca/…; /openbao/…; /dirsrv/…; /kea/reservations (mac, ip, hostname) and
                 /kea/reservations/<mac>/delete; /freeradius/clients…; /freeradius/people (group, vlan, priority) and
                 /freeradius/people/<group>/delete; /bind9/tsig/….
        Returns: /logout: session dropped, LOGOUT audited, 303 to Keycloak's logout URL clearing the session cookie.
                 Zone records, Kea and FreeRADIUS people: 303 back to the tab with msg or err (err includes the last
                 300 characters of a failed apply). /apply: 200 apply result. The rest: as stepca_post, vault_post,
                 dirsrv_post, radius_post, tsig_post.
        Fails:   404 for an unknown path or operation; ValidationError → 303 with err on the routes handled here; a
                 non-numeric record index raises ValueError (500); agent errors from agentclient (ValidationError,
                 AuthError, PermissionDenied, AgentError) propagate to handle_request (400, redirect to /login, 403,
                 503).
        Feeds:   handle_request.
        """
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
        if path.startswith("/freeradius/clients"):
            return self.radius_post(sess, [urllib.parse.unquote(p) for p in path.split("/")[3:]], form)
        if path.startswith("/freeradius/people"):
            parts = [urllib.parse.unquote(p) for p in path.split("/")[3:]]
            try:
                if not parts:
                    res = actions.map_radius_group(form.get("group", ""), form.get("vlan", ""), form.get("priority", ""))
                    m = res["mapping"]
                    msg = f"Members of {m['group']} may join by password" + (f" on VLAN {m['vlan']}." if m["vlan"] else ".")
                elif len(parts) == 2 and parts[1] == "delete":
                    res = actions.unmap_radius_group(parts[0])
                    msg = f"Members of {parts[0]} may no longer join by password."
                else:
                    return self.deny(404, "Not found.")
                if not res.get("applied"):
                    return self.redirect("/freeradius?" + urllib.parse.urlencode(
                        {"err": msg + " Saved, but applying failed: " + res.get("output", "")[-300:]}))
            except actions.ValidationError as exc:
                return self.redirect("/freeradius?" + urllib.parse.urlencode({"err": str(exc)}))
            return self.redirect("/freeradius?" + urllib.parse.urlencode({"msg": msg}))
        if path.startswith("/bind9/tsig/"):
            return self.tsig_post(sess, urllib.parse.unquote(path[len("/bind9/tsig/"):]), form)
        return self.deny(404, "Not found.")

    def radius_post(self, sess, parts, form):
        """Purpose: RADIUS clients: add, new shared secret, remove — saved and applied at once; a secret is shown once
                 on its own page, never in a URL.
        Inputs:  sess — dict from session; parts — path segments after /freeradius/clients: [] add (form: name,
                 lower-cased; address; message_authenticator '1' to require it; secret, optional), [<name>,
                 'rotate'], [<name>, 'delete']; form — dict from read_form.
        Returns: add / rotate: 200 page with the shared secret, the RADIUS host IP and whether applying worked;
                 delete: 303 to /freeradius with msg, or err if applying failed.
        Fails:   404 for other paths; ValidationError → 303 to /freeradius with err; AgentError, PermissionDenied and
                 AuthError propagate to handle_request.
        Feeds:   post (/freeradius/clients…).
        """
        try:
            if not parts:
                name = form.get("name", "").strip().lower()
                res = actions.add_radius_client(name, form.get("address", ""),
                                                form.get("message_authenticator") == "1", form.get("secret", ""))
                action = "added"
            elif len(parts) == 2 and parts[1] == "rotate":
                name, action = parts[0], "rotated"
                res = actions.rotate_radius_secret(name)
            elif len(parts) == 2 and parts[1] == "delete":
                res = actions.remove_radius_client(parts[0])
                msg = f"RADIUS client {parts[0]} removed."
                if not res.get("applied"):
                    return self.redirect("/freeradius?" + urllib.parse.urlencode(
                        {"err": msg + " Saved, but applying failed: " + res.get("output", "")[-300:]}))
                return self.redirect("/freeradius?" + urllib.parse.urlencode({"msg": msg}))
            else:
                return self.deny(404, "Not found.")
        except actions.ValidationError as exc:
            return self.redirect("/freeradius?" + urllib.parse.urlencode({"err": str(exc)}))
        host_ip = (actions.radius_overview() or {}).get("host_ip", "")
        return self.send(200, views.radius_secret(self.ctx(sess), name, res.get("secret", ""), action, host_ip,
                                                  bool(res.get("applied")), res.get("output", "")))

    def stepca_post(self, sess, op, form):
        """Purpose: Manual PKI: each Step-CA form maps to one fabric-agent operation.
        Inputs:  sess — dict from session; op — str after /stepca/: 'sign/review' (csr_file or csr, device), 'sign'
                 (csr, days, device), 'issue' (cn, sans split on spaces/commas, key_type, days, device), 'inspect'
                 (file or data), 'convert' (cert_file or cert, key_file or key); form — dict from read_form.
        Returns: sign/review: Step-CA sign view with the decoded request; inspect: inspect view with the result;
                 sign, issue, convert: 200 result page with downloads (a private key only on this page, never
                 stored).
        Fails:   404 for an unknown op; ValidationError → the form's view again with status 400 and the error;
                 AgentError, PermissionDenied and AuthError propagate to handle_request.
        Feeds:   post (/stepca/…).
        """
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
        """Purpose: Turn the device edit form into the fields fabric-agent's save_device takes.
        Inputs:  form — dict from read_form: type, owner, description, macs (space or comma separated), enabled (any
                 non-empty value), role_<name> checkboxes.
        Returns: {'type': str, 'owner': str, 'description': str, 'macs': [str], 'enabled': bool, 'roles': [role names
                 checked]}.
        Fails:   never.
        Feeds:   dirsrv_post → agentclient.save_device.
        """
        return {"type": form.get("type", ""), "owner": form.get("owner", ""), "description": form.get("description", ""),
                "macs": [m for m in re.split(r"[\s,]+", form.get("macs", "")) if m],
                "enabled": bool(form.get("enabled")),
                "roles": [k[5:] for k, val in form.items() if k.startswith("role_") and val]}

    @staticmethod
    def role_form(form):
        """Purpose: Turn the role edit form into the fields fabric-agent's save_role takes.
        Inputs:  form — dict from read_form: description, vlan, priority, perm_<permission> checkboxes.
        Returns: {'description': str, 'vlan': str, 'priority': str, 'permissions': [permissions checked]}.
        Fails:   never.
        Feeds:   dirsrv_post → agentclient.save_role.
        """
        return {"description": form.get("description", ""), "vlan": form.get("vlan", ""),
                "priority": form.get("priority", ""),
                "permissions": [k[5:] for k, val in form.items() if k.startswith("perm_") and val]}

    def dirsrv_post(self, sess, parts, form):
        """Purpose: Devices, device roles and people: each form maps to one fabric-agent call.
        Inputs:  sess — dict from session; parts — path segments after /dirsrv/: ['people', '_new'] (form uid, first,
                 last, email), ['people', <uid>, 'reset'], ['devices'|'roles', '_new'] (form name + fields),
                 ['devices'|'roles', <name>] (save), [..., <name>, 'delete'], ['devices', <name>, 'certs', …] (unlink
                 the certificate in form sha256); form — dict from read_form.
        Returns: people: 200 page with the one-time password; devices and roles: 303 to /dirsrv with msg — the new
                 item's page after create, the list after delete, the item's page otherwise.
        Fails:   404 for an unknown kind or operation or a missing name; ValidationError → 303 with err (people list;
                 the list after a failed create; else the item's page); AgentError, PermissionDenied and AuthError
                 propagate to handle_request.
        Feeds:   post (/dirsrv/…).
        Notes:   Only the third path segment is looked at, so any path under …/certs/ unlinks (the page posts to
                 …/certs/unlink).
        """
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
        """Purpose: TSIG keys: create, rotate, delete (Apply publishes them to BIND9).
        Inputs:  sess — dict from session; rest — str after /bind9/tsig/ (unquoted): 'create' (form name, zone,
                 scope, hosts space/comma separated, type_<T> checkboxes, secret — optional existing one),
                 '<name>/rotate', '<name>/delete'; form — dict from read_form.
        Returns: create / rotate: 200 page with the secret and an RFC2136 ini (shown once); delete: 303 to
                 /bind9?view=tsig with msg.
        Fails:   404 for anything else; ValidationError → the TSIG section again with 400 and the error; AgentError,
                 PermissionDenied and AuthError propagate to handle_request.
        Feeds:   post (/bind9/tsig/…).
        """
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
    """Purpose: Start the web UI: load the config, point agentclient at fabric-agent, and serve HTTP on a unix socket
             that only nginx's group can use.
    Inputs:  command line --config <path to webui.json> (required); the config's agent_socket, socket, socket_gid
             (int or group name) and the keys App needs.
    Returns: never returns while serving (serve_forever).
    Fails:   SystemExit from argparse without --config; OSError / json.JSONDecodeError reading the config; KeyError
             for a missing key (also from grp.getgrnam for an unknown group); errors from App; OSError binding the
             socket.
    Feeds:   — (the container's ENTRYPOINT in webui/Dockerfile).
    Notes:   A stale socket is removed first; it is created under umask 0117, then group-owned by nginx's group and
             set to 0660, so only nginx can connect and the forwarded certificate headers cannot be forged.
    """
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
