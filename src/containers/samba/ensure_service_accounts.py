import ldb
from samba.credentials import DONT_USE_KERBEROS, Credentials
from samba.samdb import SamDB

import paths

DONT_EXPIRE_PASSWORD = 0x10000          # userAccountControl: a service account's password does not expire


def _signs_in(lp, account, password):
    """Purpose: whether an account signs in to this DC over LDAP with a password (NTLM, on loopback).
    Inputs:  lp — LoadParm; account — sAMAccountName; password — str.
    Returns: bool.
    Fails:   never (a refused sign-in is False).
    Feeds:   ensure_service_accounts."""
    creds = Credentials()
    creds.guess(lp)
    creds.set_username(account)
    creds.set_password(password)
    creds.set_domain(lp.get("workgroup"))
    creds.set_kerberos_state(DONT_USE_KERBEROS)
    try:
        SamDB(url="ldap://127.0.0.1", credentials=creds, lp=lp)
        return True
    except ldb.LdbError:
        return False


def ensure_service_accounts(samdb, lp, site, accounts):
    """Purpose: a site's service accounts in the directory (manual 1.6.3.7) — fabric-agent, Keycloak, FreeRADIUS — in
             its OU=service-accounts, their passwords never expiring, each signing in with the password fabric keeps
             for it (set only when a sign-in with it fails: a new account, or a password fabric changed).
    Inputs:  samdb — SamDB (system); lp — LoadParm; site — str; accounts — {sAMAccountName: password}.
    Returns: list of str, what was created or set.
    Fails:   ldb.LdbError from a creation or change AD refuses.
    Feeds:   converge."""
    done = []
    for name, password in sorted(accounts.items()):
        found = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                             expression=f"(sAMAccountName={ldb.binary_encode(name)})",
                             attrs=["userAccountControl"])
        if not found:
            services = paths.relative(samdb, f"OU=service-accounts,{paths.site_dn(samdb, site)}")
            samdb.newuser(name, password, userou=services, force_password_change_at_next_login_req=False)
            done.append(f"service account {name} created")
            found = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                                 expression=f"(sAMAccountName={ldb.binary_encode(name)})",
                                 attrs=["userAccountControl"])
        elif not _signs_in(lp, name, password):
            samdb.setpassword(f"(sAMAccountName={ldb.binary_encode(name)})", password,
                              force_change_at_next_login=False)
            done.append(f"service account {name}: password set")
        uac = int(str(found[0]["userAccountControl"][0]))
        if not uac & DONT_EXPIRE_PASSWORD:
            samdb.modify(ldb.Message.from_dict(samdb, {"dn": str(found[0].dn),
                                                       "userAccountControl": str(uac | DONT_EXPIRE_PASSWORD)},
                                               ldb.FLAG_MOD_REPLACE))
    return done
