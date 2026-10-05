import re

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,13}[a-z0-9])?$")


def create_machine(samdb, lp, site, name, password):
    """Purpose: pre-create a machine's computer account in the site's OU=machines with a one-time join password
             (manual 2.10.2.3, S6.2), so the machine joins with `adcli --login-type=computer` and no admin password
             is typed on it.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str; name — the machine's name
             (1–15 lower-case letters, digits, dashes: a NetBIOS name); password — the one-time password.
    Returns: {"name", "dn"}.
    Fails:   ValueError for a name that is not a machine name; ldb.LdbError ERR_ENTRY_ALREADY_EXISTS when the name is
             taken, ERR_INSUFFICIENT_ACCESS_RIGHTS outside the agent's site.
    Feeds:   directory_ops (op "create_machine")."""
    if not NAME_RE.match(name or ""):
        raise ValueError(f"not a machine name (1-15 letters, digits, dashes): {name}")
    account = name.upper()               # as Windows and adcli name them: Linux clients look for NAME$ in their keytab
    samdb.newcomputer(account, computerou=f"OU=machines,OU={site},OU=sites")
    samdb.setpassword(f"(sAMAccountName={account}$)", password, force_change_at_next_login=False)
    return {"name": name, "dn": f"CN={account},OU=machines,OU={site},OU=sites,{samdb.domain_dn()}"}
