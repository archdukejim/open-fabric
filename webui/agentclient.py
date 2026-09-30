"""Client for fabric-agent, the privileged host-side API (see agent/server.py).

Exposes the same function names the web UI used when it ran on the host, so
server.py stays unchanged: every operation is a JSON call over the agent's
unix socket, mounted into this container.
"""
import http.client
import json
import socket
import threading
import urllib.parse

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
_socket_path = "/agent/agent.sock"
_local = threading.local()          # the signed-in person's ID token for this request's calls


class ValidationError(ValueError):
    """The agent rejected the input (HTTP 400); message is safe to show."""


class AgentError(RuntimeError):
    """The agent is unreachable or failed."""


class AuthError(RuntimeError):
    """The agent did not accept the sign-in token (expired, ended): sign in again."""


class PermissionDenied(RuntimeError):
    """The signed-in person lacks the permission this needs; message is safe to show."""


def set_token(token):
    """Purpose: Make every later agent call from this thread carry `token`, which fabric-agent verifies and checks
             permissions against.
    Inputs:  token — str Keycloak ID token of the signed-in person, or None/"" to send no Authorization header.
             Stored in the thread-local `_local`, so each request thread has its own.
    Returns: None.
    Fails:   never — it only sets a thread-local attribute.
    Feeds:   _call (reads it); set by webui/server.py Handler.handle_request (None first, then the session's token)
             and Handler.callback (the fresh login token, for the login audit calls).
    """
    _local.token = token


def configure(path):
    """Purpose: Point this client at fabric-agent's unix socket instead of the default /agent/agent.sock.
    Inputs:  path — str filesystem path of the agent socket; sets the module global `_socket_path`.
    Returns: None.
    Fails:   never — the path is not checked here; a wrong path shows up later as AgentError from _call.
    Feeds:   _UnixConnection.connect; called by webui/server.py main() with cfg["agent_socket"].
    """
    global _socket_path
    _socket_path = path


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, timeout):
        """Purpose: An HTTP connection to fabric-agent that runs over the unix socket instead of TCP.
        Inputs:  timeout — seconds allowed for connecting and for each socket read.
        Returns: None.
        Fails:   never — nothing is opened until connect().
        Feeds:   _call (one connection per call).
        Notes:   "fabric-agent" is only the Host header value; no name is resolved.
        """
        super().__init__("fabric-agent", timeout=timeout)

    def connect(self):
        """Purpose: Open the unix stream socket at `_socket_path`; http.client calls it on the first request.
        Inputs:  none (reads self.timeout and the module global `_socket_path`).
        Returns: None; sets self.sock.
        Fails:   OSError (FileNotFoundError, ConnectionRefusedError, PermissionError, socket.timeout) if the socket is
                 missing, the agent is down, or the socket's permissions refuse this uid;
                 _call turns it into AgentError.
        Feeds:   http.client.HTTPConnection.request, used by _call.
        """
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(_socket_path)


def _call(method, path, body=None, timeout=30):
    """Purpose: Send one JSON request to fabric-agent over its unix socket and return the decoded JSON reply.
             Every public function in this module goes through it.
    Inputs:  method — "GET" or "POST"; path — agent path such as "/v1/zones" with names already quoted (_q);
             body — JSON-serialisable object, or None (default) for no body; timeout — seconds, default 30
             (long operations pass more). Sends the thread's token from set_token as Authorization: Bearer.
    Returns: the decoded JSON body of a 200 reply (dict or list; None for an empty body).
    Fails:   AgentError — the socket is missing/refused/timed out (OSError), the reply is not JSON (ValueError),
               or any status other than 200/400/401/403 (e.g. 404 unknown route, 500 agent internal error);
             ValidationError — 400: fabriclib rejected the input; message is the agent's "error", safe to show;
             AuthError — 401: the agent did not accept the ID token (missing, expired, not valid);
             PermissionDenied — 403: the token lacks the permission the route needs
               (fabriclib/rbac/required_permission.py), the route is not in that table, or the peer uid is refused;
             TypeError from json.dumps if `body` is not JSON-serialisable (not wrapped).
    Feeds:   every public function in this module.
    Notes:   webui/server.py Handler.handle_request maps these to: 400 page, redirect to /login, 403 page, 503 page.
    """
    conn = _UnixConnection(timeout)
    try:
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if getattr(_local, "token", None):
            headers["Authorization"] = f"Bearer {_local.token}"
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"null")
    except (OSError, ValueError) as exc:
        raise AgentError(f"fabric-agent unavailable: {exc}") from exc
    finally:
        conn.close()
    if resp.status == 400:
        raise ValidationError((data or {}).get("error", "rejected"))
    if resp.status == 401:
        raise AuthError((data or {}).get("error", "not signed in"))
    if resp.status == 403:
        raise PermissionDenied((data or {}).get("error", "not allowed"))
    if resp.status != 200:
        raise AgentError(f"fabric-agent error {resp.status}: {(data or {}).get('error', '')}")
    return data


