from fabriclib.federation.constants import SITE_NAME_RE


def site_name_problem(name, org_ous=()):
    """Purpose: why a name cannot be a site's name, if it cannot: it must be one host-name label and must not
             be a top-level OU of the organisation (a site's directory part is ou=<site>,<base DN>, beside them).
    Inputs:  name — str; org_ous — the organisation's top-level OU names (ldap_organizational_units without a
             parent), default none.
    Returns: None when the name is fine, else the reason (str).
    Fails:   never.
    Feeds:   create_invitation, deploy/check_fixed_identity."""
    if not SITE_NAME_RE.match(str(name)):
        return f"invalid site name: {name!r} (one host-name label: a-z, 0-9, -)"
    if str(name) in set(org_ous):
        return f"{name} is a directory OU of the organisation (ou={name}): choose another site name"
    return None
