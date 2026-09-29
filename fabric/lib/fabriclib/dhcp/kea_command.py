import json
import os
import socket

from fabriclib.common.errors import ValidationError


def kea_command(v, command, arguments=None, timeout=10):
    """One command to kea-dhcp4 over its control socket (host side:
    <deploy_base>/kea/run/kea4-ctrl-socket, root only). Returns the
    response's `arguments` (or {}); raises ValidationError if Kea is not
    running or refuses."""
    path = os.path.join(v["deploy_base_dir"], "kea", "run", "kea4-ctrl-socket")
    req = {"command": command, **({"arguments": arguments} if arguments else {})}
    resp = None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            s.sendall(json.dumps(req).encode())
            data = b""
            while resp is None:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
                try:
                    resp = json.loads(data)
                except ValueError:
                    continue
    except OSError as exc:
        raise ValidationError(f"Kea is not answering ({exc}): sudo fabricctl status")
    if resp is None:
        raise ValidationError(f"Kea sent no answer to {command}")
    if isinstance(resp, list):
        resp = resp[0]
    if resp.get("result") not in (0, 3):                   # 3 = empty (e.g. no leases yet)
        raise ValidationError(f"Kea refused {command}: {resp.get('text', '')}")
    return resp.get("arguments") or {}