def _q(s):
    """Purpose: URL-quote one path segment with nothing kept safe ("/" becomes %2F), so a name cannot change the route.
    Inputs:  s — any value; converted with str().
    Returns: the quoted str.
    Fails:   never.
    Feeds:   every function here that puts a zone, key, slot, device, role, MAC, group, client or uid in the path.
    """
    return urllib.parse.quote(str(s), safe="")


def version_info():
    """Purpose: The fabric version and build shown in every page's header.
             Agent route: GET /v1/version (permission: session).
    Inputs:  none.
    Returns: {"version": str, "build": str} (fabriclib.system.version_info).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.ctx (every page).
    """
    return _call("GET", "/v1/version")


def service_status():
    """Purpose: The state of every fabric service, for the overview page.
             Agent route: GET /v1/services (status:read).
    Inputs:  none.
    Returns: list of tuples (service, systemd state, container health — "" for host services); the agent's
             JSON lists are turned back into tuples.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.get for "/" (views.overview).
    """
    return [tuple(x) for x in _call("GET", "/v1/services")]


def list_zones():
    """Purpose: The DNS zones for the BIND page's zone list.
             Agent route: GET /v1/zones (dns:read).
    Inputs:  none.
    Returns: [{"key": str, "name": str, "records": int, "reverse": bool}] (fabriclib.dns.list_zones).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.bind9_page.
    """
    return _call("GET", "/v1/zones")


def zone_detail(key):
    """Purpose: One zone's records and BIND sync status, for the forward-zone view.
             Agent route: GET /v1/zones/<key> (dns:read).
    Inputs:  key — str zone key from list_zones (quoted into the path).
    Returns: {"key", "name", "records": [record dicts with display values and PTR info], "status": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown zone key.
    Feeds:   webui/server.py Handler.bind9_page.
    """
    return _call("GET", f"/v1/zones/{_q(key)}")


def read_audit(limit=200):
    """Purpose: Recent audit-log lines for the Audit page.
             Agent route: GET /v1/audit (audit:read).
    Inputs:  limit — int, default 200; the client keeps only the first `limit` lines (the agent already sends at
             most 200).
    Returns: list of str log lines, newest first.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.get for "/audit".
    """
    return _call("GET", "/v1/audit")[:limit]


def add_record(actor, key, rtype, form):
    """Purpose: Add one DNS record to a zone in vars.yaml (published by the next apply).
             Agent route: POST /v1/zones/<key>/records (dns:write).
    Inputs:  actor — str user name (the agent uses the token's user instead for the web UI); key — zone key;
             rtype — one of RECORD_TYPES; form — mapping; only name, ip, target, text, priority, weight and
             port are sent ("" when absent).
    Returns: the added record as a dict (fabriclib.dns.add_record); the caller reads its "name".
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a bad type, name or value.
    Feeds:   webui/server.py Handler.post for /bind9/zone/<key>/add.
    """
    fields = {k: form.get(k, "") for k in ("name", "ip", "target", "text", "priority", "weight", "port")}
    return _call("POST", f"/v1/zones/{_q(key)}/records", {"actor": actor, "type": rtype, **fields})


