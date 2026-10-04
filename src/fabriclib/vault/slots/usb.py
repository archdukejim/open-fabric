"""Slot type "usb": the vault key on a USB stick fabric formatted.

The stick is recognised by the file-system UUID fabric gave it and, when
the stick reports one, its USB serial: a stick with the right UUID but
another serial is refused. The key file is root-only on the stick; the
stick is mounted read-only (nosuid,nodev,noexec) only while it is read."""
import os

from fabriclib.vault.common.block_device import block_device
from fabriclib.vault.common.mounted_stick import mounted_stick
from fabriclib.vault.common.write_private_file import write_private_file

TESTED = ("loop device (format, UUID, read, rotate, remove); "
          "real stick on a Pi 5 (add, unlock, pull/re-plug kill switch)")
KEY_DIR = "fabric-vault"


def _stick(slot):
    """Purpose: the enrolled stick, if it is attached: found by file-system UUID, and by USB serial if one was recorded.
    Inputs:  slot — usb slot: device.fs_uuid, device.serial.
    Returns: block_device facts ({path, fs_path, serial, ...}), or None if absent or the serial differs.
    Fails:   FileNotFoundError if lsblk is missing (see block_device).
    Feeds:   wrap, unwrap, present, forget.
    Notes:   a stick with the right UUID but another serial is a copy, not ours, and is refused.
    """
    dev = slot["device"]
    found = block_device(fs_uuid=dev["fs_uuid"])
    if not found:
        return None
    if dev.get("serial") and found["serial"] != dev["serial"]:
        return None                 # same UUID on another stick: a copy, not ours
    return found


def wrap(v, slot, key, key_id):
    """Purpose: write the vault key as a root-only (0400) file fabric-vault/<key_id>.key on the attached stick.
    Inputs:  v — vars (for the mount point); slot — usb slot; key — the key (bytes); key_id — its version.
             Takes no attended argument.
    Returns: wrap record {"file": "fabric-vault/<key_id>.key"}.
    Fails:   ValueError if the stick is not attached; ValidationError from mounted_stick; OSError writing.
    Feeds:   add_usb_slot, rotate_vault_key (through slot_type).
    """
    stick = _stick(slot)
    if not stick:
        raise ValueError("the stick is not attached")
    record = {"file": f"{KEY_DIR}/{key_id}.key"}
    with mounted_stick(v, stick["fs_path"], slot["id"], writable=True) as point:
        os.makedirs(os.path.join(point, KEY_DIR), mode=0o700, exist_ok=True)
        write_private_file(os.path.join(point, record["file"]), key, 0, 0, 0o400)
    return record


def unwrap(v, slot, record, attended=False):
    """Purpose: read the vault key from the stick, mounted read-only (nosuid,nodev,noexec) only while it is read.
    Inputs:  v — vars; slot — usb slot; record — the wrap record; attended — not used.
    Returns: the key (bytes), or None if the stick is absent or the file is missing.
    Fails:   ValidationError from mounted_stick; OSError reading.
    Feeds:   obtain_key (through slot_type), add_usb_slot (read-back check).
    """
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
    """Purpose: tell whether the enrolled stick is attached (nothing is mounted).
    Inputs:  v — not used; slot — usb slot.
    Returns: True if _stick finds it, else False.
    Fails:   FileNotFoundError if lsblk is missing; list_slots and vault_device_event catch it.
    Feeds:   list_slots, vault_device_event (through slot_type).
    """
    return _stick(slot) is not None


def forget(v, slot, record):
    """Purpose: shred one key version's file on the stick (random overwrite, fsync, delete) if the stick is attached.
    Inputs:  v — vars; slot — usb slot; record — the wrap record naming the file.
    Returns: None. With the stick absent nothing happens: the copy stays on it until the key is rotated
             (the UI says so).
    Fails:   ValidationError from mounted_stick; OSError writing or removing.
    Feeds:   remove_slot, rotate_vault_key (through slot_type).
    """
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
