import http.client
import json
import os
import socket
import ssl

from fabriclib.common.errors import ValidationError


def bao_request(v, method, path, token=None, body=None, timeout=15, admin=False):
    """Purpose: make one OpenBao HTTP API call (/v1/<path>) and return its status and JSON body.
    Inputs:  v — vars: ip_openbao (connect here) and hostname_openbao (TLS name checked), openbao_port (8200),
               openbao_ca_file or else <deploy_base_dir>/stepca/data/certs/root_ca.crt, openbao_admin_dir.
             method — HTTP verb; path — API path without /v1/ (a leading "/" is stripped);
             token — sent as X-Vault-Token, or None; body — JSON-able payload, or None;
             timeout — seconds (15);
             admin — True: plain HTTP over the root-only break-glass socket
               <openbao_admin_dir or /run/fabric/openbao-admin>/bao.sock instead of TLS on fabric_net.
    Returns: (status int, data): data is the parsed JSON, {} for an empty body, or {"raw": first 200 chars}
             when the body is not JSON. HTTP error statuses are returned, not raised.
    Fails:   ValidationError "OpenBao is not reachable" on OSError / ssl.SSLError while connecting or talking
             (refused, timeout, certificate not verified); OSError / ssl.SSLError if the CA file cannot be loaded
             (raised before the connection); http.client.HTTPException (a malformed response) propagates as is.
    Feeds:   every OpenBao call: approle_login, wait_active, configure_openbao, configure_oidc, init_openbao,
             generate_root_token, revoke_token, vault_status, secrets/common/read_vault_secrets and
             write_vault_secrets, tests/openbao/run.py.
    Notes:   the socket goes to ip_openbao while the certificate is verified for hostname_openbao against the fabric
             root CA, so no DNS is needed. The admin socket is the only place generate-root is enabled.
    """
    root_ca = v.get("openbao_ca_file") or os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    ctx = ssl.create_default_context(cafile=root_ca)
    host = v["hostname_openbao"]
    conn = http.client.HTTPSConnection(host, v.get("openbao_port", 8200), timeout=timeout, context=ctx)
    try:
        if admin:
            conn = http.client.HTTPConnection("localhost", timeout=timeout)
            conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            conn.sock.settimeout(timeout)
            conn.sock.connect(os.path.join(v.get("openbao_admin_dir") or "/run/fabric/openbao-admin", "bao.sock"))
        else:
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