def delete_record(actor, key, rtype, index, expected_name):
    """Purpose: Remove one DNS record from a zone, only if it is still the record the page showed.
             Agent route: POST /v1/zones/<key>/records/delete (dns:write).
    Inputs:  actor — str user name (ignored by the agent for token callers); key — zone key; rtype — record type;
             index — int position among that type's records; expected_name — the name the page showed.
    Returns: the removed record (fabriclib.dns.remove_record).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if the index is out of range or the name no longer matches.
    Feeds:   webui/server.py Handler.post for /bind9/zone/<key>/delete (result unused).
    """
    return _call("POST", f"/v1/zones/{_q(key)}/records/delete",
                 {"actor": actor, "type": rtype, "index": index, "name": expected_name})


def apply_changes(actor):
    """Purpose: Render and apply the configuration (as `fabricctl --apply`) on the host.
             Agent route: POST /v1/apply (dns:write), timeout 960 s.
    Inputs:  actor — str user name (ignored by the agent for token callers).
    Returns: (ok: bool, output: str) — whether the apply succeeded and its log output.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             a failed apply is ok=False, not an exception.
    Feeds:   webui/server.py Handler.post for "/apply" (views.apply_result).
    """
    result = _call("POST", "/v1/apply", {"actor": actor}, timeout=960)
    return result["ok"], result["output"]


def ca_summary():
    """Purpose: The CA certificates, where devices fetch them, and the signing limits, for the Step-CA page.
             Agent route: GET /v1/pki/ca (pki:read).
    Inputs:  none.
    Returns: dict from fabriclib.pki.ca_summary: {"domain", "certs_url", "max_days", "root": {...},
             "intermediate": {...}}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.stepca_page (catches AgentError/ValidationError and shows no CA).
    """
    return _call("GET", "/v1/pki/ca")


def list_issued():
    """Purpose: Certificates issued by hand, for the Step-CA 'issued' view.
             Agent route: GET /v1/pki/issued (pki:read).
    Inputs:  none.
    Returns: list of {"when", "actor", "kind", "subject", "sans", "not_after", "status"}, newest first.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.stepca_page (view "issued").
    """
    return _call("GET", "/v1/pki/issued")


def describe_csr(actor, csr):
    """Purpose: Decode an uploaded CSR and judge it before signing (the review step).
             Agent route: POST /v1/pki/describe-csr (pki:read).
    Inputs:  actor — str user name (not used by the agent for this route); csr — str PEM, DER-as-text or base64.
    Returns: dict from fabriclib.pki.describe_csr: {"pem", "subject", "cn", "sans", "key", "ca_requested",
             "problems", "text", ...}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if it is not a readable CSR.
    Feeds:   webui/server.py Handler.stepca_post for "sign/review".
    """
    return _call("POST", "/v1/pki/describe-csr", {"actor": actor, "csr": csr})


def sign_csr(actor, csr, days, device=""):
    """Purpose: Sign a device's CSR with the fabric CA.
             Agent route: POST /v1/pki/sign (pki:sign), timeout 120 s.
    Inputs:  actor — str user name; csr — str PEM; days — validity as typed in the form (the agent validates it
             against the CA limit); device — optional device name to link the certificate to, default "".
    Returns: dict from fabriclib.pki.sign_csr: {"name", "cert", "chain", "fullchain", ..., "info", "device"}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a bad CSR, days or device.
    Feeds:   webui/server.py Handler.stepca_post for "sign" (views.pki_result).
    """
    return _call("POST", "/v1/pki/sign", {"actor": actor, "csr": csr, "days": days, "device": device}, timeout=120)


def issue_key_pair(actor, cn, sans, key_type, days, device=""):
    """Purpose: Generate a private key and certificate for a device that cannot make its own CSR.
             Agent route: POST /v1/pki/issue (pki:issue), timeout 180 s.
    Inputs:  actor — str user name; cn — common name; sans — list of str names/IPs; key_type — e.g. "RSA-2048";
             days — validity as typed; device — optional device name to link, default "".
    Returns: dict from fabriclib.pki.issue_key_pair: cert fields plus "key", "p12_b64" and "p12_password"
             (the key is returned this once).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad names, key type or days.
    Feeds:   webui/server.py Handler.stepca_post for "issue" (views.pki_result).
    """
    return _call("POST", "/v1/pki/issue", {"actor": actor, "cn": cn, "sans": sans, "key_type": key_type,
                                           "days": days, "device": device}, timeout=180)


