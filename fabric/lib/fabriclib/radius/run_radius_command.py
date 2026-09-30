import getpass
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.radius.add_radius_client import add_radius_client
from fabriclib.radius.list_auth_log import list_auth_log
from fabriclib.radius.radius_overview import radius_overview
from fabriclib.radius.remove_radius_client import remove_radius_client
from fabriclib.radius.rotate_radius_secret import rotate_radius_secret
from fabriclib.system.apply_changes import apply_changes

USAGE = """usage: fabricctl radius status                     server name, RADIUS clients
       fabricctl radius log [-n N]                 recent 802.1X decisions (accepted, refused and why)
       fabricctl radius add-client <name> <address> [--secret-prompt] [--no-message-authenticator] [--no-apply]
       fabricctl radius rotate-secret <name> [--secret-prompt] [--no-apply]
       fabricctl radius remove-client <name> [--no-apply]
  A new secret is shown once; --secret-prompt keeps one the switch already has (typed, hidden)."""


def _apply(args):
    if "--no-apply" in args:
        print("recorded; apply with: sudo fabricctl --apply")
        return 0
    ok, output = apply_changes("root", "cli")
    print("applied (FreeRADIUS restarted)" if ok else output[-2000:])
    return 0 if ok else 1


def _secret(args):
    return getpass.getpass("shared secret (hidden): ").strip() if "--secret-prompt" in args else None


def run_radius_command(v, argv):
    """`fabricctl radius …` — the FreeRADIUS tab's operations, without the web UI."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    pos = [a for a in args if not a.startswith("-")]
    try:
        if cmd == "status" and not pos:
            o = radius_overview(v, log_limit=0)
            if not o["enabled"]:
                print("802.1X is off (install_freeradius: false)")
                return 0
            print(f"server name (supplicants check it): {o['server_name']}   RADIUS on {o['host_ip']}:1812/udp")
            for c in o["clients"] or []:
                print(f"  {c['name']:<16} {c['address']:<20} "
                      f"{'Message-Authenticator required' if c['message_authenticator'] else 'Message-Authenticator NOT required'}")
            if not o["clients"]:
                print("  no RADIUS clients yet: fabricctl radius add-client <name> <address>")
            return 0
        if cmd == "log":
            n = int(args[args.index("-n") + 1]) if "-n" in args else 50
            for e in list_auth_log(n):
                print(f"{e['time']}  {e['decision']:<6} {e['method']:<8} {e['device']:<16} vlan {e['vlan']:<5} "
                      f"mac {e['mac']:<17} via {e['nas']}" + (f"  — {e['reason']}" if e["reason"] else ""))
            return 0
        if cmd == "add-client" and len(pos) == 2:
            secret = add_radius_client("root", pos[0], pos[1], "--no-message-authenticator" not in args, _secret(args))
            print(f"RADIUS client {pos[0].lower()} added; its shared secret (shown once, kept in OpenBao):\n{secret}")
            return _apply(args)
        if cmd == "rotate-secret" and len(pos) == 1:
            secret = rotate_radius_secret("root", pos[0], _secret(args))
            print(f"new shared secret for {pos[0].lower()} (shown once; give the device the same):\n{secret}")
            return _apply(args)
        if cmd == "remove-client" and len(pos) == 1:
            remove_radius_client("root", pos[0])
            print(f"RADIUS client {pos[0].lower()} removed")
            return _apply(args)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
