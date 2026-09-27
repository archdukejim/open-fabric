import argparse
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.add_acl_entries import add_acl_entries
from fabriclib.dns.builtin_acls import builtin_acls
from fabriclib.dns.remove_acl_entries import remove_acl_entries
from fabriclib.dns.set_acl_policy import set_acl_policy
from fabriclib.system.apply_changes import apply_changes


def _describe(policy):
    what = (", ".join(f"_acme-challenge.{r}.{policy['domain']}" for r in policy["records"])
            if policy.get("records") else f"any name in {policy['domain']}")
    return f"members may update {what} ({' '.join(policy['record_types'])})"


def run_acl_command(argv):
    """`fabricctl acl list | add | remove | policy` — BIND ACLs (bind_acls)
    and their update policies. Every ACL may query fabric's zones. Entries:
    IP, CIDR, 'key <tsig-key>', another ACL, any/none/localhost/localnets;
    prefix with ! to exclude. A policy gives every TSIG key in the ACL
    update rights (e.g. DNS-01 TXT records for chosen hosts only)."""
    ap = argparse.ArgumentParser(prog="fabricctl acl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add", help="create an ACL or add entries, then apply")
    add.add_argument("acl")
    add.add_argument("entries", nargs="+", help="e.g. 192.168.10.0/24 10.0.0.5 'key npm' '!10.0.0.9'")
    rm = sub.add_parser("remove", help="remove entries (or the whole ACL and its policy), then apply")
    rm.add_argument("acl")
    rm.add_argument("entries", nargs="*")
    pol = sub.add_parser("policy", help="set what the ACL's TSIG keys may update (created if missing)")
    pol.add_argument("acl")
    pol.add_argument("--record", action="append", default=[],
                     help="host whose DNS-01 challenge members may set (_acme-challenge.<host>.<zone>); repeatable")
    pol.add_argument("--any-name", action="store_true", help="members may update any name in the zone")
    pol.add_argument("--types", default="TXT", help="record types, comma-separated (default TXT)")
    pol.add_argument("--domain", help="zone (default: the fabric domain)")
    pol.add_argument("--clear", action="store_true", help="remove the policy (members lose these rights)")
    for p in (add, rm, pol):
        p.add_argument("--no-apply", action="store_true", help="only record the change; apply later")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "list":
            data = load_vars()
            builtin = builtin_acls(data)
            policies = data.get("bind_acl_policies") or {}
            for name, entries in (data.get("bind_acls") or {}).items():
                tag = " (built in)" if name in builtin else ""
                print(f"{name}{tag}: {', '.join(entries or []) or '(empty)'}")
                if name in policies:
                    print(f"    policy: {_describe(policies[name])}")
            print("tsig-updaters (automatic): every TSIG key")
            return 0
        if args.cmd == "add":
            entries = add_acl_entries("root", args.acl, args.entries)
            print(f"{args.acl}: {', '.join(entries)}")
        elif args.cmd == "remove":
            remove_acl_entries("root", args.acl, args.entries)
            print(f"{args.acl}: " + ("removed" if not args.entries else "entries removed"))
        else:
            if args.clear:
                set_acl_policy("root", args.acl, None)
                print(f"{args.acl}: policy removed")
            else:
                if bool(args.record) == args.any_name:
                    raise ValidationError("give --record host (repeatable) or --any-name")
                policy = {"record_types": [t.strip() for t in args.types.split(",") if t.strip()]}
                if args.record:
                    policy["records"] = args.record
                else:
                    policy["any_name"] = True
                if args.domain:
                    policy["domain"] = args.domain
                print(f"{args.acl}: {_describe(set_acl_policy('root', args.acl, policy))}")
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
