"""Converge fabric's Samba AD domain to what fabric wants (manual 2.11.2.15, S1.3), inside the DC, as root, on its own
database: no credentials, no network. Run after every start and apply by fabriclib/samba/converge_domain:
    docker exec -i samba python3 /fabric/converge.py < state.json
The wanted state comes on stdin as JSON: {"site", "root" (bool), "password_policy" {…}, "networks" [CIDR…],
"root_ca_pem", "id_range", "groups" [{name, gidNumber, description}], "admin_group", "accounts" {name: password}}
(stdin, never a command line: it holds the service accounts' passwords). Prints one JSON object: {"changed": [what
changed, …]}. Exits 1 with the error on stderr."""
import json
import sys

import ldb

from ensure_ad_site import ensure_ad_site
from ensure_gpo import ensure_gpo
from ensure_groups import ensure_groups
from ensure_layout import ensure_layout
from ensure_schema import ensure_schema
from ensure_service_accounts import ensure_service_accounts
from ensure_site_acl import ensure_site_acl
from ensure_site_info import ensure_site_info
from logon_rights_policy import EXTENSIONS as LOGON_EXTENSIONS, logon_rights_policy
from open_samdb import open_samdb
from root_ca_policy import EXTENSIONS as TRUST_EXTENSIONS, root_ca_policy
from set_password_policy import set_password_policy

CONF = "/data/etc/smb.conf"
BUILTIN_ADMINISTRATORS = "S-1-5-32-544"        # each machine's own local Administrators


def _sid(samdb, name):
    """Purpose: a group's SID by its name.
    Inputs:  samdb — SamDB; name — sAMAccountName.
    Returns: str, the SID.
    Fails:   IndexError if there is no such group; ldb.LdbError from the search.
    Feeds:   converge."""
    res = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                       expression=f"(sAMAccountName={ldb.binary_encode(name)})", attrs=["objectSid"])
    return str(samdb.schema_format_value("objectSid", res[0]["objectSid"][0]), "utf-8")


def converge(state):
    """Purpose: every part of the domain fabric owns, in order: the schema, the layout, the site's id block, the
             groups, the site's service accounts, its access entries, the AD site and its subnets, the password
             policy, the domain's trust GPO (fabric's root CA) and the site's log-on GPO. Each part changes only what
             differs, so a second run changes nothing.
    Inputs:  state — dict: site (str), root (bool: the root site, which also holds the organisation's items and the
             domain-wide trust GPO), password_policy (dict, every key), networks (list of CIDR), root_ca_pem (str),
             id_range ("first-last"), groups (fabric's ldap_groups), admin_group (the web UI's admin group, in the
             log-on policy), accounts ({sAMAccountName: password}: the site's service accounts).
    Returns: list of str, what changed.
    Fails:   KeyError for a missing state key; whatever a part raises (ldb.LdbError, OSError, CalledProcessError).
    Feeds:   this script's main."""
    site, root = state["site"], bool(state["root"])
    changed = [f"schema: {name} added" for name in ensure_schema(CONF)]
    samdb, lp = open_samdb(CONF)
    changed += ensure_layout(samdb, site, root)
    changed += ensure_site_info(samdb, site, state["id_range"])
    changed += ensure_groups(samdb, site, root, state["groups"])
    changed += ensure_service_accounts(samdb, lp, site, state["accounts"])
    changed += ensure_site_acl(samdb, site)
    changed += ensure_ad_site(samdb, site, list(state["networks"]))
    changed += [f"password policy: {a}" for a in set_password_policy(samdb, state["password_policy"])]
    base = str(samdb.domain_dn())
    if root:
        changed += ensure_gpo(samdb, lp, "fabric: trust in fabric's root CA", base, TRUST_EXTENSIONS,
                              {"Machine/Registry.pol": root_ca_policy(state["root_ca_pem"])})
    # a machine's own local Administrators keep log-on too: the policy replaces Windows' local lists, and its owners
    # must never be locked out of it
    sids = [_sid(samdb, g) for g in (f"{site}-users", f"{site}-admins", state["admin_group"], "fabric-break-glass")]
    sids.append(BUILTIN_ADMINISTRATORS)
    changed += ensure_gpo(samdb, lp, f"fabric: {site} log-on rights", f"OU={site},OU=sites,{base}", LOGON_EXTENSIONS,
                          {"Machine/Microsoft/Windows NT/SecEdit/GptTmpl.inf": logon_rights_policy(sids)})
    return changed


if __name__ == "__main__":
    try:
        result = converge(json.load(sys.stdin))
    except Exception as e:                  # the caller reports it; the DC keeps running
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"changed": result}))
