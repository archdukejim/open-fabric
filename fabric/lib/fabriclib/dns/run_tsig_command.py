import argparse
import getpass
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.dns.add_tsig_key import add_tsig_key
from fabriclib.dns.list_tsig_keys import list_tsig_keys
from fabriclib.dns.remove_tsig_key import remove_tsig_key
from fabriclib.system.apply_changes import apply_changes


def _apply():
    ok, output = apply_changes("root", "cli")
    if not ok:
        print(output[-2000:], file=sys.stderr)
        raise ValidationError("apply failed; BIND was not updated (see above)")


def run_tsig_command(argv):
    """`fabricctl tsig list | add <name> | remove <name>` — TSIG keys for
    RFC2136 dynamic updates (e.g. certbot's rfc2136 plugin in
    nginx-proxy-manager). Secrets never appear in argv: an existing secret
    is read from --secret-file or a hidden prompt (--secret-prompt)."""
    ap = argparse.ArgumentParser(prog="fabricctl tsig")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add", help="add a key and apply")
    add.add_argument("name")
    add.add_argument("--domain", help="zone (default: the fabric domain)")
    add.add_argument("--record", action="append", default=[],
                     help="host allowed a DNS-01 challenge (_acme-challenge.<host>.<zone>); repeatable. "
                          "Without --record the key may update any name in the zone")
    add.add_argument("--types", default="TXT", help="record types it may change (default TXT)")
    add.add_argument("--algorithm", default="hmac-sha256")
    add.add_argument("--out", help="where to write its rfc2136.ini (default /opt/<name>/rfc2136.ini)")
    add.add_argument("--secret-file", help="keep an existing key: file holding its base64 secret")
    add.add_argument("--secret-prompt", action="store_true", help="keep an existing key: type its secret")
    rm = sub.add_parser("remove", help="remove a key and apply")
    rm.add_argument("name")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "list":
            keys = list_tsig_keys()
            for k in keys:
                print(f"{k['name']:<24} {k['algorithm']:<12} {k['types']:<8} {k['scope']}\n{'':<24} credentials: {k['ini']}")
            if not keys:
                print("no TSIG keys")
            return 0
        if args.cmd == "add":
            secret = None
            if args.secret_file:
                with open(args.secret_file) as f:
                    secret = f.read().strip()
            elif args.secret_prompt:
                secret = getpass.getpass("TSIG secret (base64): ").strip()
            entry = {"name": args.name, "record_types": [t.strip() for t in args.types.split(",") if t.strip()],
                     "algorithm": args.algorithm}
            for k, val in (("domain", args.domain), ("records", args.record), ("out", args.out)):
                if val:
                    entry[k] = val
            added, _ = add_tsig_key("root", entry, secret)
            _apply()
            print(f"TSIG key '{added['name']}' active ({'existing secret kept' if secret else 'new secret'}).")
            print(f"RFC2136 credentials (server, port, key, secret, algorithm): "
                  f"{added.get('out') or '/opt/' + added['name'] + '/rfc2136.ini'} (0600)")
            return 0
        remove_tsig_key("root", args.name)
        _apply()
        print(f"TSIG key '{args.name}' removed.")
        return 0
    except (ValidationError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
