import re

import ldap
import ldap.filter

from directory import connect, load_config, search

UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")


def check_person(uid, password):
    """A person joining by password (EAP-TTLS/PAP, inside the TLS tunnel):
    {person, allowed, vlan, reason}. The password is checked by binding to
    389-DS as that person over verified LDAPS, so the directory's lockout
    policy counts network logins and a locked account cannot join. Only
    members of a mapped group (fabric-radius.json "people") may join; the
    VLAN comes from the mapping with the lowest priority number that sets
    one (ties by group name)."""
    conf = load_config()
    if not UID_RE.match(uid or "") or not password:
        return {"person": uid or "-", "allowed": False, "vlan": None, "reason": "not a user name and password"}
    users = search("ou=users,ou=accounts," + conf["base"],
                   "(&(objectClass=inetOrgPerson)(uid=%s))" % ldap.filter.escape_filter_chars(uid), ["memberOf"])
    if len(users) != 1:
        return {"person": uid, "allowed": False, "vlan": None, "reason": "no such person"}
    dn, attrs = users[0]
    try:
        connect(dn, password).unbind_s()
    except (ldap.INVALID_CREDENTIALS, ldap.UNWILLING_TO_PERFORM, ldap.CONSTRAINT_VIOLATION):
        # wrong password, or the account is locked (lockout policy, nsAccountLock)
        return {"person": uid, "allowed": False, "vlan": None, "reason": "wrong password or account locked"}
    groups_base = ("ou=groups," + conf["base"]).lower()
    groups = {v.decode().split(",", 1)[0][3:].lower() for v in attrs.get("memberOf") or []
              if v.decode().lower().endswith(groups_base)}
    mapped = sorted((m for m in conf.get("people") or [] if m["group"].lower() in groups),
                    key=lambda m: (m.get("priority", 100), m["group"]))
    if not mapped:
        return {"person": uid, "allowed": False, "vlan": None, "reason": "in no group mapped for 802.1X"}
    vlan = next((m["vlan"] for m in mapped if m.get("vlan")), None)
    return {"person": uid, "allowed": True, "vlan": vlan, "reason": "", "group": mapped[0]["group"]}
