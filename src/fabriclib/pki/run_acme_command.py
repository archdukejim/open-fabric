import re
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.dns.add_tsig_key import add_tsig_key
from fabriclib.dns.remove_tsig_key import remove_tsig_key
from fabriclib.pki.acme_info import acme_info
from fabriclib.pki.acme_machines import PREFIX, acme_machines
from fabriclib.system.apply_changes import apply_changes

USAGE = """usage: fabricctl acme info                   the ACME directory LAN machines use, and how (2.1.5.8)
       fabricctl acme enroll <name> [--dns]   a machine named <name>.<domain>; --dns: its DNS-01 key (it may change
                                              only _acme-challenge.<name>'s TXT record), for a machine without a
                                              web server on port 80
       fabricctl acme list                    the machines enrolled for DNS-01
       fabricctl acme remove <name>           withdraw a machine's DNS-01 key"""
LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*$")


def run_acme_command(ctx, argv):
    """Purpose: `fabricctl acme info | enroll | list | remove` — ACME from fabric's CA for machines fabric does not run
             (manual 2.1.5.8): the directory and, for DNS-01, a TSIG key per machine that may change only that
             machine's _acme-challenge TXT record (fabric's TSIG keys, applied at once).
    Inputs:  ctx — SetupContext (not loaded); argv — list of str after "acme".
    Returns: exit status: 0 done, 1 refused (ValidationError printed) or the apply failed, 2 usage.
    Fails:   never raises a ValidationError (printed, exit 1); OSError propagates.
    Feeds:   cli main (`acme`)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("info", [])
    try:
        if cmd == "info" and not args:
            print("\n".join(acme_info(ctx.load_state().vars)))
            return 0
        if cmd == "list" and not args:
            machines = acme_machines(ctx.load_state().vars)
            for m in machines:
                print(f"{m['name']:<30} DNS-01 key {m['key']} (TXT at _acme-challenge.{', '.join(m['records'])})")
            print(f"{len(machines)} machine(s) enrolled for DNS-01" if machines else "no machine enrolled for DNS-01")
            return 0
        if cmd in ("enroll", "remove") and args and set(args[1:]) <= ({"--dns"} if cmd == "enroll" else set()) \
                and not args[0].startswith("-"):
            name = args[0].lower()
            v = ctx.load_state().vars
            suffix = "." + v["domain"]
            if name.endswith(suffix):
                name = name[:-len(suffix)]
            if not LABEL.match(name) or len(PREFIX + name) > 63:
                raise ValidationError(f"{args[0]!r}: a machine's name under {v['domain']} (letters, digits, hyphens; "
                                      "dots between labels)")
            if cmd == "enroll" and "--dns" not in args:
                print(f"{name}.{v['domain']}: nothing to enroll for http-01; its client uses:")
                print("\n".join("  " + line for line in acme_info(v)[:4]))
                return 0
            if cmd == "enroll":
                add_tsig_key("root", {"name": PREFIX + name, "records": [name], "record_types": ["TXT"]})
            else:
                remove_tsig_key("root", PREFIX + name)
            ok, output = apply_changes("root", "cli")
            if not ok:
                print(output[-2000:])
                return 1
            if cmd == "enroll":
                print(f"{name}.{v['domain']}: DNS-01 key {PREFIX + name}, allowed only _acme-challenge.{name}'s TXT "
                      f"record; its settings (with the secret) in /opt/{PREFIX + name}/rfc2136.ini — copy them to the "
                      "machine over a channel you trust")
            else:
                print(f"{name}: its DNS-01 key is withdrawn")
            return 0
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
