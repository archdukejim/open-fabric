"""Slot type "local": the vault key in a root-only file on this host.

A slot type is one file with its three operations (wrap, unwrap, present);
fabriclib/vault/common/slot_type.py picks the file by type name."""
import os

from fabriclib.vault.common.write_private_file import write_private_file

TESTED = "real OpenBao image"


def _path(v, wrap):
    return os.path.join(v["openbao_key_dir"], wrap["file"])


def wrap(v, slot, key, key_id):
    """Store `key` for this slot; returns the slot's wrap record for key_id."""
    record = {"file": f"local-{key_id}.key"}
    write_private_file(_path(v, record), key, 0, 0, 0o400)
    return record


def unwrap(v, slot, record, attended=False):
    """The key bytes, or None if the file is gone."""
    try:
        with open(_path(v, record), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def present(v, slot):
    return any(os.path.exists(_path(v, r)) for r in slot["wraps"].values())


def forget(v, slot, record):
    """Destroy this slot's copy (overwrite, then delete)."""
    path = _path(v, record)
    if os.path.exists(path):
        with open(path, "r+b") as f:
            f.write(os.urandom(max(os.path.getsize(path), 1)))
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