def inspect_pem(actor, data):
    """Purpose: Decode certificates or a CSR for reading, with a trust verdict.
             Agent route: POST /v1/pki/inspect (pki:read).
    Inputs:  actor — str user name (not used by the agent for this route); data — str PEM chain, DER-as-text
             or base64.
    Returns: {"kind": "cert" | "csr", "items": [{"info", "text", "trusted", ...}]}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if nothing can be decoded.
    Feeds:   webui/server.py Handler.stepca_post for "inspect".
    """
    return _call("POST", "/v1/pki/inspect", {"actor": actor, "data": data})


def convert_cert(actor, cert, key):
    """Purpose: Re-package a certificate (and optional key) into other formats.
             Agent route: POST /v1/pki/convert (pki:issue).
    Inputs:  actor — str user name; cert — str certificate data; key — str private key PEM, or "" for none.
    Returns: dict from fabriclib.pki.convert_cert: {"name", "cert", "fullchain", "der_b64", "p7b_b64", "p12_b64",
             "p12_password", "info"}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for unreadable input or a key that does not match.
    Feeds:   webui/server.py Handler.stepca_post for "convert" (views.pki_result).
    """
    return _call("POST", "/v1/pki/convert", {"actor": actor, "cert": cert, "key": key})


def reverse_zones():
    """Purpose: The reverse (PTR) zones apply generates from the A/AAAA records.
             Agent route: GET /v1/reverse-zones (dns:read).
    Inputs:  none.
    Returns: {"zones": {zone name: records}, "skipped": [addresses left out and why]}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.bind9_page (view "reverse").
    """
    return _call("GET", "/v1/reverse-zones")


def list_tsig_keys():
    """Purpose: The TSIG keys and their update rights (never their secrets).
             Agent route: GET /v1/tsig (dns:read).
    Inputs:  none.
    Returns: list of {"name", "algorithm", "types", "scope", "acls"}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.bind9_page (view "tsig").
    """
    return _call("GET", "/v1/tsig")


def create_tsig_key(actor, name, zone, scope, hosts, types, secret):
    """Purpose: Create a TSIG key allowed to update part of a zone (published by the next apply).
             Agent route: POST /v1/tsig (tsig:manage).
    Inputs:  actor — str user name; name — key name; zone — zone name; scope — str scope choice from the form;
             hosts — list of str host names; types — list of record types; secret — str, "" to generate one.
    Returns: {"key": key dict, "secret": str, "ini": str certbot RFC2136 credentials} — the secret is shown once.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a bad or duplicate name, zone, scope, host or type.
    Feeds:   webui/server.py Handler.tsig_post (create -> views.tsig_result).
    """
    return _call("POST", "/v1/tsig", {"actor": actor, "name": name, "zone": zone, "scope": scope,
                                      "hosts": hosts, "types": types, "secret": secret})


def rotate_tsig_key(actor, name):
    """Purpose: Give a TSIG key a new secret.
             Agent route: POST /v1/tsig/<name>/rotate (tsig:manage).
    Inputs:  actor — str user name; name — existing key name.
    Returns: {"secret": str, "ini": str} — shown once.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown key.
    Feeds:   webui/server.py Handler.tsig_post (rotate -> views.tsig_result).
    """
    return _call("POST", f"/v1/tsig/{_q(name)}/rotate", {"actor": actor})


def delete_tsig_key(actor, name):
    """Purpose: Remove a TSIG key (published by the next apply).
             Agent route: POST /v1/tsig/<name>/delete (tsig:manage).
    Inputs:  actor — str user name; name — existing key name.
    Returns: {} (empty dict).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown key.
    Feeds:   webui/server.py Handler.tsig_post (result unused).
    """
    return _call("POST", f"/v1/tsig/{_q(name)}/delete", {"actor": actor})


