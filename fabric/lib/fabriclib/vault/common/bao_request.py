import http.client
import json
import os
import socket
import ssl

from fabriclib.common.errors import ValidationError


def bao_request(v, method, path, token=None, body=None, timeout=15):
    """Call the OpenBao API (/v1/<path>) on its fabric_net address, TLS
    verified against the fabric root CA for its host name. Returns
    (status, parsed JSON or {}). Raises ValidationError if OpenBao cannot
    be reached."""
    root_ca = v.get("openbao_ca_file") or os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    ctx = ssl.create_default_context(cafile=root_ca)
    host = v["hostname_openbao"]
    conn = http.client.HTTPSConnection(host, v.get("openbao_port", 8200), timeout=timeout, context=ctx)
    try:
        sock = socket.create_connection((v["ip_openbao"], v.get("openbao_port", 8200)), timeout)
        conn.sock = ctx.wrap_socket(sock, server_hostname=host)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Vault-Token"] = token
        conn.request(method, f"/v1/{path.lstrip('/')}", body=json.dumps(body) if body is not None else None,
                     headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
    except (OSError, ssl.SSLError) as exc:
        raise ValidationError(f"OpenBao is not reachable at {v['ip_openbao']}: {exc}") from exc
    finally:
        conn.close()
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {"raw": raw[:200].decode(errors="replace")}
    return resp.status, data
