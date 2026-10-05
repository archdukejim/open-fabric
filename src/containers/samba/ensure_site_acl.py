from acl_entries import ensure_aces, sid_of
import paths
from site_roles import role_group

# read, write, create and delete children, list, read permissions, delete — inherited below the OU (Q4); never
# change permissions or owner (WD, WO): a site could otherwise protect its OU from its parents' inherited access (D105)
FULL = "RPWPCRCCDCLCLORCSDDTSW"
# what may not be done to a site's service accounts: write, create or delete, change permissions
SERVICE_DENY = "WPCCDCWDWOSDDT"
# the attributes a site's GPO admins write on its OU: its GPO links and its blocked inheritance (schema GUIDs)
GP_LINK, GP_OPTIONS = "f30e3bbe-9ff0-11d1-b603-0000f80367c1", "f30e3bbf-9ff0-11d1-b603-0000f80367c1"


def ensure_site_acl(samdb, site, root):
    """Purpose: who may write what in a site (S2, D103, manual 1.6.3.6), checked by every DC, offline too (Q4, Q12):
             its `<site>-ou-admins` and its fabric-agent account have full control below the site's OU, inherited
             (so into the sites nested below it, D105); its `<site>-machine-admins` full control of its machines and
             devices; its `<site>-gpo-admins` its OU's GPO links and blocked inheritance (their own GPOs: admin_gpo);
             none of them over permissions, nor over its own or a nested site's service accounts; its Keycloak account
             full control of the site's people only (sign-in changes passwords and lockouts), and at the root site
             the members of the organisation's groups (Keycloak's group mapper).
    Inputs:  samdb — SamDB; site — str (its groups and service accounts exist: ensure_groups,
             ensure_service_accounts); root — bool.
    Returns: list of str, the access entries added.
    Fails:   ldb.LdbError reading a principal or changing a security descriptor; IndexError if one is missing.
    Feeds:   converge."""
    site_dn = paths.site_dn(samdb, site)
    services = f"OU=service-accounts,{site_dn}"
    entries = []
    for principal in (role_group(site, "ou-admins"), f"fabric-agent-{site}"):
        entries.append((site_dn, f"(A;CI;{FULL};;;{sid_of(samdb, principal)})"))
    machines = sid_of(samdb, role_group(site, "machine-admins"))
    entries += [(f"OU={ou},{site_dn}", f"(A;CI;{FULL};;;{machines})") for ou in ("machines", "devices")]
    gpo = sid_of(samdb, role_group(site, "gpo-admins"))
    entries += [(site_dn, f"(OA;;RPWP;{attr};;{gpo})") for attr in (GP_LINK, GP_OPTIONS)]
    # the service accounts are fabric's: no one's inherited access reaches them, this site's or a parent's
    for owner in [site] + paths.ancestors(samdb, site):
        for principal in (role_group(owner, "ou-admins"), role_group(owner, "machine-admins"), f"{owner}-admins",
                          f"fabric-agent-{owner}"):
            entries.append((services, f"(D;CI;{SERVICE_DENY};;;{sid_of(samdb, principal)})"))
    keycloak = sid_of(samdb, f"fabric-keycloak-{site}")
    entries.append((f"OU=people,{site_dn}", f"(A;CI;{FULL};;;{keycloak})"))
    if root:            # Keycloak's group mapper writes memberships of the organisation's groups (LDAP_ONLY)
        entries.append((f"OU=groups,{paths.organisation_dn(samdb)}", f"(A;CI;RPWPLCLORC;;;{keycloak})"))
    return ensure_aces(samdb, entries)
