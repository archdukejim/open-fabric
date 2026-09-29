import datetime
import os

from fabriclib.vault.constants import KEY_FILE


def list_slots(v):
    """The ways this vault can be unlocked (key slots). Until slot storage
    lands, an install has exactly one: the local key file OpenBao's static
    seal reads. Returns [{id, type, label, device, present, key_id, added,
    detail}] — never key material."""
    path = os.path.join(v["openbao_key_dir"], KEY_FILE)
    if not os.path.exists(path):
        return []
    st = os.stat(path)
    return [{"id": "local", "type": "local", "label": "Key file on this host", "device": path,
             "present": st.st_size == 32, "key_id": v.get("openbao_seal_key_id", "fabric-1"),
             "added": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
             "detail": "always present: while this slot exists, removing a device cannot seal the vault"}]