def vault_status():
    """Purpose: OpenBao at a glance for the OpenBao page; never secrets.
             Agent route: GET /v1/vault (vault:status).
    Inputs:  none.
    Returns: dict from fabriclib.vault.vault_status: {"url", "reachable", "initialized", "sealed", "key", "mounts",
             "auth", ...}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.openbao_page.
    """
    return _call("GET", "/v1/vault")


def vault_slots():
    """Purpose: The vault's unlock methods and this host's name (typed to confirm changes).
             Agent route: GET /v1/vault/slots (vault:status).
    Inputs:  none.
    Returns: {"slots": [slot dicts], "host": str hostname from vars.yaml}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.openbao_page and Handler.vault_post (the host-name confirmation).
    """
    return _call("GET", "/v1/vault/slots")


def vault_slot_action(actor, slot_id, op):
    """Purpose: Test or remove one unlock method.
             Agent route: POST /v1/vault/slots/<id>/<op> (vault:unlock), timeout 120 s.
    Inputs:  actor — str user name; slot_id — slot id (quoted); op — "test" or "remove", put in the path unquoted
             (the caller only passes those two).
    Returns: {"ok": bool}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError when fabriclib refuses (e.g. the test fails, the last method); another op is
             not in the route table -> PermissionDenied.
    Feeds:   webui/server.py Handler.vault_post.
    """
    return _call("POST", f"/v1/vault/slots/{_q(slot_id)}/{op}", {"actor": actor}, timeout=120)


def vault_add_usb(actor, disk, label):
    """Purpose: Add a USB stick as an unlock method.
             Agent route: POST /v1/vault/slots/add-usb (vault:unlock), timeout 180 s.
    Inputs:  actor — str user name; disk — device path chosen from vault_devices; label — str name for it.
    Returns: {"id": str new slot id}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown disk or a failed write/read-back.
    Feeds:   webui/server.py Handler.vault_post (add-usb).
    """
    return _call("POST", "/v1/vault/slots/add-usb", {"actor": actor, "disk": disk, "label": label}, timeout=180)


def vault_rotate(actor):
    """Purpose: Make a new vault key and give it to every unlock method whose device is present.
             Agent route: POST /v1/vault/rotate (vault:unlock), timeout 900 s.
    Inputs:  actor — str user name.
    Returns: {"key_id": str, "kept": [slot ids], "dropped": [slot ids removed because their device was absent]}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.vault_post (rotate).
    """
    return _call("POST", "/v1/vault/rotate", {"actor": actor}, timeout=900)


def vault_add_security_key(actor, module, token, pin, key_id, label):
    """Purpose: Add a PKCS#11 security key (e.g. a YubiKey) as an unlock method.
             Agent route: POST /v1/vault/slots/add-security-key (vault:unlock), timeout 120 s.
    Inputs:  actor — str user name; module — PKCS#11 module path; token — token serial; pin — the token PIN;
             key_id — an existing key id on the token, or "new"; label — str name for it.
    Returns: {"id": str new slot id}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a wrong PIN, token or key.
    Feeds:   webui/server.py Handler.vault_post (add-security-key).
    Notes:   The PIN travels only in this request body over the agent socket.
    """
    return _call("POST", "/v1/vault/slots/add-security-key", {"actor": actor, "module": module, "token": token,
                                                              "pin": pin, "key_id": key_id, "label": label}, timeout=120)


def vault_add_kmip(endpoint, key_id, ca_pem, cert_pem, key_pem, server_name, label):
    """Purpose: Add a KMIP HSM/KMS as an unlock method.
             Agent route: POST /v1/vault/slots/add-hsm (vault:unlock), timeout 120 s.
    Inputs:  endpoint — host:port; key_id — key on the device; ca_pem, cert_pem, key_pem — str PEM CA, client cert
             and client key; server_name — TLS name to verify; label — str name. No actor is sent: the agent
             takes the user from the token.
    Returns: {"id": str new slot id}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if the device cannot be reached or the wrap fails.
    Feeds:   webui/server.py Handler.vault_post (add-hsm).
    Notes:   The client key travels only in this request body over the agent socket.
    """
    return _call("POST", "/v1/vault/slots/add-hsm",
                 {"endpoint": endpoint, "key_id": key_id, "ca": ca_pem, "cert": cert_pem, "key": key_pem,
                  "server_name": server_name, "label": label}, timeout=120)


