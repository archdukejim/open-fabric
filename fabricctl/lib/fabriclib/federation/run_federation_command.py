import datetime
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.federation.create_invitation import create_invitation
from fabriclib.federation.federation_status import federation_status
from fabriclib.federation.list_invitations import list_invitations
from fabriclib.federation.revoke_invitation import revoke_invitation
from fabriclib.federation.set_federation_endpoint import set_federation_endpoint

USAGE = """usage: fabricctl federation status                 this install's place in its fabric: upstream, sites, invitations
       fabricctl federation enable | disable       the endpoint sites join through (https://federation.<domain>)
       fabricctl federation invite <site>          a one-time invitation for a new site (good for one hour)
       fabricctl federation invitations            open invitations
       fabricctl federation revoke <id|site>       withdraw an open invitation
  On the new site: sudo fabricctl setup --join '<invitation>'   (a fresh install)"""


def _when(epoch):
    """Purpose: an epoch as local date and time to the minute.
    Inputs:  epoch — int seconds.
    Returns: str "YYYY-MM-DD HH:MM".
    Fails:   never for an int.
    Feeds:   run_federation_command (invite, invitations, status)."""
    return datetime.datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M")


def run_federation_command(ctx, argv):
    """Purpose: `fabricctl federation status | enable | disable | invite | invitations | revoke` — joining sites to
             this install without the web UI (design federation.md §4).
    Inputs:  ctx — SetupContext with state loaded (ctx.vars: the rendered vars); argv — list of str after
             "federation" (default status).
    Returns: exit status: 0 success; 1 a ValidationError or a failed apply; 2 usage (printed to stderr).
    Fails:   ValidationError is caught (exit 1); OSError and errors from set_federation_endpoint other than
             ValidationError propagate.
    Feeds:   fabriclib/cli.py (`fabricctl federation`).
    Notes:   an invitation's secret is printed once, never logged; the actor is root (the CLI runs as root)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    v = ctx.vars
    try:
        if cmd == "status" and not args:
            s = federation_status(v)
            print(f"site {s['site_name']}  domain {s['domain']}  organisation {s['org_domain']}  role {s['role']}")
            print(f"federation endpoint: {'on, https://' + s['endpoint_host'] if s['endpoint'] else 'off'}")
            if s["upstream"]:
                u = s["upstream"]
                print(f"upstream: {u.get('site_name')} ({u.get('domain')}, {u.get('address')}), joined {u.get('joined')}")
            for name, site in sorted(s["sites"].items()):
                print(f"  site {name:<16} {site.get('domain', ''):<28} {site.get('address', ''):<16} "
                      f"joined {site.get('joined', '')}  CA until {site.get('ca_not_after', '')}")
            if not s["sites"] and s["role"] != "site":
                print("  no sites yet" + ("" if s["endpoint"] else ": fabricctl federation enable, then invite <site>"))
            for i in s["invitations"]:
                print(f"  invitation {i['id']} for {i['site']}, open until {_when(i['expires'])}")
            return 0
        if cmd in ("enable", "disable") and not args:
            ok, output = set_federation_endpoint(ctx, "root", cmd == "enable")
            print(output[-2000:] if not ok else
                  f"federation endpoint {'on' if cmd == 'enable' else 'off'}"
                  + (f": https://{v.get('hostname_federation')}" if cmd == "enable" else " (sites that joined stay)"))
            return 0 if ok else 1
        if cmd == "invite" and len(args) == 1:
            inv = create_invitation(v, "root", args[0])
            print(f"Invitation for site {inv['site']} (one use, until {_when(inv['expires'])}). On the new site run:\n")
            print(f"  sudo fabricctl setup --join '{inv['invitation']}'\n")
            print("It carries a secret: send it over a channel you trust. Withdraw it with: "
                  f"fabricctl federation revoke {inv['id']}")
            return 0
        if cmd == "invitations" and not args:
            rows = list_invitations(v)
            for i in rows:
                print(f"{i['id']}  site {i['site']:<16} open until {_when(i['expires'])}  by {i['actor']}")
            if not rows:
                print("no open invitations")
            return 0
        if cmd == "revoke" and len(args) == 1:
            print(f"withdrawn: {revoke_invitation(v, 'root', args[0])} invitation(s)")
            return 0
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
