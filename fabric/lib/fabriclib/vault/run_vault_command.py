import subprocess
import sys
import time

from fabriclib.common.errors import ValidationError
from fabriclib.vault.add_usb_slot import add_usb_slot
from fabriclib.vault.list_slots import list_slots
from fabriclib.vault.remove_slot import remove_slot
from fabriclib.vault.rotate_vault_key import rotate_vault_key
from fabriclib.vault.test_slot import test_slot
from fabriclib.vault.unlock_vault import unlock_vault
from fabriclib.vault.vault_device_event import vault_device_event
from fabriclib.vault.vault_status import vault_status
from fabriclib.vault.wipe_runtime_keys import wipe_runtime_keys

USAGE = """usage: fabricctl vault status
       fabricctl vault slots                 unlock methods (key slots)
       fabricctl vault test <slot>           unwrap the vault key through one method
       fabricctl vault remove <slot> --yes   remove a method (never the last)
       fabricctl vault rotate --yes          new vault key for every present method
       fabricctl vault add-usb <disk> [--label L] --yes   ERASE a USB stick and make it an unlock method
       fabricctl vault unlock                (systemd) put the key in RAM for OpenBao's start
       fabricctl vault device-event          (udev) an unlock device came or went: start/stop OpenBao
       fabricctl vault wipe-key              (systemd) wipe it once OpenBao is unsealed"""


def restart_openbao(v, timeout=180):
    """Restart the openbao unit (its start condition runs fabric-unlock) and
    wait until OpenBao is unsealed."""
    subprocess.run(["systemctl", "restart", "openbao"], check=True, timeout=timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = vault_status(v)
        if s.get("initialized") and s.get("sealed") is False:
            return
        time.sleep(3)
    raise ValidationError("OpenBao did not come back unsealed")


def _status(v):
    s = vault_status(v)
    if not s["reachable"]:
        print(f"OpenBao: unreachable — {s.get('error', '')}")
        return 1
    state = "not initialised" if not s["initialized"] else ("SEALED" if s["sealed"] else "unsealed")
    print(f"OpenBao {s['version']}: {state}  ({s['seal_type']} seal, {s['storage']} storage)  {s['url']}")
    print(f"unlock methods: {s['key']['detail']}")
    for m in s.get("mounts", []):
        print(f"  {m['path']:<12} {m['type']}{' v' + m['version'] if m['version'] else ''}  {m['description']}")
    if s.get("secrets"):
        print(f"fabric's secrets: in OpenBao (fabric/secrets, version {s['secrets']['version']}, "
              f"updated {s['secrets']['updated']})")
    if s.get("auth"):
        print(f"  auth: {', '.join(s['auth'])}")
    if s.get("error"):
        print(f"note: {s['error']}")
    return 0 if s["initialized"] and not s["sealed"] else 1


def run_vault_command(v, argv):
    """`fabricctl vault …` — OpenBao status and its unlock methods. Never
    prints key material. `unlock` exits 0 when the key is in place and 1
    when no method is present (systemd then skips starting OpenBao)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    try:
        if cmd == "status" and not args:
            return _status(v)
        if cmd == "unlock" and not args:
            res = unlock_vault(v)
            if res is None:
                print("no unlock method is present: OpenBao stays locked", file=sys.stderr)
                return 1
            print(f"vault key in place (via {res['slot']})" + (" — WARNING: unlock methods changed while locked"
                                                              if res["tamper"] else ""))
            return 0
        if cmd == "wipe-key" and not args:
            print(f"wiped {wipe_runtime_keys(v)} key file(s) from RAM")
            return 0
        if cmd == "slots" and not args:
            for sl in list_slots(v):
                print(f"{'●' if sl['present'] else '○'} {sl['id']:<12} {sl['type']:<7} {sl['key_id']:<10} "
                      f"{sl['label']}  {sl['device']}  [tested: {sl['tested']}]")
            return 0
        if cmd == "test" and len(args) == 1:
            test_slot(v, "root", args[0], source="cli")
            print(f"{args[0]}: unwrapped the vault key, check value matches")
            return 0
        if cmd == "remove" and len(args) == 2 and args[1] in ("--yes", "-y"):
            remove_slot(v, "root", args[0], source="cli")
            print(f"{args[0]}: removed")
            return 0
        if cmd == "device-event" and not args:
            print(vault_device_event(v))
            return 0
        if cmd == "add-usb" and args and "--yes" in args:
            label = args[args.index("--label") + 1] if "--label" in args else ""
            print(f"added {add_usb_slot(v, 'root', args[0], label, source='cli')}")
            return 0
        if cmd == "rotate" and args in (["--yes"], ["-y"]):
            res = rotate_vault_key(v, "root", lambda: restart_openbao(v), source="cli")
            print(f"vault key rotated to {res['key_id']}; kept {', '.join(res['kept'])}"
                  + (f"; dropped {', '.join(res['dropped'])}" if res["dropped"] else ""))
            return 0
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