def vault_devices():
    """Purpose: Unlock-capable devices plugged into the host, for the add-method forms.
             Agent route: GET /v1/vault/devices (vault:status).
    Inputs:  none.
    Returns: {"tokens": [...], "disks": [...], "pkcs11": [...]} (fabriclib.vault.detect_devices).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.openbao_page (views "add-security-key" and "add-usb").
    """
    return _call("GET", "/v1/vault/devices")


def device_overview():
    """Purpose: Devices, roles and the RBAC vocabulary from one directory read.
             Agent route: GET /v1/devices (devices:read).
    Inputs:  none.
    Returns: {"devices": [...], "roles": [...], "types": [...], "permissions": {...}}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.dirsrv_page and Handler.stepca_page (device picker; errors ignored there).
    """
    return _call("GET", "/v1/devices")


def list_people():
    """Purpose: People and their groups (read-only; managed in Keycloak).
             Agent route: GET /v1/people (people:read).
    Inputs:  none.
    Returns: dict from fabriclib.ldap.list_people, e.g. {"users": [...], "groups": [...], "keycloak_url": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.dirsrv_page (view "people").
    """
    return _call("GET", "/v1/people")


def save_device(actor, name, fields, new=False):
    """Purpose: Create a device, or replace an existing device's fields.
             Agent route: POST /v1/devices (devices:enroll) when new, else POST /v1/devices/<name> (devices:admin).
    Inputs:  actor — str user name; name — device name; fields — dict from Handler.device_form (type, owner,
             description, macs, enabled, roles); new — bool, default False.
    Returns: new: {"name": str created name}; edit: fabriclib.ldap.update_device's result, or {} if it returns none.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad fields, a duplicate or unknown device.
    Feeds:   webui/server.py Handler.dirsrv_post (devices).
    """
    if new:
        return _call("POST", "/v1/devices", {"actor": actor, "name": name, "fields": fields})
    return _call("POST", f"/v1/devices/{_q(name)}", {"actor": actor, "fields": fields})


def delete_device(actor, name):
    """Purpose: Delete a device and take it out of every role.
             Agent route: POST /v1/devices/<name>/delete (devices:admin).
    Inputs:  actor — str user name; name — device name.
    Returns: fabriclib's result, or {} (unused).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown device.
    Feeds:   webui/server.py Handler.dirsrv_post (devices, delete).
    """
    return _call("POST", f"/v1/devices/{_q(name)}/delete", {"actor": actor})


def link_device_cert(actor, name, sha256, link=True):
    """Purpose: Record or forget a certificate fingerprint on a device.
             Agent route: POST /v1/devices/<name>/certs (pki:link-device).
    Inputs:  actor — str user name; name — device name; sha256 — certificate fingerprint; link — bool, True to
             record, False to forget (default True).
    Returns: fabriclib.ldap.link_device_cert's result, or {} (unused).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown device or bad fingerprint.
    Feeds:   webui/server.py Handler.dirsrv_post (devices, certs — always link=False).
    """
    return _call("POST", f"/v1/devices/{_q(name)}/certs", {"actor": actor, "sha256": sha256, "link": link})


def save_role(actor, name, fields, new=False):
    """Purpose: Create a device role, or replace an existing role's fields.
             Agent route: POST /v1/roles when new, else POST /v1/roles/<name> (roles:admin).
    Inputs:  actor — str user name; name — role name; fields — dict from Handler.role_form (description, vlan,
             priority, permissions); new — bool, default False.
    Returns: new: {"name": str created name}; edit: fabriclib.ldap.update_role's result, or {}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad fields, a duplicate or unknown role.
    Feeds:   webui/server.py Handler.dirsrv_post (roles).
    """
    if new:
        return _call("POST", "/v1/roles", {"actor": actor, "name": name, "fields": fields})
    return _call("POST", f"/v1/roles/{_q(name)}", {"actor": actor, "fields": fields})


