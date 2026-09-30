import datetime
import re
import subprocess
import uuid

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.block_device import block_device
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.write_slot_store import write_slot_store
from fabriclib.vault.slots import usb
from fabriclib.vault.write_device_rules import write_device_rules

LABEL_RE = re.compile(r"^[\w .,'()-]{0,60}$")


def add_usb_slot(v, actor, disk, label="", source="web", require_usb=True):
    """Erase a USB stick and make it an unlock method.

    Refuses anything that is not a whole, unmounted USB disk (`require_usb`
    is off only in tests, where a loop device stands in). The stick gets an
    ext4 file system with a UUID fabric chooses, the vault key in a
    root-only file, and is read back and verified before the method is
    saved. Returns the new slot id."""
    if not LABEL_RE.match(label or ""):
        raise ValidationError("label: letters, digits and simple punctuation, at most 60")
    facts = block_device(path=disk)
    if not facts:
        raise ValidationError(f"{disk} is not a disk on this host")
    if require_usb and facts["tran"] != "usb":
        raise ValidationError(f"{disk} is not a USB disk")
    if facts["mounted"]:
        raise ValidationError(f"{disk} is in use (mounted at {', '.join(facts['mounted'])}); refusing to erase it")
    store = read_slot_store(v)
    if not store:
        raise ValidationError("no vault key yet: run `sudo fabricctl setup` first")
    # By the UUID fabric gave the stick, not the serial: cheap sticks share
    # one generic serial (seen on hardware: "General_UDisk-0:0").
    if facts["uuid"] and any(s["type"] == "usb" and s["device"].get("fs_uuid") == facts["uuid"]
                             for s in store["slots"]):
        raise ValidationError("this stick is already an unlock method")
    key, _ = obtain_key(v, store, store["key_id"], attended=True)
    if key is None:
        raise ValidationError("no unlock method is present to vouch for the new one")
    fs_uuid = str(uuid.uuid4())
    for cmd in (["wipefs", "-a", disk],
                ["mkfs.ext4", "-q", "-F", "-L", "FABRIC-KEY", "-U", fs_uuid, "-E", "root_owner=0:0", disk]):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise ValidationError(f"preparing {disk} failed: {(res.stderr or res.stdout).strip()[-300:]}")
    # udev does not re-probe after mkfs on its own; without this its database
    # keeps the old (empty) ID_FS_UUID and the kill-switch rule never matches
    # when the stick is pulled (found on real hardware).
    subprocess.run(["udevadm", "trigger", "--action=change", "--settle", disk], capture_output=True)
    subprocess.run(["udevadm", "settle", "--timeout=10"], capture_output=True)
    slot_id = f"usb-{fs_uuid[:8]}"
    model = facts["model"] or "USB stick"
    slot = {"id": slot_id, "type": "usb", "label": label or model, "added": datetime.date.today().isoformat(),
            "device": {"fs_uuid": fs_uuid, "serial": facts["serial"], "model": model,
                       "summary": f"{model} · serial {facts['serial'] or '—'} · UUID {fs_uuid[:8]}",
                       "detail": "a plain stick can be copied by anyone holding it: rotate if one goes missing"},
            "wraps": {}}
    slot["wraps"][store["key_id"]] = usb.wrap(v, slot, key, store["key_id"])
    if usb.unwrap(v, slot, slot["wraps"][store["key_id"]]) != key:
        raise ValidationError("the key read back from the stick does not match; the stick was not added")
    store["slots"].append(slot)
    write_slot_store(v, store, key)
    write_device_rules(v)
    write_audit(actor, "VAULT_SLOT_ADD", f"slot={slot_id} type=usb model={model!r} serial={facts['serial'] or '-'}",
                source)
    return slot_id
