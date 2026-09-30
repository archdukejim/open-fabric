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
    """Every call from this thread carries `token` (fabric-agent checks it)."""
    _local.token = token


def configure(path):
    global _socket_path
    _socket_path = path


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, timeout):
        super().__init__("fabric-agent", timeout=timeout)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(_socket_path)


def _call(method, path, body=None, timeout=30):
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
    return urllib.parse.quote(str(s), safe="")


def version_info():
    return _call("GET", "/v1/version")


def service_status():
    return [tuple(x) for x in _call("GET", "/v1/services")]


def list_zones():
    return _call("GET", "/v1/zones")


def zone_detail(key):
    return _call("GET", f"/v1/zones/{_q(key)}")


def read_audit(limit=200):
    return _call("GET", "/v1/audit")[:limit]


def add_record(actor, key, rtype, form):
    fields = {k: form.get(k, "") for k in ("name", "ip", "target", "text", "priority", "weight", "port")}
    return _call("POST", f"/v1/zones/{_q(key)}/records", {"actor": actor, "type": rtype, **fields})


def delete_record(actor, key, rtype, index, expected_name):
    return _call("POST", f"/v1/zones/{_q(key)}/records/delete",
                 {"actor": actor, "type": rtype, "index": index, "name": expected_name})


def apply_changes(actor):
    result = _call("POST", "/v1/apply", {"actor": actor}, timeout=960)
    return result["ok"], result["output"]


def ca_summary():
    return _call("GET", "/v1/pki/ca")


def list_issued():
    return _call("GET", "/v1/pki/issued")


def describe_csr(actor, csr):
    return _call("POST", "/v1/pki/describe-csr", {"actor": actor, "csr": csr})


def sign_csr(actor, csr, days, device=""):
    return _call("POST", "/v1/pki/sign", {"actor": actor, "csr": csr, "days": days, "device": device}, timeout=120)


def issue_key_pair(actor, cn, sans, key_type, days, device=""):
    return _call("POST", "/v1/pki/issue", {"actor": actor, "cn": cn, "sans": sans, "key_type": key_type,
                                           "days": days, "device": device}, timeout=180)


def inspect_pem(actor, data):
    return _call("POST", "/v1/pki/inspect", {"actor": actor, "data": data})


def convert_cert(actor, cert, key):
    return _call("POST", "/v1/pki/convert", {"actor": actor, "cert": cert, "key": key})


def reverse_zones():
    return _call("GET", "/v1/reverse-zones")


def list_tsig_keys():
    return _call("GET", "/v1/tsig")


def create_tsig_key(actor, name, zone, scope, hosts, types, secret):
    return _call("POST", "/v1/tsig", {"actor": actor, "name": name, "zone": zone, "scope": scope,
                                      "hosts": hosts, "types": types, "secret": secret})


def rotate_tsig_key(actor, name):
    return _call("POST", f"/v1/tsig/{_q(name)}/rotate", {"actor": actor})


def delete_tsig_key(actor, name):
    return _call("POST", f"/v1/tsig/{_q(name)}/delete", {"actor": actor})


def vault_status():
    return _call("GET", "/v1/vault")


def vault_slots():
    return _call("GET", "/v1/vault/slots")


def vault_slot_action(actor, slot_id, op):
    return _call("POST", f"/v1/vault/slots/{_q(slot_id)}/{op}", {"actor": actor}, timeout=120)


def vault_add_usb(actor, disk, label):
    return _call("POST", "/v1/vault/slots/add-usb", {"actor": actor, "disk": disk, "label": label}, timeout=180)


def vault_rotate(actor):
    return _call("POST", "/v1/vault/rotate", {"actor": actor}, timeout=900)


def vault_add_security_key(actor, module, token, pin, key_id, label):
    """The PIN travels only in this request body over the agent socket."""
    return _call("POST", "/v1/vault/slots/add-security-key", {"actor": actor, "module": module, "token": token,
                                                              "pin": pin, "key_id": key_id, "label": label}, timeout=120)


def vault_add_kmip(endpoint, key_id, ca_pem, cert_pem, key_pem, server_name, label):
    """The client key travels only in this request body over the agent socket."""
    return _call("POST", "/v1/vault/slots/add-hsm",
                 {"endpoint": endpoint, "key_id": key_id, "ca": ca_pem, "cert": cert_pem, "key": key_pem,
                  "server_name": server_name, "label": label}, timeout=120)


def vault_devices():
    return _call("GET", "/v1/vault/devices")


def device_overview():
    return _call("GET", "/v1/devices")


def list_people():
    return _call("GET", "/v1/people")


def save_device(actor, name, fields, new=False):
    if new:
        return _call("POST", "/v1/devices", {"actor": actor, "name": name, "fields": fields})
    return _call("POST", f"/v1/devices/{_q(name)}", {"actor": actor, "fields": fields})


def delete_device(actor, name):
    return _call("POST", f"/v1/devices/{_q(name)}/delete", {"actor": actor})


def link_device_cert(actor, name, sha256, link=True):
    return _call("POST", f"/v1/devices/{_q(name)}/certs", {"actor": actor, "sha256": sha256, "link": link})


def save_role(actor, name, fields, new=False):
    if new:
        return _call("POST", "/v1/roles", {"actor": actor, "name": name, "fields": fields})
    return _call("POST", f"/v1/roles/{_q(name)}", {"actor": actor, "fields": fields})


def delete_role(actor, name):
    return _call("POST", f"/v1/roles/{_q(name)}/delete", {"actor": actor})


def dhcp_overview():
    return _call("GET", "/v1/dhcp")


def add_reservation(mac, ip, hostname):
    """Saved and applied at once (Kea reloads with it)."""
    return _call("POST", "/v1/dhcp/reservations", {"mac": mac, "ip": ip, "hostname": hostname}, timeout=300)


def remove_reservation(mac):
    return _call("POST", f"/v1/dhcp/reservations/{_q(mac)}/delete", {}, timeout=300)


def radius_overview():
    return _call("GET", "/v1/radius")


def add_radius_client(name, address, message_authenticator=True, secret=""):
    """Saved and applied at once; the secret comes back once."""
    return _call("POST", "/v1/radius/clients", {"name": name, "address": address, "secret": secret,
                                                "message_authenticator": message_authenticator}, timeout=300)


def rotate_radius_secret(name, secret=""):
    return _call("POST", f"/v1/radius/clients/{_q(name)}/rotate", {"secret": secret}, timeout=300)


def radius_guides():
    return _call("GET", "/v1/radius/guides")


def map_radius_group(group, vlan="", priority=""):
    return _call("POST", "/v1/radius/people", {"group": group, "vlan": vlan, "priority": priority}, timeout=300)


def unmap_radius_group(group):
    return _call("POST", f"/v1/radius/people/{_q(group)}/delete", {}, timeout=300)


def remove_radius_client(name):
    return _call("POST", f"/v1/radius/clients/{_q(name)}/delete", {}, timeout=300)


def create_person(uid, first, last, email):
    """Returns the one-time password (shown once)."""
    return _call("POST", "/v1/people", {"uid": uid, "first": first, "last": last, "email": email})["password"]


def reset_sign_in(uid):
    """Returns the new one-time password (shown once)."""
    return _call("POST", f"/v1/people/{_q(uid)}/reset", {})["password"]


def audit(actor, action, detail):
    """Login events; best effort so an agent outage never blocks a denial."""
    try:
        _call("POST", "/v1/events", {"actor": actor or "unknown", "action": action, "detail": detail})
    except (AgentError, ValidationError):
        pass
