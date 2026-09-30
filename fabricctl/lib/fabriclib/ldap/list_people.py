from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_PEOPLE = r'''
users = []
for dn, a in c.search_s(USERS, ldap.SCOPE_ONELEVEL, "(objectClass=inetOrgPerson)",
                        ["uid", "cn", "mail", "memberOf", "nsAccountLock"]):
    users.append({"uid": one(a, "uid"), "name": one(a, "cn"), "mail": one(a, "mail"),
                  "locked": one(a, "nsAccountLock").lower() == "true",
                  "groups": sorted(m.split(",", 1)[0][3:] for m in s(a.get("memberOf"))
                                   if m.lower().endswith(GROUPS.lower()))})
groups = []
for dn, a in c.search_s(GROUPS, ldap.SCOPE_ONELEVEL, "(objectClass=groupOfNames)", ["cn", "member"]):
    groups.append({"name": one(a, "cn"), "members": len(a.get("member", []))})
out({"users": sorted(users, key=lambda u: u["uid"]), "groups": sorted(groups, key=lambda g: g["name"])})
'''


def list_people(v):
    """People and their groups, read-only: they are managed in Keycloak,
    which writes them to 389-DS (link to its admin console included). No
    passwords are read."""
    people = run_dirsrv(v, _PEOPLE)
    realm = v.get("webui_realm") or v.get("domain", "")
    people["keycloak_url"] = f"https://{v.get('hostname_keycloak', '')}/admin/{realm}/console/"
    return people
