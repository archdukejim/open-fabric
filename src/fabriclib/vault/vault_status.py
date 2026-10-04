import os
import stat

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.constants import AGENT_CREDS, SLOT_STORE


def _key_state(v):
    """Purpose: check the unlock-method store is safe: root-owned 0600, and no vault key left in RAM.
    Inputs:  v — vars: openbao_key_dir (slots.json), openbao_runtime_dir (*.key files).
    Returns: {path, present, ok, detail} plus, when the store exists, methods (count) and key_id; detail lists the
             problems or summarises the healthy state.
    Fails:   PermissionError (OSError) when not root; ValueError on a corrupt store.
    Feeds:   vault_status (its "key" field).
    """
    path = os.path.join(v["openbao_key_dir"], SLOT_STORE)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return {"path": path, "present": False, "ok": False, "detail": "no unlock methods"}
    mode = stat.S_IMODE(st.st_mode)
    store = read_slot_store(v) or {}
    left = [f for f in os.listdir(v["openbao_runtime_dir"]) if f.endswith(".key")] \
        if os.path.isdir(v.get("openbao_runtime_dir", "")) else []
    problems = ([f"store mode {oct(mode)} / owner {st.st_uid}"] if st.st_uid != 0 or mode != 0o600 else []) + \
               ([f"{len(left)} key file(s) still in RAM"] if left else [])
    n = len(store.get("slots", []))
    return {"path": path, "present": True, "ok": not problems, "methods": n, "key_id": store.get("key_id"),
            "detail": "; ".join(problems) or f"{n} unlock method{'s' if n != 1 else ''}, "
                                               f"vault key {store.get('key_id')}, "
                                               "store root-only, no key left in RAM"}


def vault_status(v):
    """Purpose: OpenBao at a glance for `fabricctl vault status`, setup and the web UI. Never returns secrets.
    Inputs:  v — vars; logs in as fabric-agent (AGENT_CREDS) when OpenBao is initialised and unsealed.
    Returns: {url, key (_key_state), reachable} and, when reachable: initialized, sealed, version, seal_type, storage,
             recovery_seal, mounts [{path, type, version, description}], auth [paths], optionally secrets {version,
             updated} (metadata of fabric/secrets, never a value) and error (why a part is missing).
    Fails:   OpenBao errors (ValidationError) are caught into "error"; OSError from _key_state propagates.
    Feeds:   agent route GET /v1/vault (webui agentclient.vault_status), run_vault_command._status,
             setup/setup_openbao, setup/verify_install, tests/openbao/run.py.
    """
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
            out["mounts"] = sorted(({"path": k, "type": m.get("type"),
                                     "version": (m.get("options") or {}).get("version"),
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
