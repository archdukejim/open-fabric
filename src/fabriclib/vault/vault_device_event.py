import subprocess

from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type


def vault_device_event(v, systemctl=None):
    """Purpose: the kill switch: an enrolled unlock device was plugged in or pulled out (run from udev).
    Inputs:  v — vars; reads slots.json and asks each type whether its device is present;
             systemctl — callable(*args) returning a CompletedProcess (default: runs systemctl; tests pass a fake).
    Returns: "stopped" — no method present any more and OpenBao was running: stopped at once, its key leaves memory
               with the process; "started" — a method present and OpenBao stopped (fabric-unlock runs as its start
               condition); "unchanged" otherwise.
    Fails:   never for a method's present() (caught); ValueError/OSError reading the store; audit write errors.
             systemctl failures are not checked.
    Feeds:   `fabricctl vault device-event` (run from the rules of write_device_rules), tests/openbao/run.py.
    Notes:   a key-file method is always present, so it disables the kill switch. Audited as VAULT_LOCKED or
             VAULT_UNLOCK.
    """
    systemctl = systemctl or (lambda *a: subprocess.run(["systemctl", *a], capture_output=True, text=True))
    store = read_slot_store(v) or {"slots": []}
    here = []
    for slot in store["slots"]:
        try:
            if slot_type(slot["type"]).present(v, slot):
                here.append(slot["id"])
        except Exception:
            pass
    running = systemctl("is-active", "--quiet", "openbao").returncode == 0
    if running and not here:
        systemctl("stop", "openbao")
        write_audit("fabric-unlock", "VAULT_LOCKED", "last unlock device removed: OpenBao stopped", "host")
        return "stopped"
    if not running and here:
        systemctl("start", "openbao")
        write_audit("fabric-unlock", "VAULT_UNLOCK", f"unlock device present ({', '.join(here)}): starting OpenBao", "host")
        return "started"
    return "unchanged"
