import sys

from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.add_reservation import add_reservation
from fabriclib.dhcp.dhcp_overview import dhcp_overview
from fabriclib.dhcp.remove_reservation import remove_reservation
from fabriclib.system.apply_changes import apply_changes

USAGE = """usage: fabricctl dhcp status                       subnets, pools, reservations
       fabricctl dhcp leases                       active leases (from Kea)
       fabricctl dhcp reserve <mac> <ip> [<hostname>] [--no-apply]
       fabricctl dhcp unreserve <mac> [--no-apply]"""


def _apply(args):
    """Purpose: Apply a just-recorded DHCP change now, unless --no-apply was given.
    Inputs:  args — list of str (looks for "--no-apply"). Runs apply_changes as root (interactive.py --apply).
    Returns: 0 if skipped or applied; 1 if apply failed (last 2000 characters of its output on stdout).
    Fails:   subprocess.TimeoutExpired (900 s) and OSError from apply_changes propagate.
    Feeds:   run_dhcp_command (reserve, unreserve).
    """
    if "--no-apply" in args:
        print("recorded; apply with: sudo fabricctl --apply")
        return 0
    ok, output = apply_changes("root", "cli")
    print("applied (Kea reloaded)" if ok else output[-2000:])
    return 0 if ok else 1


def run_dhcp_command(v, argv):
    """Purpose: `fabricctl dhcp status | leases | reserve | unreserve` — the Kea tab's operations without the web UI.
    Inputs:  v — the rendered vars (SetupContext.load_state().vars).
             argv — list of str after "dhcp" (default status): reserve <mac> <ip> [<hostname>], unreserve <mac>, each
             with optional --no-apply.
    Returns: exit status: 0 success; 1 a ValidationError, unreadable leases or a failed apply; 2 usage (printed to
             stderr).
    Fails:   ValidationError is caught (exit 1); other exceptions propagate.
    Feeds:   fabriclib/cli.py (`fabricctl dhcp`).
    """
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    pos = [a for a in args if not a.startswith("--")]
    try:
        if cmd in ("status", "leases") and not pos:
            d = dhcp_overview(v)
            if not d["enabled"]:
                print("DHCP is off (install_kea: false)")
                return 0
            if cmd == "status":
                print(f"interfaces {', '.join(d['interfaces'])}  lease {d['lease_time']} s"
                      + (f"  hostnames in {d['ddns_zone']}" if d["ddns_zone"] else ""))
                for s in d["subnets"]:
                    print(f"{s['subnet']:<20} pools {', '.join(s.get('pools') or [])}  router {s.get('routers') or '-'}")
                    for r in s.get("reservations") or []:
                        print(f"  {r['mac']}  {r['ip']:<15} {r.get('hostname') or ''}")
                return 0
            if d["leases_error"]:
                print(f"error: {d['leases_error']}", file=sys.stderr)
                return 1
            for lease in d["leases"]:
                print(f"{lease['ip']:<15} {lease['mac']}  {lease['hostname'] or '-':<30} {lease['expires']}  {lease['state']}")
            return 0
        if cmd == "reserve" and len(pos) in (2, 3):
            saved = add_reservation("root", pos[0], pos[1], pos[2] if len(pos) == 3 else "", source="cli")
            print(f"reserved {saved['ip']} for {saved['mac']}")
            return _apply(args)
        if cmd == "unreserve" and len(pos) == 1:
            remove_reservation("root", pos[0], source="cli")
            print(f"reservation for {pos[0]} removed")
            return _apply(args)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
