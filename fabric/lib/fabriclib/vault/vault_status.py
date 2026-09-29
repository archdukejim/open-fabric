import os
import stat

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import AGENT_CREDS, KEY_FILE


def _key_state(v):
    path = os.path.join(v["openbao_key_dir"], KEY_FILE)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return {"path": path, "present": False, "ok": False, "detail": "missing"}
    uid = int(v["service_users"]["openbao"]["uid"])
    mode = stat.S_IMODE(st.st_mode)
    ok = st.st_uid == uid and mode == 0o400 and st.st_size == 32
    return {"path": path, "present": True, "ok": ok,
            "detail": "32 bytes, 0400, openbao only" if ok else f"mode {oct(mode)}, owner uid {st.st_uid}, {st.st_size} bytes"}


def vault_status(v):
    """OpenBao at a glance, for `fabricctl vault status` and the web UI:
    reachability, initialised/sealed, version, seal and storage type, the
    seal key file's permissions, and (as fabric-agent) the secret engines
    and auth methods. Never returns secrets."""
    out = {"url": f"https://{v['hostname_openbao']}/", "key": _key_state(v), "reachable": False}
    try:
        status, health = bao_request(v, "GET", "sys/health?uninitcode=200&sealedcode=200&standbyok=true")
        _, seal = bao_request(v, "GET", "sys/seal-status")
    except ValidationError as exc:
        out["error"] = str(exc)
        return out
    out.update(reachable=True, initialized=bool(health.get("initialized")), sealed=bool(health.get("sealed")),
               version=health.get("version", ""), seal_type=seal.get("type", ""),
               storage=seal.get("storage_type", ""), recovery_seal=bool(seal.get("recovery_seal")),
               mounts=[], auth=[])
    if out["initialized"] and not out["sealed"]:
        try:
            token = approle_login(v, AGENT_CREDS)
            mounts = bao_request(v, "GET", "sys/mounts", token=token)[1]
            auth = bao_request(v, "GET", "sys/auth", token=token)[1]
            out["mounts"] = sorted(({"path": k, "type": m.get("type"), "version": (m.get("options") or {}).get("version"),
                                     "description": m.get("description", "")}
                                    for k, m in (mounts.get("data") or mounts).items() if isinstance(m, dict)),
                                   key=lambda m: m["path"])
            out["auth"] = sorted(k for k, m in (auth.get("data") or auth).items() if isinstance(m, dict))
            st, meta = bao_request(v, "GET", "fabric/metadata/secrets", token=token)
            if st == 200:
                d = meta.get("data") or {}
                out["secrets"] = {"version": d.get("current_version"), "updated": (d.get("updated_time") or "")[:19]}
        except ValidationError as exc:
            out["error"] = str(exc)
    return out
