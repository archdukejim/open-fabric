import os
import subprocess

from fabriclib.vault.common.read_slot_store import read_slot_store

RULES = "/etc/udev/rules.d/90-fabric-unlock.rules"


def write_device_rules(v, path=None):
    """udev rules for the kill switch: when an enrolled stick (by file-system
    UUID) or security key (by USB serial) is plugged in or pulled out, run
    `fabricctl vault device-event` (through systemd-run: udev must not wait).
    Only enrolled devices trigger it. Returns True if the rules changed.
    udev does not run in the test containers: tested by hand with a real
    stick on a Pi 5 (pull → OpenBao stopped, re-plug → started)."""
    path = path or v.get("openbao_udev_rules") or RULES
    store = read_slot_store(v) or {"slots": []}
    cli = f"{v['deploy_base_dir']}/fabric/lib/fabriclib/cli.py"
    run = f'RUN+="/usr/bin/systemd-run --no-block --collect /usr/bin/python3 {cli} vault device-event"'
    lines = ["# Written by fabricctl (fabriclib/vault/write_device_rules.py): unlock-method devices.", ""]
    for slot in store["slots"]:
        dev = slot.get("device") or {}
        if slot["type"] == "usb" and dev.get("fs_uuid"):
            lines.append(f'ACTION=="add|remove", SUBSYSTEM=="block", ENV{{ID_FS_UUID}}=="{dev["fs_uuid"]}", {run}')
        elif slot["type"] == "pkcs11" and dev.get("usb_serial"):
            lines.append(f'ACTION=="add|remove", SUBSYSTEM=="usb", ENV{{DEVTYPE}}=="usb_device", '
                         f'ENV{{ID_SERIAL_SHORT}}=="{dev["usb_serial"]}", {run}')
    text = "\n".join(lines) + "\n"
    if os.path.exists(path) and open(path).read() == text:
        return False
    if not os.path.isdir(os.path.dirname(path)):
        return False
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o644)
    subprocess.run(["udevadm", "control", "--reload"], capture_output=True)
    return True
