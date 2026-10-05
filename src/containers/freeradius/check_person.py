import re

import ldap
import ldap.filter

from directory import connect, load_config, search

UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")
DOMAIN_USERS_RID = "513"                 # a person's primary group: not listed in memberOf


def person_groups(attrs, sites):
    """Purpose: the names of a person's groups, as radius_people names them (lower case).
    Inputs:  attrs — dict {attr: [bytes]} with memberOf and primaryGroupID; sites — str, the DN of OU=sites.
    Returns: set of str: the CN of each group fabric manages (under OU=sites; AD's own groups such as Guests or
             Administrators never match a mapping), and "domain users" (fabric's `users`, D95) when it is the
             primary group.
    Fails:   UnicodeDecodeError for a value that is not UTF-8.
    Feeds:   check_person."""
    tail = "," + sites.lower()
    groups = {dn.split(",", 1)[0][3:].lower() for dn in (v.decode() for v in attrs.get("memberOf") or [])
              if dn.lower().endswith(tail)}
    if [v.decode() for v in attrs.get("primaryGroupID") or []] == [DOMAIN_USERS_RID]:
        groups |= {"domain users", "users"}
    return groups


def check_person(uid, password):
    """Purpose: decide a person joining by password (EAP-TTLS/PAP, inside the TLS tunnel). The password is
             checked by binding to the DC as that person over verified LDAPS, so the domain's lockout policy
             counts network logins; only members of a group mapped in fabric-radius.json "people" may join
             (manual 1.6.3.10).
    Inputs:  uid — str user name (sAMAccountName, must match UID_RE); password — str. Reads fabric-radius.json and
             the people under OU=sites (never the service accounts) with their groups.
    Returns: dict {person, allowed, vlan, reason}; when allowed also "group" (the best mapping). vlan comes from
             the mapping with the lowest priority number that sets one (ties by group name), else None.
    Fails:   ldap errors other than a refused bind (directory down, timeout) and config errors (OSError,
             KeyError) propagate; the caller turns them into Access-Reject.
    Feeds:   fabric_radius._decide_person."""
    conf = load_config()
    if not UID_RE.match(uid or "") or not password:
        return {"person": uid or "-", "allowed": False, "vlan": None, "reason": "not a user name and password"}
    users = [(dn, a) for dn, a in search(
        "OU=sites," + conf["base"],
        "(&(objectCategory=person)(objectClass=user)(sAMAccountName=%s))" % ldap.filter.escape_filter_chars(uid),
        ["memberOf", "primaryGroupID"], subtree=True) if ",ou=service-accounts," not in dn.lower()]
    if len(users) != 1:
        return {"person": uid, "allowed": False, "vlan": None, "reason": "no such person"}
    dn, attrs = users[0]
    try:
        connect(dn, password).unbind_s()
    except (ldap.INVALID_CREDENTIALS, ldap.UNWILLING_TO_PERFORM, ldap.CONSTRAINT_VIOLATION):
        # a wrong password, or the account locked, disabled, expired or still on its one-time password
        return {"person": uid, "allowed": False, "vlan": None, "reason": "wrong password or account locked"}
    groups = person_groups(attrs, "OU=sites," + conf["base"])
    mapped = sorted((m for m in conf.get("people") or [] if m["group"].lower() in groups),
                    key=lambda m: (m.get("priority", 100), m["group"]))
    if not mapped:
        return {"person": uid, "allowed": False, "vlan": None, "reason": "in no group mapped for 802.1X"}
    vlan = next((m["vlan"] for m in mapped if m.get("vlan")), None)
    return {"person": uid, "allowed": True, "vlan": vlan, "reason": "", "group": mapped[0]["group"]}
