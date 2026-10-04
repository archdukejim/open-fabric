import ldb
from samba.dcerpc import security
from samba.sd_utils import SDUtils

# read, write, create and delete children, list, read and change permissions — inherited below the OU (Q4)
FULL = "RPWPCRCCDCLCLORCWOWDSDDTSW"
# what a site's admins may not do to the site's service accounts: write, create or delete, change permissions
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


def ensure_site_acl(samdb, site):
    """Purpose: a site's admins write their own site and nothing else (S2, manual 1.6.3.6): full control below its OU,
             inherited, except its service accounts; checked by every DC, offline too (Q4, Q12).
    Inputs:  samdb — SamDB; site — str (its <site>-admins group exists: ensure_groups).
    Returns: list of str, the access entries added.
    Fails:   ldb.LdbError reading the group or changing a security descriptor; IndexError if the group is missing.
    Feeds:   converge."""
    base = str(samdb.domain_dn())
    found = samdb.search(base=base, scope=ldb.SCOPE_SUBTREE, expression=f"(sAMAccountName={site}-admins)",
                         attrs=["objectSid"])
    sid = str(samdb.schema_format_value("objectSid", found[0]["objectSid"][0]), "utf-8")
    domain_sid = security.dom_sid(samdb.get_domain_sid())
    utils, done = SDUtils(samdb), []
    for dn, ace in ((f"OU={site},OU=sites,{base}", f"(A;CI;{FULL};;;{sid})"),
                    (f"OU=service-accounts,OU={site},OU=sites,{base}", f"(D;CI;{SERVICE_DENY};;;{sid})")):
        if not _has_ace(utils, dn, ace, domain_sid):
            utils.dacl_add_ace(dn, ace)
            done.append(f"{dn}: {ace}")
    return done
