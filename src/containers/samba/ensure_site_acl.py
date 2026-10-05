import ldb
from samba.dcerpc import security
from samba.sd_utils import SDUtils

# read, write, create and delete children, list, read and change permissions — inherited below the OU (Q4)
FULL = "RPWPCRCCDCLCLORCWOWDSDDTSW"
# what may not be done to a site's service accounts: write, create or delete, change permissions
SERVICE_DENY = "WPCCDCWDWOSDDT"


def _has_ace(utils, dn, ace, domain_sid):
    """Purpose: whether an object's DACL already holds an access entry (compared parsed: Samba rewrites SDDL text).
    Inputs:  utils — SDUtils; dn — str; ace — str, one SDDL entry "(A;CI;…;;;S-…)"; domain_sid — security.dom_sid.
    Returns: bool.
    Fails:   ldb.LdbError reading the descriptor; RuntimeError for invalid SDDL.
    Feeds:   ensure_site_acl."""
    want = security.descriptor.from_sddl("D:" + ace, domain_sid).dacl.aces[0]
    return any(a.type == want.type and a.flags == want.flags and a.access_mask == want.access_mask
               and str(a.trustee) == str(want.trustee) for a in utils.read_sd_on_dn(dn).dacl.aces)


def _sid(samdb, name):
    """Purpose: an account's or group's SID by its name.
    Inputs:  samdb — SamDB; name — sAMAccountName.
    Returns: str.
    Fails:   IndexError if it does not exist; ldb.LdbError from the search.
    Feeds:   ensure_site_acl."""
    res = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                       expression=f"(sAMAccountName={ldb.binary_encode(name)})", attrs=["objectSid"])
    return str(samdb.schema_format_value("objectSid", res[0]["objectSid"][0]), "utf-8")


def ensure_site_acl(samdb, site):
    """Purpose: who may write what in a site (S2, manual 1.6.3.6), checked by every DC, offline too (Q4, Q12): the
             site's admins and its fabric-agent account have full control below the site's OU, inherited, but not
             over its service accounts; its Keycloak account has full control of the site's people only (sign-in
             changes passwords and lockouts).
    Inputs:  samdb — SamDB; site — str (its groups and service accounts exist: ensure_groups,
             ensure_service_accounts).
    Returns: list of str, the access entries added.
    Fails:   ldb.LdbError reading a principal or changing a security descriptor; IndexError if one is missing.
    Feeds:   converge."""
    base = str(samdb.domain_dn())
    site_dn = f"OU={site},OU=sites,{base}"
    services = f"OU=service-accounts,{site_dn}"
    people = f"OU=people,{site_dn}"
    entries = []
    for principal in (f"{site}-admins", f"fabric-agent-{site}"):
        sid = _sid(samdb, principal)
        entries += [(site_dn, f"(A;CI;{FULL};;;{sid})"), (services, f"(D;CI;{SERVICE_DENY};;;{sid})")]
    entries.append((people, f"(A;CI;{FULL};;;{_sid(samdb, f'fabric-keycloak-{site}')})"))
    domain_sid = security.dom_sid(samdb.get_domain_sid())
    utils, done = SDUtils(samdb), []
    for dn, ace in entries:
        if not _has_ace(utils, dn, ace, domain_sid):
            utils.dacl_add_ace(dn, ace)
            done.append(f"{dn}: {ace}")
    return done
