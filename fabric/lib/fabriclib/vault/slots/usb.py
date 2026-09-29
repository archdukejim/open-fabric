"""Slot type "usb": the vault key on a USB stick fabric formatted.

The stick is recognised by the file-system UUID fabric gave it and, when
the stick reports one, its USB serial: a stick with the right UUID but
another serial is refused. The key file is root-only on the stick; the
stick is mounted read-only (nosuid,nodev,noexec) only while it is read."""
import os

from fabriclib.vault.common.block_device import block_device
from fabriclib.vault.common.mounted_stick import mounted_stick
from fabriclib.vault.common.write_private_file import write_private_file

TESTED = "loop device (format, UUID, read, rotate, remove); real stick on a Pi 5 (add, unlock, pull/re-plug kill switch)"
KEY_DIR = "fabric-vault"


def _stick(slot):
    """The stick if it is attached and is the one enrolled (UUID + serial)."""
    dev = slot["device"]
    found = block_device(fs_uuid=dev["fs_uuid"])
    if not found:
        return None
    if dev.get("serial") and found["serial"] != dev["serial"]:
        return None                 # same UUID on another stick: a copy, not ours
    return found


def wrap(v, slot, key, key_id):
    stick = _stick(slot)
    if not stick:
        raise ValueError("the stick is not attached")
    record = {"file": f"{KEY_DIR}/{key_id}.key"}
    with mounted_stick(v, stick["fs_path"], slot["id"], writable=True) as point:
        os.makedirs(os.path.join(point, KEY_DIR), mode=0o700, exist_ok=True)
        write_private_file(os.path.join(point, record["file"]), key, 0, 0, 0o400)
    return record


def unwrap(v, slot, record):
    stick = _stick(slot)
    if not stick:
        return None
    with mounted_stick(v, stick["fs_path"], slot["id"]) as point:
        path = os.path.join(point, record["file"])
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()


def present(v, slot):
    return _stick(slot) is not None


def forget(v, slot, record):
    """Shred the key file on the stick if it is attached (otherwise the copy
    stays on it until the key is rotated — the UI says so)."""
    stick = _stick(slot)
    if not stick:
        return
    with mounted_stick(v, stick["fs_path"], slot["id"], writable=True) as point:
        path = os.path.join(point, record["file"])
        if os.path.exists(path):
            os.chmod(path, 0o600)
            with open(path, "r+b") as f:
                f.write(os.urandom(max(os.path.getsize(path), 1)))
                f.flush()
                os.fsync(f.fileno())
            os.remove(path)
