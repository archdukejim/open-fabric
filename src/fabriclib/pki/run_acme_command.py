import re
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.dns.add_tsig_key import add_tsig_key
from fabriclib.dns.remove_tsig_key import remove_tsig_key
from fabriclib.system.apply_changes import apply_changes

USAGE = """usage: fabricctl acme info                   the ACME directory LAN machines use, and how (2.1.5.8)
       fabricctl acme enroll <name> [--dns]   a machine named <name>.<domain>; --dns: its DNS-01 key (it may change
                                              only _acme-challenge.<name>'s TXT record), for a machine without a
                                              web server on port 80
       fabricctl acme list                    the machines enrolled for DNS-01
       fabricctl acme remove <name>           withdraw a machine's DNS-01 key"""
LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*$")
PREFIX = "acme-"


def _info(v):
    """Purpose: what a LAN machine's ACME client needs (2.1.5.8).
    Inputs:  v — settings: hostname_stepca, hostname_certs, domain, host_ip, bind_dns_port.
    Returns: list of str lines.
    Fails:   KeyError for a missing hostname.
    Feeds:   run_acme_command."""
    return [f"ACME directory: https://{v['hostname_stepca']}/acme/acme/directory",
            f"trust fabric's root CA first: http://{v['hostname_certs']}/ (check its fingerprint there)",
            f"names: <name>.{v['domain']} only; certificates live {int(v.get('cert_service_days', 47))} days: let "
            "the client renew at 30 days old",
            "http-01: the machine answers on port 80 for its name (nothing to enroll)",
            f"dns-01: sudo fabricctl acme enroll <name> --dns; the client sends RFC2136 updates to "
            f"{v.get('host_ip', '<host>')} port {v.get('bind_dns_port', 53)} with the key in /opt/acme-<name>/"
            "rfc2136.ini (copy it to the machine; it is a secret)"]


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
            print("\n".join(_info(ctx.load_state().vars)))
            return 0
        if cmd == "list" and not args:
            keys = [k for k in ctx.load_state().vars.get("tsig_keys") or [] if k.get("name", "").startswith(PREFIX)]
            for k in keys:
                print(f"{k['name'][len(PREFIX):]:<30} DNS-01 key {k['name']} (TXT at _acme-challenge."
                      f"{', '.join(k.get('records') or [])})")
            print(f"{len(keys)} machine(s) enrolled for DNS-01" if keys else "no machine enrolled for DNS-01")
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
                print("\n".join("  " + line for line in _info(v)[:4]))
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