def delete_role(actor, name):
    """Purpose: Delete a device role.
             Agent route: POST /v1/roles/<name>/delete (roles:admin).
    Inputs:  actor — str user name; name — role name.
    Returns: fabriclib's result, or {} (unused).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an invalid role name or a role that still has devices.
    Feeds:   webui/server.py Handler.dirsrv_post (roles, delete).
    """
    return _call("POST", f"/v1/roles/{_q(name)}/delete", {"actor": actor})


def dhcp_overview():
    """Purpose: What the Kea (DHCP) page shows, read-only.
             Agent route: GET /v1/dhcp (dhcp:read).
    Inputs:  none.
    Returns: {"enabled", "interfaces", "lease_time", "ddns_zone", "subnets": [...], "leases": [...],
             "leases_error"} (fabriclib.dhcp.dhcp_overview).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.get for "/kea".
    """
    return _call("GET", "/v1/dhcp")


def add_reservation(mac, ip, hostname):
    """Purpose: Reserve an IP for a MAC; the agent saves it and applies at once (Kea reloads with it).
             Agent route: POST /v1/dhcp/reservations (dhcp:write), timeout 300 s.
    Inputs:  mac, ip, hostname — str as typed; validated by fabriclib. No actor: the agent uses the token's user.
    Returns: {"reservation": saved dict with "mac" and "ip", "applied": bool, "output": last 2000 chars of apply}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad values; a failed apply is applied=False (saved anyway).
    Feeds:   webui/server.py Handler.post for /kea/reservations.
    """
    return _call("POST", "/v1/dhcp/reservations", {"mac": mac, "ip": ip, "hostname": hostname}, timeout=300)


def remove_reservation(mac):
    """Purpose: Remove a DHCP reservation and apply at once.
             Agent route: POST /v1/dhcp/reservations/<mac>/delete (dhcp:write), timeout 300 s.
    Inputs:  mac — str MAC of the reservation (quoted).
    Returns: {"applied": bool, "output": str last 2000 chars of apply}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown MAC.
    Feeds:   webui/server.py Handler.post for /kea/reservations/<mac>/delete.
    """
    return _call("POST", f"/v1/dhcp/reservations/{_q(mac)}/delete", {}, timeout=300)


def radius_overview():
    """Purpose: What the FreeRADIUS page shows: on/off, clients, password groups, recent decisions.
             Agent route: GET /v1/radius (radius:read).
    Inputs:  none.
    Returns: {"enabled", "server_name", "host_ip", "clients", "people", "log", "log_error"}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.get for "/freeradius" and Handler.radius_post (host_ip).
    """
    return _call("GET", "/v1/radius")


def add_radius_client(name, address, message_authenticator=True, secret=""):
    """Purpose: Add a RADIUS client (switch or access point); saved and applied at once.
             Agent route: POST /v1/radius/clients (radius:admin), timeout 300 s.
    Inputs:  name — client name; address — IP/network; message_authenticator — bool, default True; secret — str,
             "" (default) for the agent to generate one.
    Returns: {"secret": str shown once, "applied": bool, "output": str last 2000 chars of apply}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad or duplicate values; a failed apply is applied=False.
    Feeds:   webui/server.py Handler.radius_post (add -> views.radius_secret).
    """
    return _call("POST", "/v1/radius/clients", {"name": name, "address": address, "secret": secret,
                                                "message_authenticator": message_authenticator}, timeout=300)


def rotate_radius_secret(name, secret=""):
    """Purpose: Give a RADIUS client a new shared secret; saved and applied at once.
             Agent route: POST /v1/radius/clients/<name>/rotate (radius:admin), timeout 300 s.
    Inputs:  name — client name; secret — str, "" (default) for the agent to generate one.
    Returns: {"secret": str shown once, "applied": bool, "output": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown client.
    Feeds:   webui/server.py Handler.radius_post (rotate; never passes a secret).
    """
    return _call("POST", f"/v1/radius/clients/{_q(name)}/rotate", {"secret": secret}, timeout=300)


