"""Client for fabric-agent, the privileged host-side API (see agent/server.py).

Exposes the same function names the web UI used when it ran on the host, so
server.py stays unchanged: every operation is a JSON call over the agent's
unix socket, mounted into this container.
"""
import http.client
import json
import socket
import urllib.parse

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
_socket_path = "/agent/agent.sock"


class ValidationError(ValueError):
    """The agent rejected the input (HTTP 400); message is safe to show."""


class AgentError(RuntimeError):
    """The agent is unreachable or failed."""


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
        conn.request(method, path, body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"null")
    except (OSError, ValueError) as exc:
        raise AgentError(f"fabric-agent unavailable: {exc}") from exc
    finally:
        conn.close()
    if resp.status == 400:
        raise ValidationError((data or {}).get("error", "rejected"))
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


def audit(actor, action, detail):
    """Login events; best effort so an agent outage never blocks a denial."""
    try:
        _call("POST", "/v1/events", {"actor": actor or "unknown", "action": action, "detail": detail})
    except (AgentError, ValidationError):
        pass
