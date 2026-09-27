import argparse
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.add_acl_entries import add_acl_entries
from fabriclib.dns.builtin_acls import builtin_acls
from fabriclib.dns.remove_acl_entries import remove_acl_entries
from fabriclib.system.apply_changes import apply_changes


def run_acl_command(argv):
    """`fabricctl acl list | add <acl> <entry>... | remove <acl> [<entry>...]`
    — BIND ACLs (bind_acls). Every ACL may query fabric's zones. Entries: IP,
    CIDR, 'key <tsig-key>', another ACL, any/none/localhost/localnets;
    prefix with ! to exclude."""
    ap = argparse.ArgumentParser(prog="fabricctl acl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add", help="create an ACL or add entries, then apply")
    add.add_argument("acl")
    add.add_argument("entries", nargs="+", help="e.g. 192.168.10.0/24 10.0.0.5 'key npm' '!10.0.0.9'")
    rm = sub.add_parser("remove", help="remove entries (or the whole ACL), then apply")
    rm.add_argument("acl")
    rm.add_argument("entries", nargs="*")
    for p in (add, rm):
        p.add_argument("--no-apply", action="store_true", help="only record the change; apply later")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "list":
            data = load_vars()
            builtin = builtin_acls(data)
            for name, entries in (data.get("bind_acls") or {}).items():
                tag = " (built in)" if name in builtin else ""
                print(f"{name}{tag}: {', '.join(entries or []) or '(empty)'}")
            print("tsig-updaters (automatic): every TSIG key")
            return 0
        if args.cmd == "add":
            entries = add_acl_entries("root", args.acl, args.entries)
            print(f"{args.acl}: {', '.join(entries)}")
        else:
            remove_acl_entries("root", args.acl, args.entries)
            print(f"{args.acl}: " + ("removed" if not args.entries else "entries removed"))
        if args.no_apply:
            print("not applied yet: sudo fabricctl --apply")
            return 0
        ok, output = apply_changes("root", "cli")
        if not ok:
            print(output[-2000:], file=sys.stderr)
            raise ValidationError("apply failed; BIND was not updated (see above)")
        print("applied")
        return 0
    except (ValidationError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