def radius_guides():
    """Purpose: The FreeRADIUS setup guides and Windows scripts, filled in for this host (public data only).
             Agent route: GET /v1/radius/guides (radius:read).
    Inputs:  none.
    Returns: dict from fabriclib.radius.radius_guides: {"host_ip", "server_name", "people", "windows": {"tls"|"ttls":
             {"filename", "script"}}, ...}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
    Feeds:   webui/server.py Handler.get for "/freeradius" (views "switches" and "windows").
    """
    return _call("GET", "/v1/radius/guides")


def map_radius_group(group, vlan="", priority=""):
    """Purpose: Let members of a directory group join the network by password; saved and applied at once.
             Agent route: POST /v1/radius/people (radius:admin), timeout 300 s.
    Inputs:  group — group name; vlan — str VLAN, "" for none; priority — str, "" for the agent's default 100.
    Returns: {"mapping": {"group", "vlan", ...}, "applied": bool, "output": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown group or bad VLAN/priority.
    Feeds:   webui/server.py Handler.post for /freeradius/people.
    """
    return _call("POST", "/v1/radius/people", {"group": group, "vlan": vlan, "priority": priority}, timeout=300)


def unmap_radius_group(group):
    """Purpose: Stop a group's members joining by password; saved and applied at once.
             Agent route: POST /v1/radius/people/<group>/delete (radius:admin), timeout 300 s.
    Inputs:  group — group name (quoted).
    Returns: {"applied": bool, "output": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a group that is not mapped.
    Feeds:   webui/server.py Handler.post for /freeradius/people/<group>/delete.
    """
    return _call("POST", f"/v1/radius/people/{_q(group)}/delete", {}, timeout=300)


def remove_radius_client(name):
    """Purpose: Remove a RADIUS client; saved and applied at once.
             Agent route: POST /v1/radius/clients/<name>/delete (radius:admin), timeout 300 s.
    Inputs:  name — client name (quoted).
    Returns: {"secret": None, "applied": bool, "output": str}.
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown client.
    Feeds:   webui/server.py Handler.radius_post (delete).
    """
    return _call("POST", f"/v1/radius/clients/{_q(name)}/delete", {}, timeout=300)


def create_person(uid, first, last, email):
    """Purpose: Create a person in Keycloak with a one-time password.
             Agent route: POST /v1/people (people:create).
    Inputs:  uid — user name; first, last — names; email — address. No actor: the agent uses the token's user.
    Returns: str one-time password (shown once, stored nowhere).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad or duplicate values; KeyError if a 200 reply had no "password".
    Feeds:   webui/server.py Handler.dirsrv_post (people/_new -> views.person_result).
    """
    return _call("POST", "/v1/people", {"uid": uid, "first": first, "last": last, "email": email})["password"]


def reset_sign_in(uid):
    """Purpose: Reset a person's sign-in: new one-time password, TOTP removed, sessions ended.
             Agent route: POST /v1/people/<uid>/reset (people:reset).
    Inputs:  uid — user name (quoted).
    Returns: str new one-time password (shown once).
    Fails:   the _call exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for an unknown user, or a fabric-group member when the caller lacks
             system:admin; KeyError if a 200 reply had no "password".
    Feeds:   webui/server.py Handler.dirsrv_post (people/<uid>/reset -> views.person_result).
    """
    return _call("POST", f"/v1/people/{_q(uid)}/reset", {})["password"]


def audit(actor, action, detail):
    """Purpose: Write a login event to the audit log, best effort so an agent outage never blocks a denial.
             Agent route: POST /v1/events (session).
    Inputs:  actor — str user name, or None/"" (sent as "unknown"); action — "LOGIN", "LOGOUT" or "LOGIN_DENIED"
             (the agent refuses others with 400); detail — str (the agent keeps 200 chars).
    Returns: None.
    Fails:   AgentError and ValidationError are swallowed; AuthError (401) and PermissionDenied (403) are not caught
             and propagate to Handler.handle_request (redirect to /login, or a 403 page).
    Feeds:   — (result unused); called by webui/server.py Handler.callback (LOGIN, LOGIN_DENIED) and Handler.post
             for /logout (LOGOUT).
    """
    try:
        _call("POST", "/v1/events", {"actor": actor or "unknown", "action": action, "detail": detail})
    except (AgentError, ValidationError):
        pass
