import hmac
import os

from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_store_mac import slot_store_mac
from fabriclib.vault.common.write_private_file import write_private_file


def unlock_vault(v):
    """fabric-unlock: get the vault key from any present unlock method and
    put it where OpenBao's static seal reads it (<openbao_runtime_dir>, RAM,
    openbao user, 0400) — the current key, and the previous one while a
    rotation is in progress. Returns {"slot": slot id, "tamper": bool}, or
    None when no method is present (OpenBao then must not start: without
    its key file it would not run at all). A slot store that does not match
    its signature is reported (audit) but does not block the unlock: every
    key is still verified against its check value."""
    store = read_slot_store(v)
    if not store:
        return None
    key, slot_id = obtain_key(v, store, store["key_id"])
    if key is None:
        return None
    uid, gid = (int(v["service_users"]["openbao"][k]) for k in ("uid", "gid"))
    runtime = v["openbao_runtime_dir"]
    os.makedirs(runtime, mode=0o700, exist_ok=True)
    os.chown(runtime, uid, gid)
    os.chmod(runtime, 0o700)
    write_private_file(os.path.join(runtime, f"{store['key_id']}.key"), key, uid, gid, 0o400)
    if store.get("previous_key_id"):
        prev, _ = obtain_key(v, store, store["previous_key_id"])
        if prev:
            write_private_file(os.path.join(runtime, f"{store['previous_key_id']}.key"), prev, uid, gid, 0o400)
    tamper = not hmac.compare_digest(slot_store_mac(store, key), store.get("mac", ""))
    if tamper:
        write_audit("fabric-unlock", "VAULT_SLOTS_TAMPERED",
                    "the unlock-method store does not match its signature (changed while locked?)", "host")
    return {"slot": slot_id, "tamper": tamper}
