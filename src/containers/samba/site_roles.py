"""The roles that administer a site (2.1.9.13, manual 1.6.3.6): each its own group in the site's OU=groups, so each can
be given to a different admin group; `<site>-admins` is a member of all of them. A parent site's roles reach the sites
below it (2.1.6.20)."""

# role -> what its group's description says
ROLES = {
    "ou-admins": "Manage the site's OU: people, groups and sub-OUs",
    "machine-admins": "Add, enable and remove the site's machines and devices",
    "gpo-admins": "Edit the site's own Group Policy, and block what a parent did not enforce",
    "linux-sudo": "Run any command as root on the site's Linux machines",
    "windows-admins": "Local Administrators on the site's Windows machines",
}


def role_group(site, role):
    """Purpose: a role's group name.
    Inputs:  site — str; role — a key of ROLES.
    Returns: str "<site>-<role>".
    Fails:   KeyError for an unknown role.
    Feeds:   ensure_groups, ensure_site_acl, ensure_sudo_rule, converge."""
    ROLES[role]
    return f"{site}-{role}"
