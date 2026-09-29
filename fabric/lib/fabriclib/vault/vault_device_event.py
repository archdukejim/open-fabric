import subprocess

from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type


def vault_device_event(v, systemctl=None):
    """An enrolled unlock device was plugged in or pulled out (udev):

    - no method present any more and OpenBao running → stop it at once: its
      key leaves memory with the process (the kill switch);
    - a method present and OpenBao stopped → start it (fabric-unlock runs as
      its start condition).
    A key-file method is always present, so it disables the kill switch.
    Returns "stopped", "started" or "unchanged"."""
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
