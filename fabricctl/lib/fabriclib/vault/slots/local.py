"""Slot type "local": the vault key in a root-only file on this host.

A slot type is one file with its three operations (wrap, unwrap, present);
fabriclib/vault/common/slot_type.py picks the file by type name."""
import os

from fabriclib.vault.common.write_private_file import write_private_file

TESTED = "real OpenBao image"


def _path(v, wrap):
    """Purpose: the full path of one local key file.
    Inputs:  v — vars: openbao_key_dir; wrap — a wrap record with "file" (e.g. local-fabric-1.key).
    Returns: <openbao_key_dir>/<file> (str).
    Fails:   KeyError if a field is missing; nothing else.
    Feeds:   wrap, unwrap, present, forget.
    """
    return os.path.join(v["openbao_key_dir"], wrap["file"])


def wrap(v, slot, key, key_id):
    """Purpose: store the vault key as a root-only (0400) file on this host.
    Inputs:  v — vars: openbao_key_dir (must exist); slot — the local slot (not used); key — the key (bytes);
             key_id — its version, used in the file name local-<key_id>.key. Takes no attended argument.
    Returns: wrap record {"file": "local-<key_id>.key"}.
    Fails:   OSError from write_private_file (folder missing, not root).
    Feeds:   ensure_vault_key, rotate_vault_key (through slot_type).
    """
    record = {"file": f"local-{key_id}.key"}
    write_private_file(_path(v, record), key, 0, 0, 0o400)
    return record


def unwrap(v, slot, record, attended=False):
    """Purpose: read the vault key back from its local file.
    Inputs:  v — vars; slot — not used; record — the wrap record; attended — not used.
    Returns: the key (bytes), or None if the file is gone. The caller verifies it against the check value.
    Fails:   OSError other than FileNotFoundError (e.g. PermissionError when not root).
    Feeds:   obtain_key (through slot_type).
    """
    try:
        with open(_path(v, record), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def present(v, slot):
    """Purpose: tell whether any of this slot's key files exists.
    Inputs:  v — vars; slot — local slot (its wraps).
    Returns: True if the file of any wrap record exists.
    Fails:   never — os.path.exists does not raise.
    Feeds:   list_slots, vault_device_event (through slot_type).
    Notes:   a key-file method is therefore always present, which disables the kill switch.
    """
    return any(os.path.exists(_path(v, r)) for r in slot["wraps"].values())


def forget(v, slot, record):
    """Purpose: destroy one key version's file: overwrite it with random bytes, fsync, then delete it.
    Inputs:  v — vars; slot — not used; record — the wrap record naming the file.
    Returns: None (nothing happens if the file is already gone).
    Fails:   OSError if the file cannot be opened, written or removed.
    Feeds:   remove_slot, rotate_vault_key (through slot_type).
    """
    path = _path(v, record)
    if os.path.exists(path):
        with open(path, "r+b") as f:
            f.write(os.urandom(max(os.path.getsize(path), 1)))
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
