"""fabric's service accounts before 2026-10 (key in service_users -> (name, uid, gid)). They used the names of
Ubuntu's own packages (bind, postgres, ...) and ids Debian reserves (bind: 53, inside base-passwd's 0-99, which
an Ubuntu release upgrade asked to remove). Installs that still have them are moved to the fabric-* accounts in
the 600-649 band by the accounts step (manual 2.7.1.6)."""

PREVIOUS_ACCOUNTS = {
    "bind": ("bind", 53, 53),
    "ldap": ("ldap", 911, 911),
    "nginx": ("nginx", 443, 443),
    "step": ("step", 135, 135),
    "keycloak": ("keycloak", 900, 0),
    "postgres": ("postgres", 901, 901),
    "webui": ("webui", 912, 912),
    "openbao": ("openbao", 913, 913),
    "fluentbit": ("fluentbit", 914, 914),
    "kea": ("kea", 915, 915),
    "freeradius": ("freeradius", 916, 916),
    "adguard": ("adguard", 917, 917),
    "oauth2proxy": ("oauth2proxy", 918, 918),
}
